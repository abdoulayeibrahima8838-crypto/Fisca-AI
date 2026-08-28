#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag.py — Moteur de recherche CGI 2026 pour Fisca AI.

Logique (Phase 3 - recherche hybride) :
  1. Recherche VECTORIELLE (similarité sémantique) + recherche par MOTS-CLES
     (PostgreSQL full-text) en parallèle -> fusionnées par rang (RRF) pour
     obtenir les articles pivot.
  2. Expansion par renvois explicites, priorisée par le TYPE et le POIDS de
     la relation (SANCTIONNE_PAR, DEFINI_PAR... voir Phase 2), pas un simple
     "les 4 premiers renvois trouvés".
  3. Construction du contexte -> LLM -> vérification anti-hallucination.

Ce fichier suppose une connexion psycopg2 déjà configurée (`db`) et un
client Gemini pour les embeddings/la génération. Il tourne sur Render
(accès réseau), pas dans l'environnement de préparation.

Les fichiers cgi2026_articles_enrichis.json et cgi2026_refs_enrichis.json
(produits par enrichir_phase1.py / enrichir_phase2.py) sont chargés en
mémoire au démarrage, s'ils sont présents à côté de ce fichier - sans eux,
le moteur continue de fonctionner (juste sans les enrichissements).
"""

import json
import os
import re
from dataclasses import dataclass, field

from google.genai import types as genai_types

from vocabulaire import elargir_question


TOP_K_VECTOR = 5          # nb d'articles récupérés par similarité vectorielle
TOP_K_MOTS_CLES = 5       # nb d'articles récupérés par recherche mots-clés
MAX_EXPANSION_PER_ARTICLE = 2  # nb max de renvois ajoutés par article pivot
                                 # (resserré de 4 à 2 le 28/08 - un cas reel a montre
                                 # que 5 pivots x 4 renvois = 25 articles au total rendait
                                 # les reponses trop lentes (43s) et propices aux erreurs
                                 # de citation, Gemini se perdant dans un contexte trop
                                 # volumineux. Les relations les plus fortes (SANCTIONNE_PAR,
                                 # DEFINI_PAR) restent triees en premier, donc toujours
                                 # incluses en priorite malgre le plafond plus bas.
SEUIL_POIDS_EXPANSION_NIVEAU1 = 0.80  # en dessous, un renvoi n'est ajoute qu'en dernier recours


# ---------------------------------------------------------------------------
# Chargement des enrichissements Phase 1 (matière fiscale, valeurs, exceptions
# par article) et Phase 2 (type + poids de chaque renvoi) - fait une seule
# fois, au chargement du module. Repli silencieux sur des dicts vides si les
# fichiers ne sont pas encore déployés, pour ne jamais faire planter le RAG
# de base par leur absence.
# ---------------------------------------------------------------------------
_DOSSIER_MODULE = os.path.dirname(os.path.abspath(__file__))


def _charger_json_optionnel(nom_fichier):
    chemin = os.path.join(_DOSSIER_MODULE, nom_fichier)
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[Fisca AI][RAG] Enrichissement '{nom_fichier}' non chargé ({type(e).__name__}) - le RAG continue sans.")
        return None


_articles_enrichis = _charger_json_optionnel("cgi2026_articles_complet.json")
_SOURCE_METADONNEES = "complet (Phase 5)"
if _articles_enrichis is None:
    # Repli : le fichier cumulatif Phase 5 n'est pas encore deploye -
    # on continue avec les seules metadonnees Phase 1, comme avant.
    _articles_enrichis = _charger_json_optionnel("cgi2026_articles_enrichis.json")
    _SOURCE_METADONNEES = "enrichis (Phase 1 seule)"
_METADONNEES_PAR_ARTICLE = (
    {a["article_id"]: a for a in _articles_enrichis} if _articles_enrichis else {}
)

_refs_enrichis = _charger_json_optionnel("cgi2026_refs_enrichis.json")
_POIDS_RELATIONS = (
    {(r["source_article_id"], r["target_article_id"]): r for r in _refs_enrichis}
    if _refs_enrichis else {}
)

# Fiches par impot (Phase 5, Volet 3) - utilisees pour les questions LARGES
# ("explique-moi toute la taxe professionnelle"), en complement de la
# recherche article-par-article habituelle.
_fiches_par_impot = _charger_json_optionnel("cgi2026_fiches_par_impot.json")
_FICHES_PAR_MATIERE = (
    {f["matiere_fiscale"]: f for f in _fiches_par_impot} if _fiches_par_impot else {}
)

# Espace Procedures (session dediee entreprises) : fiches par PROCEDURE
# (contrôle, sanctions, recouvrement...) et fiches par ACTE (une vraie
# action entreprise - "creer mon entreprise", "faire face a un controle").
# Meme principe que les fiches par impot : utilisees pour les questions
# LARGES, jamais pour les questions ciblees habituelles.
_fiches_procedures = _charger_json_optionnel("cgi2026_fiches_procedures.json")
_FICHES_PAR_PROCEDURE = (
    {f["matiere_fiscale"]: f for f in _fiches_procedures} if _fiches_procedures else {}
)

_fiches_par_acte = _charger_json_optionnel("cgi2026_fiches_par_acte.json")
_FICHES_PAR_ACTE = (
    {f["acte"]: f for f in _fiches_par_acte} if _fiches_par_acte else {}
)

print(
    f"[Fisca AI][RAG] Enrichissements chargés : "
    f"{len(_METADONNEES_PAR_ARTICLE)} article(s) — source : {_SOURCE_METADONNEES}, "
    f"{len(_POIDS_RELATIONS)} relation(s) qualifiées Phase 2, "
    f"{len(_FICHES_PAR_MATIERE)} fiche(s) par impôt, "
    f"{len(_FICHES_PAR_PROCEDURE)} fiche(s) par procédure, "
    f"{len(_FICHES_PAR_ACTE)} fiche(s) par acte (Espace Procédures)."
)


@dataclass
class RetrievedArticle:
    article_id: str
    text: str
    livre_titre: str = ""
    chapitre_titre: str = ""
    section_titre: str = ""
    role: str = "pivot"   # 'pivot' | 'lie'  (article lié via renvoi)
    matiere_fiscale: str = ""
    type_relation: str = ""   # rempli uniquement pour les articles 'lie'
    score: float = 0.0        # score composite (recherche hybride)


def search_pivot_articles(db, query_embedding, top_k=TOP_K_VECTOR):
    """Étape 1 : recherche vectorielle pure -> articles pivot.
    'db' est une connexion psycopg2 (pas un curseur) - on ouvre le
    curseur ici, comme partout ailleurs dans Fisca AI (voir app.py)."""
    cur = db.cursor()
    cur.execute(
        """
        SELECT article_id, text, livre_titre, chapitre_titre, section_titre
        FROM cgi_articles
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_embedding, top_k),
    )
    rows = cur.fetchall()
    return [
        RetrievedArticle(
            article_id=r["article_id"], text=r["text"],
            livre_titre=r["livre_titre"], chapitre_titre=r["chapitre_titre"],
            section_titre=r["section_titre"], role="pivot",
            matiere_fiscale=_METADONNEES_PAR_ARTICLE.get(r["article_id"], {}).get("matiere_fiscale", ""),
        )
        for r in rows
    ]


