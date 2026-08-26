# -*- coding: utf-8 -*-
"""
moteur_local_enrichi.py — Point #35 du plan initial : renforce le moteur
local suspendu (qui ne connaissait que ~40 entrees ecrites a la main dans
cache_data.py) en lui donnant acces a la meme richesse de donnees que le
RAG : les 1096 articles du CGI 2026, le vocabulaire naturel (sigles,
synonymes), et les matieres fiscales deja classees.

AUCUN APPEL IA - recherche par mots-cles pure, calculee localement. C'est
le filet de securite de tout dernier recours : si le RAG (base de donnees
+ Gemini) est indisponible, ce moteur reste utilisable meme hors ligne
par rapport a l'API, puisqu'il ne depend que d'un fichier local.

Contrairement a l'ancien moteur local (suspendu car parfois trop confiant
sur des reponses fausses), celui-ci ne REDIGE jamais de reponse en langage
naturel - il retourne toujours le TEXTE BRUT du ou des meilleurs articles
trouves, jamais une reformulation qui pourrait deformer le sens.

Usage :
    from moteur_local_enrichi import repondre_locale_enrichie
    resultat = repondre_locale_enrichie("Quel est le taux de la TVA ?")
"""
import json
import os
import re
from collections import Counter

try:
    from vocabulaire import elargir_question
except ImportError:
    def elargir_question(q):
        return q

_DOSSIER_MODULE = os.path.dirname(os.path.abspath(__file__))
_CHEMIN_ARTICLES = os.path.join(_DOSSIER_MODULE, "cgi2026_articles_complet.json")

MOTS_VIDES = {
    "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux", "et", "ou",
    "est", "sont", "que", "qui", "quoi", "dans", "sur", "pour", "par", "avec",
    "ce", "cette", "ces", "son", "sa", "ses", "leur", "leurs", "je", "tu", "il",
    "elle", "nous", "vous", "ils", "elles", "mon", "ma", "mes", "ton", "ta",
    "tes", "notre", "votre", "pas", "plus", "moins", "peut", "doit", "être",
    "avoir", "fait", "faire", "comment", "quel", "quelle", "quels", "quelles",
    "art", "code", "présent", "présente", "ainsi", "donc", "alors", "aussi",
}

try:
    with open(_CHEMIN_ARTICLES, encoding="utf-8") as f:
        _ARTICLES = json.load(f)
    print(f"[Fisca AI][MoteurLocal] {len(_ARTICLES)} articles chargés en mémoire (recherche 100% locale, sans IA).")
except (FileNotFoundError, json.JSONDecodeError) as e:
    _ARTICLES = []
    print(f"[Fisca AI][MoteurLocal] Fichier articles non chargé ({type(e).__name__}) — moteur local enrichi indisponible.")

# Frequence de chaque mot significatif a travers tout le corpus - permet
# de ponderer les mots RARES (plus distinctifs) davantage que les mots
# tres frequents (moins utiles pour distinguer un article d'un autre).
_FREQUENCE_MOTS = Counter()
for _a in _ARTICLES:
    _mots_uniques = set(re.findall(r"[a-zàâäéèêëïîôöùûüç]{4,}", _a["text"].lower()))
    _FREQUENCE_MOTS.update(_mots_uniques)


def _extraire_mots_significatifs(texte):
    mots = re.findall(r"[a-zàâäéèêëïîôöùûüç]{4,}", texte.lower())
    return [m for m in mots if m not in MOTS_VIDES]


MOTS_DECLENCHANT_THEME = {
    "Taux": {"taux", "pourcentage", "pourcent"},
    "Base d'imposition": {"base", "assiette"},
    "Exonérations": {"exonéré", "exonération", "exonérée", "exonérés"},
    "Sanctions": {"sanction", "amende", "pénalité"},
    "Déclaration et paiement": {"déclarer", "déclaration", "payer", "paiement"},
}
BONUS_THEME = 3.0  # fort : le theme Phase 5 est un signal bien plus fiable
                    # qu'une simple co-occurrence de mots pour ce type de question


