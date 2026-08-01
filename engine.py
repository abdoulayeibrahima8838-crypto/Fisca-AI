# -*- coding: utf-8 -*-
"""
Moteur de comprehension de Fisca AI.

Architecture "filet de securite" :
1) On tente d'abord une reponse via l'API OpenAI (si une cle est configuree
   ET que l'appel reussit) - c'est le moteur intelligent, capable de
   comprendre n'importe quelle formulation et de chercher dans tout le
   CGI, pas seulement les questions pre-ecrites.
2) Si OpenAI n'est pas configure, ou si l'appel echoue pour QUELQUE
   RAISON QUE CE SOIT (carte bancaire refusee, credit epuise, panne
   OpenAI, pas de connexion, delai depasse...), on bascule
   AUTOMATIQUEMENT et SILENCIEUSEMENT sur le moteur local base sur
   mots-cles (cache_data.py). L'utilisateur recoit toujours une reponse,
   jamais une page d'erreur.

Tant que OPENAI_API_KEY et OPENAI_VECTOR_STORE_ID ne sont pas configures
sur Render, ce fichier se comporte EXACTEMENT comme avant : 100% moteur
local, aucun risque, aucun cout.
"""
import os
import re
import unicodedata
import difflib

from cache_data import QA_LIBRARY

# ---------------------------------------------------------------------------
# Partie IA (OpenAI) - optionnelle, activee seulement si configuree
# ---------------------------------------------------------------------------
try:
    from openai import OpenAI
    _client = OpenAI() if os.environ.get("OPENAI_API_KEY") else None
except Exception:
    # Le paquet "openai" n'est pas installe, ou la cle est absente/invalide.
    # Ce n'est jamais bloquant : on continue avec le moteur local.
    _client = None

OPENAI_VECTOR_STORE_ID = os.environ.get("OPENAI_VECTOR_STORE_ID")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT_SECONDS = 12

SYSTEM_PROMPT = (
    "Tu es Fisca AI, assistant documentaire specialise dans la fiscalite "
    "nigerienne. Tu reponds UNIQUEMENT a partir des documents officiels "
    "fournis (Code General des Impots 2026 et textes reglementaires). "
    "Si l'information ne figure pas dans ces documents, dis-le "
    "clairement : 'Aucune information suffisamment precise n'a ete "
    "trouvee dans les documents actuellement integres.' N'invente jamais "
    "un article, un taux, un seuil ou une sanction. Cite toujours "
    "l'article ou le document exact sur lequel repose ta reponse. "
    "Reponds en francais, simplement, pour un contribuable qui n'est pas "
    "juriste."
)


def repondre_ia(question_brute):
    """Tente une reponse via OpenAI (File Search sur les documents
    officiels). Retourne None si indisponible pour une raison quelconque -
    c'est le signal pour l'appelant de basculer sur le moteur local."""
    if not _client or not OPENAI_VECTOR_STORE_ID:
        return None
    try:
        response = _client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question_brute},
            ],
            tools=[{"type": "file_search", "vector_store_ids": [OPENAI_VECTOR_STORE_ID]}],
            timeout=OPENAI_TIMEOUT_SECONDS,
        )
        texte = getattr(response, "output_text", "") or ""
        if not texte.strip():
            return None
        return {
            "niveau": 1,
            "reponse": texte.strip(),
            "source": "Reponse generee par l'IA a partir des documents officiels charges",
            "verified": None,  # ni "test" ni verifie a la main : generee dynamiquement
            "question_comprise": question_brute,
            "moteur": "openai",
        }
    except Exception as e:
        # Carte refusee, credit epuise, panne OpenAI, pas de reseau,
        # delai depasse... Peu importe la cause : on ne casse jamais
        # l'experience utilisateur. On journalise pour toi (visible dans
        # les logs Render) et on bascule sur le moteur local.
        print(f"[Fisca AI] Echec de l'appel OpenAI ({type(e).__name__}: {e}) - bascule sur le moteur local.")
        return None


# ---------------------------------------------------------------------------
# Partie moteur local (toujours disponible, jamais de dependance externe)
# ---------------------------------------------------------------------------
def normaliser(texte):
    """Minuscule, sans accents, sans ponctuation - pour comparer sans se
    faire piquer par une majuscule ou un accent oublie."""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"[^\w\s]", " ", texte)
    texte = re.sub(r"\s+", " ", texte)
    return texte


def _score_entree(mots_question, entree):
    """Calcule un score de correspondance en tolerant les fautes de
    frappe (comparaison de similarite), pas seulement une correspondance
    exacte de mots-cles."""
    score = 0
    for mot_cle in entree["keywords"]:
        mot_cle_norm = normaliser(mot_cle)
        if mot_cle_norm in mots_question:
            score += 2
            continue
        for mot_q in mots_question.split():
            for mot_k in mot_cle_norm.split():
                if len(mot_k) < 4:
                    continue
                ratio = difflib.SequenceMatcher(None, mot_q, mot_k).ratio()
                if ratio >= 0.8:
                    score += 1
    return score


def repondre_locale(question_brute):
    """Moteur de secours base sur mots-cles. Toujours disponible, ne
    depend d'aucun service externe."""
    mots_question = normaliser(question_brute)

    meilleur = None
    meilleur_score = 0
    for entree in QA_LIBRARY:
        score = _score_entree(mots_question, entree)
        if score > meilleur_score:
            meilleur_score = score
            meilleur = entree

    if meilleur and meilleur_score >= 2:
        return {
            "niveau": 1,
            "reponse": meilleur["answer"],
            "source": meilleur["source"],
            "verified": meilleur["verified"],
            "question_comprise": meilleur["question_type"],
            "moteur": "local",
        }

    return {
        "niveau": 3,
        "reponse": (
            "Aucune information suffisamment precise n'a ete trouvee dans les "
            "documents actuellement integres. Essayez de reformuler, ou "
            "precisez votre question."
        ),
        "source": None,
        "verified": None,
        "question_comprise": question_brute,
        "moteur": "local",
    }


# ---------------------------------------------------------------------------
# Point d'entree unique utilise par app.py
# ---------------------------------------------------------------------------
def repondre(question_brute):
    """Essaie l'IA si configuree ; bascule automatiquement sur le moteur
    local en cas d'absence de configuration OU d'echec de l'appel."""
    resultat_ia = repondre_ia(question_brute)
    if resultat_ia is not None:
        return resultat_ia
    return repondre_locale(question_brute)