def search_keywords(db, question, top_k=TOP_K_MOTS_CLES):
    """Recherche par MOTS-CLES (complément de la recherche vectorielle) -
    utilise le full-text search natif de PostgreSQL (configuration
    'french', qui gère la conjugaison/accords). Utile pour les questions
    qui citent un terme juridique precis ('facture certifiée', 'flagrance
    fiscale') que la recherche vectorielle seule peut parfois diluer parmi
    des articles seulement 'proches par le sens'."""
    cur = db.cursor()
    cur.execute(
        """
        SELECT article_id, text, livre_titre, chapitre_titre, section_titre,
               ts_rank(to_tsvector('french', text), plainto_tsquery('french', %s)) AS rang
        FROM cgi_articles
        WHERE to_tsvector('french', text) @@ plainto_tsquery('french', %s)
        ORDER BY rang DESC
        LIMIT %s
        """,
        (question, question, top_k),
    )
    rows = cur.fetchall()
    return [
        RetrievedArticle(
            article_id=r["article_id"], text=r["text"],
            livre_titre=r["livre_titre"], chapitre_titre=r["chapitre_titre"],
            section_titre=r["section_titre"], role="pivot",
            matiere_fiscale=_METADONNEES_PAR_ARTICLE.get(r["article_id"], {}).get("matiere_fiscale", ""),
        )
        for r in rows
    ]