def _detecter_matiere_probable(mots_question, question_normalisee):
    """Version simplifiee (sans dependance a rag.py) de la detection de
    matiere fiscale : la matiere gagne si tous ses mots significatifs
    apparaissent dans la question."""
    matieres = {a["matiere_fiscale"] for a in _ARTICLES}
    for matiere in matieres:
        mots_matiere = [m for m in matiere.lower().split() if len(m) > 3]
        if mots_matiere and all(m in question_normalisee for m in mots_matiere):
            return matiere
    return None


def _score_article(mots_question, article, matiere_probable, theme_recherche):
    mots_article = set(_extraire_mots_significatifs(article["text"]))
    score = 0.0
    for mot in mots_question:
        if mot in mots_article:
            frequence = _FREQUENCE_MOTS.get(mot, 1)
            # Poids inverse de la frequence : un mot rare compte plus
            # qu'un mot tres commun dans tout le corpus (esprit IDF).
            score += 1.0 / frequence

    # Bonus structurel (remplace l'ancien bonus par simple presence de
    # valeur extraite, trop peu discriminant - voir Art 94 vs Art 58) :
    # utilise directement le THEME Phase 5 de l'article. Un article dont
    # le theme correspond exactement a ce que la question demande (ex.
    # "Taux" quand la question demande un taux) est un signal bien plus
    # fort et fiable qu'une co-occurrence de mots.
    theme_article = (article.get("themes") or {}).get("principal")
    if theme_recherche and theme_article == theme_recherche:
        score += BONUS_THEME
        # Bonus supplementaire si en plus la matiere fiscale correspond
        # a celle detectee dans la question (ex. "Taux" ET "Impot sur les
        # societes" ensemble = tres probablement le bon article).
        if matiere_probable and article["matiere_fiscale"] == matiere_probable:
            score += BONUS_THEME

    return score


def repondre_locale_enrichie(question, top_k=3):
    """Cherche, par simple correspondance de mots-cles (aucune IA), les
    articles les plus pertinents pour la question. Retourne le texte BRUT
    des meilleurs articles trouves - jamais une reformulation, pour rester
    toujours honnete meme sans verification par un LLM.

    Retourne None si aucun article pertinent n'a ete trouve (le score le
    plus haut est nul), ou si le fichier de donnees n'a pas pu etre
    charge - dans ce cas, l'appelant doit basculer sur un message
    d'indisponibilite plutot que d'inventer une reponse."""
    if not _ARTICLES:
        return None

    question_elargie = elargir_question(question)
    question_normalisee = question_elargie.lower()
    mots_question = set(_extraire_mots_significatifs(question_elargie))
    if not mots_question:
        return None

    matiere_probable = _detecter_matiere_probable(mots_question, question_normalisee)
    theme_recherche = None
    for theme, mots_declencheurs in MOTS_DECLENCHANT_THEME.items():
        if mots_question & mots_declencheurs:
            theme_recherche = theme
            break

    scores = []
    for article in _ARTICLES:
        s = _score_article(mots_question, article, matiere_probable, theme_recherche)
        if s > 0:
            scores.append((s, article))

    if not scores:
        return None

    scores.sort(key=lambda x: -x[0])
    meilleurs = [a for _, a in scores[:top_k]]

    lignes = [
        "Le moteur de recherche principal n'est pas disponible pour le moment. "
        "Voici, à titre indicatif, le ou les articles du CGI 2026 qui semblent "
        "les plus proches de votre question :\n"
    ]
    for a in meilleurs:
        lignes.append(f"\nArticle {a['article_id']} — {a['text']}")

    print(
        f"[Fisca AI][MoteurLocal] {len(meilleurs)} article(s) trouvé(s) "
        f"(meilleur score={scores[0][0]:.2f}) : {[a['article_id'] for a in meilleurs]}"
    )

    return {
        "niveau": 3,
        "reponse": "\n".join(lignes),
        "source": f"Recherche locale (sans IA) — articles {', '.join(a['article_id'] for a in meilleurs)}",
        "verified": True,
        "question_comprise": question,
        "moteur": "local_enrichi",
    }
