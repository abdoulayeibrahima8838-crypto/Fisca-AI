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


TOP_K_VECTOR = 5          # nb d'articles récupérés par similarité vectorielle
TOP_K_MOTS_CLES = 5       # nb d'articles récupérés par recherche mots-clés
MAX_EXPANSION_PER_ARTICLE = 4  # nb max de renvois ajoutés par article pivot
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


_articles_enrichis = _charger_json_optionnel("cgi2026_articles_enrichis.json")
_METADONNEES_PAR_ARTICLE = (
    {a["article_id"]: a for a in _articles_enrichis} if _articles_enrichis else {}
)

_refs_enrichis = _charger_json_optionnel("cgi2026_refs_enrichis.json")
_POIDS_RELATIONS = (
    {(r["source_article_id"], r["target_article_id"]): r for r in _refs_enrichis}
    if _refs_enrichis else {}
)

print(
    f"[Fisca AI][RAG] Enrichissements chargés : "
    f"{len(_METADONNEES_PAR_ARTICLE)} article(s) avec métadonnées Phase 1, "
    f"{len(_POIDS_RELATIONS)} relation(s) qualifiées Phase 2."
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
    apparait ; les scores sont ensuite additionnes et retries."""
    K_RRF = 60

    resultats_vecteur = search_pivot_articles(db, query_embedding, top_k=top_k * 2)
    resultats_mots_cles = search_keywords(db, question, top_k=top_k * 2)

    articles_par_id = {}
    scores = {}

    for rang, a in enumerate(resultats_vecteur, start=1):
        articles_par_id[a.article_id] = a
        scores[a.article_id] = scores.get(a.article_id, 0.0) + 1.0 / (K_RRF + rang)

    for rang, a in enumerate(resultats_mots_cles, start=1):
        articles_par_id.setdefault(a.article_id, a)
        scores[a.article_id] = scores.get(a.article_id, 0.0) + 1.0 / (K_RRF + rang)

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
    candidats = candidats[: max_per_article * max(len(pivots), 1)]

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


def build_context_blocks(pivots, linked):
    """Étape 3 : construit le contexte envoyé au LLM avec des blocs distincts,
    pour que le modèle distingue la source principale des sources d'appui.
    Les articles liés affichent leur type de relation (SANCTIONNE_PAR,
    DEFINI_PAR...) quand connu - ça aide le LLM à comprendre POURQUOI cet
    article est pertinent, pas juste QU'IL l'est."""
    blocks = ["ARTICLES PRINCIPAUX (correspondance directe à la question) :\n"]
    for a in pivots:
        blocks.append(f"[Art. {a.article_id}] ({a.chapitre_titre or a.livre_titre})\n{a.text}\n")
    if linked:
        blocks.append("\nARTICLES LIÉS (référencés explicitement par les articles ci-dessus) :\n")
        for a in linked:
            etiquette_relation = f" — relation : {a.type_relation}" if a.type_relation and a.type_relation != "RENVOIE_A" else ""
            blocks.append(f"[Art. {a.article_id}] ({a.chapitre_titre or a.livre_titre}){etiquette_relation}\n{a.text}\n")
    return "\n".join(blocks)


RE_CITED_ARTICLE = re.compile(r"[Aa]rticle\s+(\d+)\s*(bis|ter|quater)?", re.IGNORECASE)


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