def recherche_hybride(db, query_embedding, question, top_k=TOP_K_VECTOR):
    """Combine recherche vectorielle et recherche par mots-clés par fusion
    de rang (Reciprocal Rank Fusion, RRF) - technique standard pour
    combiner deux classements sans avoir a normaliser des echelles de
    score incompatibles (distance cosinus vs score de pertinence textuel).
    Chaque article marque points = 1/(60+rang) dans chaque liste ou il
    apparait ; les scores sont ensuite additionnes et retries.

    Depuis la Phase 4, la recherche par mots-cles utilise la question
    ELARGIE (synonymes/vocabulaire naturel - voir vocabulaire.py) : une
    question contenant "IS" ou "facture electronique" retrouve aussi les
    articles qui emploient les termes officiels du CGI ("impot sur les
    societes", "systeme electronique certifie de facturation").

    Complete le score composite (point #28 du plan initial) : si la
    question nomme clairement une matiere fiscale connue (ex. "TVA",
    "taxe professionnelle"), un leger bonus est applique aux articles de
    cette meme matiere - departage les cas proches en faveur de l'impot
    explicitement mentionne, sans jamais l'imposer de force (le bonus est
    petit, il ne peut pas faire remonter un article hors-sujet)."""
    K_RRF = 60
    BONUS_MATIERE_FISCALE = 0.01  # petit, ne fait que departager, jamais dominer le classement
    BONUS_THEME_CIBLE = 0.05  # plus fort : sert a departager face a un article tres
                                # dominant sur un terme generique (ex. "NIF" -> art. 775,
                                # qui definit le NIF lui-meme et ecrase tout le reste sans ce coup de pouce)

    # Themes cibles : quand la question elargie contient un de ces termes
    # tres specifiques, les articles du THEME correspondant recoivent un
    # bonus plus fort que le simple bonus de matiere fiscale - utile pour
    # les cas ou un article generique (ex. definir le NIF) domine sinon
    # systematiquement un article plus specifique mais moins "dense" en
    # mots-cles (ex. l'article qui definit vraiment un regime precis).
    THEMES_CIBLES = {
        "Régimes d'imposition": [
            "régime réel normal d'imposition", "régime réel simplifié d'imposition",
            "régime du forfait", "régimes particuliers d'imposition",
        ],
    }

    # Matieres ciblees : meme principe que THEMES_CIBLES, mais quand l'article
    # definisseur n'a pas de theme_principal (souvent le cas pour les
    # matieres transversales courtes comme "precompte"). Ajoute au fil des
    # cas reels observes en production - ex. "precompte" confondu avec les
    # articles d'"acompte", mot proche mais concept different.
    MATIERES_CIBLES = {
        "Autres prélèvements et retenues à la source": ["précompte"],
    }

    # Articles cibles : le bonus le plus precis possible, directement sur
    # UN numero d'article. Necessaire quand le bonus par theme (ci-dessus)
    # ne suffit pas a departager - cas reel observe : "regime du forfait"
    # (NIF P) faisait remonter l'article 119 (regime reel simplifie) au
    # lieu du 120 (le vrai regime du forfait), parce que 119 mentionne
    # "regime du forfait" en passant (comme exception d'option), ce qui
    # trompe la recherche par mots-cles. Un bonus direct sur l'article
    # tranche sans ambiguite pour ces cas de confusion entre articles tres
    # proches thematiquement.
    BONUS_ARTICLE_CIBLE = 0.08  # plus fort que BONUS_THEME_CIBLE : la precision
                                  # est maximale ici (un seul article vise, pas un theme entier)
    ARTICLES_CIBLES = {
        "118": ["régime réel normal d'imposition"],
        "119": ["régime réel simplifié d'imposition"],
        "120": ["régime du forfait"],
        "94": ["précompte"],  # confusion frequente avec les articles d'"acompte" (cf. NIF P)
        # Articles tres courts (une phrase), reconstruits lors du demelage
        # de 394quinquies - texte trop pauvre pour bien ressortir seul en
        # recherche vectorielle/mots-cles sans coup de pouce direct.
        "394quaterdecies": ["taux de la taxe sur les paiements en numéraire"],
        "394sexies": ["taux de la taxe sur les dépôts", "taux de la taxe sur les dépôts et transferts d'argent"],
        "394decies": ["qu'est-ce que la taxe sur les paiements en numéraire", "assujettis à la taxe sur les paiements en numéraire"],
        "394nonies": ["collecter la taxe sur les dépôts", "qui doit collecter la taxe sur les dépôts et transferts d'argent"],
        "682": ["doctrine fiscale"],  # l'article definit le concept sans jamais utiliser le mot "doctrine"
    }

    question_elargie = elargir_question(question)
    matiere_detectee = detecter_matiere_dans_question(question)

    theme_cible = None
    for theme, termes_declencheurs in THEMES_CIBLES.items():
        if any(t in question_elargie.lower() for t in termes_declencheurs):
            theme_cible = theme
            break

    matiere_cible = None
    for matiere, termes_declencheurs in MATIERES_CIBLES.items():
        if any(t in question_elargie.lower() for t in termes_declencheurs):
            matiere_cible = matiere
            break

    article_cible = None
    for article_id, termes_declencheurs in ARTICLES_CIBLES.items():
        if any(t in question_elargie.lower() for t in termes_declencheurs):
            article_cible = article_id
            break

    resultats_vecteur = search_pivot_articles(db, query_embedding, top_k=top_k * 2)
    resultats_mots_cles = search_keywords(db, question_elargie, top_k=top_k * 2)

    articles_par_id = {}
    scores = {}

    for rang, a in enumerate(resultats_vecteur, start=1):
        articles_par_id[a.article_id] = a
        scores[a.article_id] = scores.get(a.article_id, 0.0) + 1.0 / (K_RRF + rang)

    for rang, a in enumerate(resultats_mots_cles, start=1):
        articles_par_id.setdefault(a.article_id, a)
        scores[a.article_id] = scores.get(a.article_id, 0.0) + 1.0 / (K_RRF + rang)

    if matiere_detectee:
        for article_id, a in articles_par_id.items():
            if a.matiere_fiscale == matiere_detectee:
                scores[article_id] = scores.get(article_id, 0.0) + BONUS_MATIERE_FISCALE

    if article_cible and article_cible not in articles_par_id:
        # Filet de securite : si l'article vise avec certitude n'est meme
        # pas remonte par la recherche initiale (vectorielle + mots-cles),
        # on va le chercher directement plutot que de perdre le benefice
        # du bonus - garantit que le bonus a toujours un effet reel.
        # IMPORTANT : cette injection doit avoir lieu AVANT le calcul du
        # bonus de theme ci-dessous, sinon l'article injecte n'en beneficie
        # jamais (bug reel observe : NIF P injectait le 120 mais APRES le
        # bonus de theme, qui avait deja profite au 119 present depuis le
        # debut - resultat, 119 gagnait quand meme malgre le bonus article).
        cur = db.cursor()
        cur.execute(
            "SELECT text, livre_titre, chapitre_titre, section_titre FROM cgi_articles WHERE article_id = %s",
            (article_cible,),
        )
        row = cur.fetchone()
        if row:
            articles_par_id[article_cible] = RetrievedArticle(
                article_id=article_cible, text=row["text"],
                livre_titre=row["livre_titre"], chapitre_titre=row["chapitre_titre"],
                section_titre=row["section_titre"], role="pivot",
                matiere_fiscale=_METADONNEES_PAR_ARTICLE.get(article_cible, {}).get("matiere_fiscale", ""),
            )
            scores[article_cible] = 0.0

    if theme_cible:
        for article_id in articles_par_id:
            meta = _METADONNEES_PAR_ARTICLE.get(article_id, {})
            theme_article = (meta.get("themes") or {}).get("principal")
            if theme_article == theme_cible:
                scores[article_id] = scores.get(article_id, 0.0) + BONUS_THEME_CIBLE

    if matiere_cible:
        for article_id, a in articles_par_id.items():
            if a.matiere_fiscale == matiere_cible:
                scores[article_id] = scores.get(article_id, 0.0) + BONUS_THEME_CIBLE

    if article_cible and article_cible in articles_par_id:
        scores[article_cible] = scores.get(article_cible, 0.0) + BONUS_ARTICLE_CIBLE

    classement = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
    resultat = []
    for article_id, score in classement:
        a = articles_par_id[article_id]
        a.score = round(score, 5)
        resultat.append(a)
    return resultat


def expand_via_refs(db, pivots, max_per_article=MAX_EXPANSION_PER_ARTICLE):
    """Étape 2 : pour chaque article pivot, ajoute les articles qu'il cite
    explicitement - en PRIORISANT les relations les plus fortes (voir
    Phase 2 : SANCTIONNE_PAR, DEFINI_PAR, DEROGE_A... poids 1.00) avant
    les simples renvois génériques (poids 0.70), plutôt que de prendre
    les 4 premiers trouvés sans distinction. Si les enrichissements Phase 2
    ne sont pas chargés, se comporte comme avant (ordre d'insertion)."""
    pivot_ids = {a.article_id for a in pivots}
    seen = set(pivot_ids)
    candidats = []  # (poids, type_relation, article_id) avant recuperation du texte

    for p in pivots:
        cur = db.cursor()
        cur.execute(
            """SELECT target_article_id FROM article_refs WHERE source_article_id = %s""",
            (p.article_id,),
        )
        for row in cur.fetchall():
            cible = row["target_article_id"]
            if cible in seen:
                continue
            seen.add(cible)
            info_relation = _POIDS_RELATIONS.get((p.article_id, cible))
            poids = info_relation["poids"] if info_relation else 0.70
            type_relation = info_relation["type_relation"] if info_relation else "RENVOIE_A"
            candidats.append((poids, type_relation, cible))

    # Tri par poids decroissant : les relations fortes (sanctions, definitions,
    # derogations) passent avant les renvois generiques, meme si ceux-ci ont
    # ete trouves en premier dans le texte.
    candidats.sort(key=lambda c: -c[0])
    plafond = max_per_article * max(len(pivots), 1)

    # Phase 5, Volet 4 : s'il reste de la place sous le plafond, completer
    # avec les liens IMPLICITES (meme matiere fiscale + theme complementaire,
    # ou procedures generales du meme theme) - avec un poids plus faible que
    # les renvois explicites, puisque ce ne sont que des rapprochements
    # deduits, pas des citations reelles du texte. Ignore silencieusement
    # si les enrichissements Phase 5 ne sont pas charges (repli Phase 1 seul).
    if len(candidats) < plafond:
        for p in pivots:
            meta = _METADONNEES_PAR_ARTICLE.get(p.article_id, {})
            liens = meta.get("liens_implicites", {})
            candidats_implicites = []
            for cibles in liens.get("meme_matiere_autres_themes", {}).values():
                candidats_implicites.extend(cibles)
            candidats_implicites.extend(liens.get("procedures_generales_meme_theme", []))
            for cible in candidats_implicites:
                if cible in seen:
                    continue
                seen.add(cible)
                candidats.append((0.40, "LIEN_IMPLICITE", cible))
                if len(candidats) >= plafond:
                    break
            if len(candidats) >= plafond:
                break
        candidats.sort(key=lambda c: -c[0])

    candidats = candidats[:plafond]

    linked = []
    for poids, type_relation, cible in candidats:
        cur = db.cursor()
        cur.execute(
            "SELECT text, livre_titre, chapitre_titre, section_titre FROM cgi_articles WHERE article_id = %s",
            (cible,),
        )
        row = cur.fetchone()
        if not row:
            continue  # l'article cible n'existe pas en base (embedding jamais genere)
        linked.append(
            RetrievedArticle(
                article_id=cible, text=row["text"],
                livre_titre=row["livre_titre"], chapitre_titre=row["chapitre_titre"],
                section_titre=row["section_titre"], role="lie",
                matiere_fiscale=_METADONNEES_PAR_ARTICLE.get(cible, {}).get("matiere_fiscale", ""),
                type_relation=type_relation, score=poids,
            )
        )
    return linked


def _bloc_exceptions(article_id):
    """Phase 5, Volet 2 : si l'article a des passages conditionnels isoles
    (toutefois, sauf, par derogation...), les met en evidence separement -
    pour que le LLM ne donne pas la regle generale en oubliant sa
    derogation. Retourne une chaine vide si aucun enrichissement charge ou
    aucune exception pour cet article (comportement inchange sinon)."""
    meta = _METADONNEES_PAR_ARTICLE.get(article_id)
    if not meta:
        return ""
    passages = meta.get("passages_conditionnels") or []
    if not passages:
        return ""
    lignes = ["  ⚠️ Exception(s)/dérogation(s) à ne pas oublier dans cet article :"]
    for p in passages[:3]:  # plafonne pour ne pas alourdir le prompt sur les articles tres charges
        lignes.append(f"  - {p['phrase']}")
    return "\n".join(lignes) + "\n"


def build_context_blocks(pivots, linked):
    """Étape 3 : construit le contexte envoyé au LLM avec des blocs distincts,
    pour que le modèle distingue la source principale des sources d'appui.

    Depuis cette mise a jour (point #29 du plan initial), les articles LIES
    sont repartis en blocs THEMATIQUES separes (SANCTIONS, EXCEPTIONS,
    PROCEDURES, DEFINITIONS, AUTRES RENVOIS) plutot qu'une seule liste
    plate - ca aide le LLM a structurer son raisonnement (ex. mentionner
    systematiquement une sanction applicable si un bloc SANCTIONS existe),
    au lieu de traiter tous les articles lies comme equivalents.

    Depuis la Phase 5, met egalement en evidence les exceptions/derogations
    deja isolees pour chaque article (Volet 2), pour reduire le risque
    d'une reponse qui donne la regle generale sans mentionner sa
    derogation."""
    CATEGORIES_RELATION = [
        ("SANCTIONS APPLICABLES", {"SANCTIONNE_PAR"}),
        ("EXCEPTIONS ET DÉROGATIONS", {"DEROGE_A", "SOUS_RESERVE_DE"}),
        ("DÉFINITIONS ET EXONÉRATIONS", {"DEFINI_PAR", "EXONERE_PAR"}),
        ("PROCÉDURES LIÉES (calcul, déclaration, recouvrement, contrôle)",
         {"CALCULE_SELON", "DECLARE_SELON", "RECOUVRE_SELON", "CONTROLE_SELON"}),
        ("ARTICLES TROUVÉS PAR RECHERCHE APPROFONDIE (2ᵉ niveau)", {"MULTI_HOP"}),
        ("AUTRES ARTICLES LIÉS", {"RENVOIE_A", "SOUMIS_A", "LIEN_IMPLICITE"}),
    ]

    blocks = ["ARTICLES PRINCIPAUX (correspondance directe à la question) :\n"]
    for a in pivots:
        blocks.append(f"[Art. {a.article_id}] ({a.chapitre_titre or a.livre_titre})\n{a.text}\n{_bloc_exceptions(a.article_id)}")

    for nom_bloc, types_inclus in CATEGORIES_RELATION:
        articles_du_bloc = [a for a in linked if a.type_relation in types_inclus]
        if not articles_du_bloc:
            continue
        blocks.append(f"\n{nom_bloc} :\n")
        for a in articles_du_bloc:
            etiquette_relation = f" — relation : {a.type_relation}" if a.type_relation and a.type_relation != "RENVOIE_A" else ""
            blocks.append(f"[Art. {a.article_id}] ({a.chapitre_titre or a.livre_titre}){etiquette_relation}\n{a.text}\n{_bloc_exceptions(a.article_id)}")
    return "\n".join(blocks)


RE_CITED_ARTICLE = re.compile(r"[Aa]rticle\s+(\d+)\s*(bis|ter|quater)?", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Phase 5, Volet 3 : fiches par impot, pour les questions LARGES ("explique-
# moi toute la taxe professionnelle") que la recherche standard (5 articles
# les plus proches) gere mal. Contexte STRICTEMENT plafonne : jamais question
# d'envoyer les 206 articles d'une grosse matiere comme "Domaines" - un
# article representatif par theme, les autres juste listes par numero.
# ---------------------------------------------------------------------------
MOTS_QUESTION_LARGE = [
    "explique", "expliquer", "expliques", "tout sur", "comment fonctionne",
    "vue d'ensemble", "en général", "de manière générale", "présente-moi",
    "parle-moi de", "qu'est-ce que",
]
MAX_ARTICLES_TEXTE_PAR_THEME = 1  # nb d'articles au texte complet recupere par theme


# ---------------------------------------------------------------------------
# Espace Procedures : declencheurs par mots-cles pour les fiches par ACTE
# et par PROCEDURE. Meme prudence que vocabulaire.py : des expressions
# suffisamment longues/specifiques pour eviter les faux positifs (jamais
# un seul mot court et ambigu).
# ---------------------------------------------------------------------------
DECLENCHEURS_ACTES = {
    "Créer son entreprise": [
        "créer mon entreprise", "créer une entreprise", "démarrer une activité",
        "nouvelle entreprise", "immatriculation fiscale", "immatriculer mon entreprise",
    ],
    "Gérer ses obligations courantes": [
        "mes obligations fiscales", "que dois-je déclarer", "obligations déclaratives",
    ],
    "Modifier son identification": [
        "changer d'adresse", "modifier mon régime", "changement d'activité",
        "changement de régime",
    ],
    "Rester en règle (ARF, régularisation, suspension, radiation)": [
        "attestation de régularité fiscale", "me régulariser", "régulariser ma situation",
        "radiation de mon entreprise", "suspension de mon activité",
    ],
    "Faire face à un contrôle fiscal": [
        "avis de contrôle", "je suis contrôlé", "vérification fiscale",
        "contrôle fiscal", "examen de ma situation fiscale",
    ],
    "Se protéger et anticiper": [
        "rescrit fiscal", "mes garanties en tant que contribuable", "doctrine fiscale",
    ],
    "Alléger sa charge fiscale légalement": [
        "réduire mes impôts légalement", "exonération fiscale", "déduction fiscale",
        "abattement fiscal",
    ],
    "Faire face aux conséquences (sanctions, recouvrement, contentieux)": [
        "quelles sanctions", "je conteste mon imposition", "réclamation fiscale",
        "avis de mise en recouvrement",
    ],
}

DECLENCHEURS_PROCEDURES = {
    "Procédures - Contrôle": ["contrôle fiscal", "vérification de comptabilité", "droit de visite"],
    "Procédures - Recouvrement": ["recouvrement de l'impôt", "poursuites fiscales", "saisie fiscale"],
    "Procédures - Sanctions": ["sanctions fiscales", "pénalités fiscales", "amendes fiscales"],
    "Procédures - Contentieux": ["contentieux fiscal", "réclamation fiscale"],
    "Procédures - Garanties du contribuable": ["garanties du contribuable", "rescrit fiscal", "doctrine fiscale"],
    "Procédures - Obligations déclaratives": ["obligations déclaratives"],
    "Procédures - Identification": ["numéro d'identification fiscale", "immatriculation fiscale"],
    "Procédures - Rectification": ["rectification contradictoire", "taxation d'office"],
    "Régimes spéciaux et incitations fiscales": [
        "régime fiscal minier", "régime fiscal pétrolier", "incitations fiscales",
        "régime fiscal des investissements",
    ],
}


def _detecter_par_declencheurs(question, declencheurs_par_cle):
    """Fonction generique : retourne la premiere cle dont au moins une
    expression declenchante apparait dans la question (insensible a la
    casse) - reutilisee pour les actes et les procedures."""
    question_lower = question.lower()
    for cle, expressions in declencheurs_par_cle.items():
        if any(expr in question_lower for expr in expressions):
            return cle
    return None


def detecter_acte_dans_question(question):
    return _detecter_par_declencheurs(question, DECLENCHEURS_ACTES)


def detecter_procedure_dans_question(question):
    return _detecter_par_declencheurs(question, DECLENCHEURS_PROCEDURES)


def detecter_matiere_dans_question(question):
    """Cherche si le nom d'une matière fiscale connue (Phase 1/5) apparaît
    dans la question - condition necessaire (mais pas suffisante seule)
    pour proposer une fiche plutot que la recherche standard."""
    question_lower = question.lower()
    for matiere in _FICHES_PAR_MATIERE:
        mots_matiere = [m for m in matiere.lower().split() if len(m) > 3]
        if mots_matiere and all(m in question_lower for m in mots_matiere):
            return matiere
    return None


def est_question_large(question):
    question_lower = question.lower()
    return any(m in question_lower for m in MOTS_QUESTION_LARGE)


def construire_contexte_fiche(matiere_fiscale, db, max_articles_par_theme=MAX_ARTICLES_TEXTE_PAR_THEME):
    """Construit un contexte de synthese a partir d'une fiche par impot.
    Pour chaque theme, recupere le texte d'un nombre PLAFONNE d'articles
    representatifs ; les autres articles du meme theme sont juste listes
    par numero, sans leur texte - pour ne jamais faire exploser la taille
    du prompt sur les grosses matieres (ex. Domaines, 206 articles).

    Retourne (contexte_texte, liste_des_ids_avec_texte_complet) ou None si
    aucune fiche n'existe pour cette matiere (Phase 5 non chargee)."""
    fiche = _FICHES_PAR_MATIERE.get(matiere_fiscale)
    if not fiche:
        return None

    blocs = [f"VUE D'ENSEMBLE — {matiere_fiscale} ({fiche['nombre_articles']} articles au total, question large détectée) :\n"]
    ids_avec_texte = []

    for section in fiche["sections"]:
        theme = section["theme"]
        ids = section["articles"]
        a_recuperer = ids[:max_articles_par_theme]
        reste = ids[max_articles_par_theme:]

        blocs.append(f"\n--- {theme} ---")
        for aid in a_recuperer:
            cur = db.cursor()
            cur.execute("SELECT text FROM cgi_articles WHERE article_id = %s", (aid,))
            row = cur.fetchone()
            if row:
                blocs.append(f"[Art. {aid}]\n{row['text']}")
                ids_avec_texte.append(aid)
        if reste:
            blocs.append(f"(Autres articles de ce thème, non détaillés ici : {', '.join(reste)})")

    if fiche["procedures_generales_associees"]:
        blocs.append(
            f"\nProcédures générales associées (sanctions, recouvrement) : "
            f"{', '.join(fiche['procedures_generales_associees'])}"
        )

    return "\n".join(blocs), ids_avec_texte


def construire_contexte_procedure(nom_procedure, db, max_articles_par_section=MAX_ARTICLES_TEXTE_PAR_THEME):
    """Equivalent de construire_contexte_fiche, mais pour les fiches par
    PROCEDURE (Espace Procedures, Groupe A + regimes speciaux). Structure
    legerement differente (cle "section" au lieu de "theme"), meme principe
    de plafond strict - jamais envoyer les 69 articles de "Recouvrement"
    d'un coup."""
    fiche = _FICHES_PAR_PROCEDURE.get(nom_procedure)
    if not fiche:
        return None

    blocs = [f"VUE D'ENSEMBLE — {nom_procedure} ({fiche['nombre_articles']} articles au total, question large détectée) :\n"]
    ids_avec_texte = []

    for section in fiche["sections"]:
        nom_section = section["section"]
        ids = section["articles"]
        a_recuperer = ids[:max_articles_par_section]
        reste = ids[max_articles_par_section:]

        blocs.append(f"\n--- {nom_section} ---")
        for aid in a_recuperer:
            cur = db.cursor()
            cur.execute("SELECT text FROM cgi_articles WHERE article_id = %s", (aid,))
            row = cur.fetchone()
            if row:
                blocs.append(f"[Art. {aid}]\n{row['text']}")
                ids_avec_texte.append(aid)
        if reste:
            blocs.append(f"(Autres articles de cette section, non détaillés ici : {', '.join(reste)})")

    return "\n".join(blocs), ids_avec_texte


def construire_contexte_acte(nom_acte, db, max_articles_par_source=1):
    """Equivalent de construire_contexte_fiche, mais pour les fiches par
    ACTE (parcours entreprise - "creer son entreprise", "faire face a un
    controle"...). Un acte croise volontairement PLUSIEURS SOURCES (ex.
    identification + choix du regime pour "creer son entreprise") - le
    plafond est donc applique PAR SOURCE, pas sur la liste fusionnee.

    Bug corrige : la version precedente plafonnait sur la liste fusionnee
    et triee, ce qui faisait systematiquement disparaitre certaines
    sources entieres (l'identification n'apparaissait jamais pour "Creer
    son entreprise", uniquement les regimes, qui triaient toujours en
    premier par pur hasard numerique) - contraire au but meme de ces
    fiches, qui est justement de montrer plusieurs sources ensemble."""
    fiche = _FICHES_PAR_ACTE.get(nom_acte)
    if not fiche:
        return None

    blocs = [
        f"VUE D'ENSEMBLE — Acte : {nom_acte} ({fiche['nombre_articles_total']} articles au total, "
        f"question large détectée) :\n{fiche['description']}\n"
    ]
    ids_avec_texte = []

    for source in fiche["sources"]:
        ids_source = source.get("articles", [])
        if not ids_source:
            continue
        libelle_source = source.get("libelle") or source["section"] or source["matiere_ou_categorie"]
        a_recuperer = ids_source[:max_articles_par_source]
        reste = [i for i in ids_source[max_articles_par_source:] if i not in ids_avec_texte]

        blocs.append(f"\n--- {libelle_source} ---")
        for aid in a_recuperer:
            if aid in ids_avec_texte:
                continue
            cur = db.cursor()
            cur.execute("SELECT text FROM cgi_articles WHERE article_id = %s", (aid,))
            row = cur.fetchone()
            if row:
                blocs.append(f"[Art. {aid}]\n{row['text']}")
                ids_avec_texte.append(aid)
        if reste:
            blocs.append(f"(Autres articles de cette source, non détaillés ici : {', '.join(reste)})")

    return "\n".join(blocs), ids_avec_texte


def check_no_hallucinated_articles(answer_text, context_article_ids):
    """Garde-fou anti-hallucination : vérifie que chaque numéro d'article cité
    dans la réponse du LLM figure bien parmi les articles réellement envoyés
    en contexte. Retourne la liste des numéros suspects (à ne jamais afficher
    tels quels, ou à faire vérifier avant affichage)."""
    cited = set()
    for m in RE_CITED_ARTICLE.finditer(answer_text):
        num = m.group(1)
        suf = (m.group(2) or "").lower()
        cited.add(f"{num}{suf}")
        cited.add(num)  # tolère la citation sans suffixe

    context_set = set(context_article_ids)
    suspect = sorted({c for c in cited if c not in context_set}, key=lambda x: int(re.sub(r"\D", "", x)))
    return suspect


def embed_question(gemini_client, texte_question):
    """Transforme une QUESTION en vecteur - utilise task_type='RETRIEVAL_QUERY',
    different de 'RETRIEVAL_DOCUMENT' utilise pour indexer les articles
    (voir generer_embeddings.py). Gemini optimise differemment les deux
    cas : un vecteur de question et un vecteur de document ne sont pas
    traites de facon symetrique en interne, meme si le modele est le meme."""
    resultat = gemini_client.models.embed_content(
        model="gemini-embedding-001",
        contents=texte_question,
        config=genai_types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=1536,  # doit correspondre a schema.sql
        ),
    )
    return resultat.embeddings[0].values


def call_gemini_llm(gemini_client, prompt, model="gemini-3.6-flash", max_output_tokens=1500, timeout_secondes=35):
    """Appelle Gemini pour la generation finale - SANS File Search, puisque
    le contexte pertinent est deja construit par notre propre recherche
    (search_pivot_articles + expand_via_refs). C'est ce qui rend cet appel
    beaucoup plus simple et rapide que l'ancien chemin File Search."""
    response = gemini_client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            max_output_tokens=max_output_tokens,
            http_options=genai_types.HttpOptions(timeout=timeout_secondes * 1000),
        ),
    )
    return getattr(response, "text", "") or ""


def normaliser_question(gemini_client, question_brute, model="gemini-3.6-flash", timeout_secondes=15):
    """Point #12 du plan initial : transforme la question brute en une
    liste de mots-cles structures (type de contribuable, operation,
    montant, impot probable, concepts fiscaux) via UN APPEL GEMINI
    SUPPLEMENTAIRE, pour guider une recherche plus intelligente que le
    texte brut seul.

    COUTE DU QUOTA - desactive par defaut (voir NORMALISATION_ACTIVE
    dans engine.py), a n'activer qu'une fois le paiement regle. En cas
    d'echec, de timeout ou de reponse vide, retourne la question brute
    INCHANGEE - ne bloque jamais la recherche standard, echoue toujours
    de facon silencieuse et sans risque."""
    prompt = (
        "Tu prepares une question fiscale pour une recherche documentaire "
        "dans le Code Général des Impôts du Niger. À partir de la question "
        "suivante, identifie en quelques mots-clés : le type de "
        "contribuable si mentionné, l'opération concernée (achat, vente, "
        "salaire, loyer, importation...), le montant si mentionné, "
        "l'impôt ou la taxe probablement concerné, et les concepts "
        "fiscaux clés. Réponds UNIQUEMENT avec ces mots-clés séparés par "
        "des espaces, sur une seule ligne, sans phrase ni explication.\n\n"
        f"Question : {question_brute}"
    )
    try:
        mots_cles = call_gemini_llm(
            gemini_client, prompt, model=model,
            max_output_tokens=100, timeout_secondes=timeout_secondes,
        ).strip()
        if mots_cles:
            print(f"[Fisca AI][RAG][Normalisation] Question enrichie : {mots_cles!r}")
            return f"{question_brute} {mots_cles}"
    except Exception as e:
        print(f"[Fisca AI][RAG][Normalisation] Échec ({type(e).__name__}: {e}) — question brute utilisée telle quelle.")
    return question_brute


def reranker_candidats(gemini_client, question_brute, candidats, model="gemini-3.6-flash", top_k_final=5, timeout_secondes=15):
    """Point #15 du plan initial : apres une recherche ELARGIE (10-15
    candidats au lieu de 5), UN APPEL GEMINI SUPPLEMENTAIRE classe chaque
    article candidat comme INDISPENSABLE / UTILE / HORS-SUJET par rapport
    a la question, et ne garde que les meilleurs - rattrape les cas ou la
    recherche automatique (vectorielle + mots-cles) se trompe ou laisse
    passer du bruit.

    COUTE UN APPEL GEMINI SUPPLEMENTAIRE - desactive par defaut (voir
    RERANKER_ACTIVE dans engine.py). En cas d'echec, de timeout ou de
    reponse illisible, retourne les candidats dans leur ORDRE INITIAL,
    simplement tronques a top_k_final - ne bloque jamais, ne fait jamais
    moins bien que l'absence de reranker."""
    if not candidats:
        return candidats

    liste_candidats = "\n".join(
        f"{i + 1}. [Art. {a.article_id}] {a.text[:150]}"
        for i, a in enumerate(candidats)
    )
    prompt = (
        "Voici une question fiscale et une liste d'articles candidats "
        "trouvés par une recherche automatique dans le Code Général des "
        "Impôts du Niger. Pour CHAQUE article, indique s'il est "
        "INDISPENSABLE, UTILE, ou HORS-SUJET pour répondre précisément à "
        "la question. Réponds UNIQUEMENT avec une ligne par article, "
        "format exact : \"1: INDISPENSABLE\" (le numéro, deux-points, "
        "puis le classement en majuscules). Aucune autre phrase.\n\n"
        f"Question : {question_brute}\n\n"
        f"Articles candidats :\n{liste_candidats}"
    )
    try:
        reponse = call_gemini_llm(
            gemini_client, prompt, model=model,
            max_output_tokens=300, timeout_secondes=timeout_secondes,
        )
        classement = {}
        for ligne in reponse.strip().split("\n"):
            m = re.match(r"\s*(\d+)\s*[:\-]\s*(INDISPENSABLE|UTILE|HORS-SUJET|HORS SUJET)", ligne, re.IGNORECASE)
            if m:
                idx = int(m.group(1)) - 1
                niveau = m.group(2).upper().replace(" ", "-")
                if 0 <= idx < len(candidats):
                    classement[idx] = niveau

        indispensables = [candidats[i] for i in range(len(candidats)) if classement.get(i) == "INDISPENSABLE"]
        utiles = [candidats[i] for i in range(len(candidats)) if classement.get(i) == "UTILE"]
        resultat = (indispensables + utiles)[:top_k_final]
        if resultat:
            print(
                f"[Fisca AI][RAG][Reranker] {len(indispensables)} indispensable(s), "
                f"{len(utiles)} utile(s) sur {len(candidats)} candidats analysés."
            )
            return resultat
    except Exception as e:
        print(f"[Fisca AI][RAG][Reranker] Échec ({type(e).__name__}: {e}) — ordre initial conservé.")
    return candidats[:top_k_final]


def construire_dossier_fiscal_virtuel(gemini_client, question_brute, model="gemini-3.6-flash", timeout_secondes=15):
    """Point #24 du plan initial : reconstruit, via UN APPEL GEMINI
    SUPPLEMENTAIRE, un "dossier fiscal virtuel" STRUCTURE (champs nommes)
    a partir de la question - contribuable, activite, operation, impot
    probable, regime, periode, montant, obligation, difficulte, sanction
    eventuelle. Version plus poussee de normaliser_question (#12), qui ne
    produisait qu'un sac de mots-cles plat : ici chaque information est
    identifiee individuellement, exploitable pour un affichage de
    confirmation a l'utilisateur ou une recherche encore plus ciblee.

    COUTE UN APPEL GEMINI SUPPLEMENTAIRE - desactive par defaut, reserve
    en pratique aux plans Expert (cout par question plus eleve). Retourne
    un dict, potentiellement vide en cas d'echec - ne bloque jamais."""
    prompt = (
        "Tu analyses une question fiscale posée au Niger. Extrais les "
        "informations suivantes si elles sont mentionnées ou clairement "
        "déductibles de la question ; laisse le champ vide (rien après "
        "les deux-points) si l'information n'est pas présente. Réponds "
        "UNIQUEMENT dans ce format exact, une ligne par champ, sans "
        "phrase ni explication :\n"
        "CONTRIBUABLE:\n"
        "ACTIVITE:\n"
        "OPERATION:\n"
        "IMPOT_PROBABLE:\n"
        "REGIME:\n"
        "PERIODE:\n"
        "MONTANT:\n"
        "OBLIGATION:\n"
        "DIFFICULTE:\n"
        "SANCTION_EVENTUELLE:\n\n"
        f"Question : {question_brute}"
    )
    dossier = {}
    try:
        reponse = call_gemini_llm(
            gemini_client, prompt, model=model,
            max_output_tokens=200, timeout_secondes=timeout_secondes,
        )
        for ligne in reponse.strip().split("\n"):
            if ":" in ligne:
                cle, _, valeur = ligne.partition(":")
                valeur = valeur.strip()
                if valeur:
                    dossier[cle.strip().upper()] = valeur
        if dossier:
            print(f"[Fisca AI][RAG][DossierVirtuel] Champs extraits : {list(dossier.keys())}")
    except Exception as e:
        print(f"[Fisca AI][RAG][DossierVirtuel] Échec ({type(e).__name__}: {e}) — dossier vide, question brute utilisée seule.")
    return dossier


def dossier_vers_texte_recherche(question_brute, dossier):
    """Convertit un dossier fiscal virtuel (dict, potentiellement vide)
    en texte enrichi pour la recherche - simple concatenation des
    valeurs non vides a la suite de la question brute."""
    if not dossier:
        return question_brute
    valeurs = " ".join(dossier.values())
    return f"{question_brute} {valeurs}"


def rechercher_multi_hop(gemini_client, db, question_brute, pivots, linked, model="gemini-3.6-flash", max_articles_supplementaires=3, timeout_secondes=15):
    """Point #25 du plan initial : recherche multi-etapes. Apres le
    premier niveau de recherche (pivots + articles lies), UN APPEL GEMINI
    SUPPLEMENTAIRE juge si les articles deja trouves mentionnent un AUTRE
    numero d'article precis, indispensable mais pas encore recupere - et
    si oui, va chercher CE deuxieme niveau precis, plutot que d'elargir
    aveuglement la recherche a tout le CGI ("suivre deux ou trois niveaux
    de relations sans rechercher tout le CGI", selon le plan initial).

    COUTE UN APPEL GEMINI SUPPLEMENTAIRE - desactive par defaut, reserve
    en pratique aux plans Expert. En cas d'echec ou si aucun besoin
    identifie, retourne une liste vide - ne degrade jamais le resultat
    deja obtenu au premier niveau."""
    tous_ids_actuels = [a.article_id for a in pivots + linked]
    contexte_actuel = "\n".join(f"[Art. {a.article_id}] {a.text[:200]}" for a in pivots + linked)

    prompt = (
        "Voici une question fiscale et les articles du Code Général des "
        "Impôts du Niger déjà trouvés pour y répondre. Ces articles "
        "mentionnent-ils un AUTRE numéro d'article précis, indispensable "
        "pour compléter la réponse, mais qui n'est PAS déjà dans la "
        "liste ci-dessous ? Si oui, réponds UNIQUEMENT avec ce(s) "
        "numéro(s) d'article séparés par des virgules (maximum 3). Si "
        "aucun article supplémentaire n'est nécessaire, réponds "
        "UNIQUEMENT \"AUCUN\".\n\n"
        f"Articles déjà trouvés (numéros : {', '.join(tous_ids_actuels)}) :\n{contexte_actuel}\n\n"
        f"Question : {question_brute}"
    )
    try:
        reponse = call_gemini_llm(
            gemini_client, prompt, model=model,
            max_output_tokens=50, timeout_secondes=timeout_secondes,
        ).strip()
        if not reponse or reponse.upper().startswith("AUCUN"):
            print("[Fisca AI][RAG][MultiHop] Aucun second niveau nécessaire.")
            return []

        numeros_demandes = [n.strip() for n in re.split(r"[,\s]+", reponse) if n.strip()]
        numeros_demandes = [n for n in numeros_demandes if n not in tous_ids_actuels][:max_articles_supplementaires]

        supplementaires = []
        for numero in numeros_demandes:
            cur = db.cursor()
            cur.execute(
                "SELECT text, livre_titre, chapitre_titre, section_titre FROM cgi_articles WHERE article_id = %s",
                (numero,),
            )
            row = cur.fetchone()
            if row:
                supplementaires.append(RetrievedArticle(
                    article_id=numero, text=row["text"],
                    livre_titre=row["livre_titre"], chapitre_titre=row["chapitre_titre"],
                    section_titre=row["section_titre"], role="lie",
                    matiere_fiscale=_METADONNEES_PAR_ARTICLE.get(numero, {}).get("matiere_fiscale", ""),
                    type_relation="MULTI_HOP",
                ))
        if supplementaires:
            print(
                f"[Fisca AI][RAG][MultiHop] {len(supplementaires)} article(s) "
                f"supplémentaire(s) récupéré(s) : {[a.article_id for a in supplementaires]}"
            )
        return supplementaires
    except Exception as e:
        print(f"[Fisca AI][RAG][MultiHop] Échec ({type(e).__name__}: {e}) — pas d'article supplémentaire.")
        return []


def answer_query(db, user_question, embed_fn, llm_fn):
    """Orchestration complète (à adapter selon le client LLM utilisé).
    Utilise desormais la recherche HYBRIDE (vectorielle + mots-cles) au
    lieu du vectoriel seul, et l'expansion ponderee par type de relation."""
    q_emb = embed_fn(user_question)

    pivots = recherche_hybride(db, q_emb, user_question)
    linked = expand_via_refs(db, pivots)

    context = build_context_blocks(pivots, linked)
    all_ids = [a.article_id for a in pivots + linked]

    prompt = (
        "Tu es un assistant fiscal spécialisé sur le Code Général des Impôts "
        "du Niger (CGI 2026). Réponds UNIQUEMENT à partir des articles fournis "
        "ci-dessous. Cite systématiquement le ou les numéros d'article sur "
        "lesquels tu bases ta réponse. Si les articles fournis ne permettent "
        "pas de répondre avec certitude, dis-le explicitement plutôt que "
        "d'improviser.\n\n"
        f"{context}\n\nQuestion : {user_question}"
    )

    answer = llm_fn(prompt)

    suspects = check_no_hallucinated_articles(answer, all_ids)
    if suspects:
        answer += (
            "\n\n⚠️ Vérification automatique : les articles "
            f"{', '.join(suspects)} cités ci-dessus n'étaient pas dans les "
            "sources consultées pour cette réponse — à vérifier manuellement."
        )

    return {
        "answer": answer,
        "sources": all_ids,
        "suspects": suspects,
    }

