# -*- coding: utf-8 -*-
"""
Moteur de comprehension de Fisca AI.

Architecture "filet de securite" :
1) On tente d'abord une reponse via l'API OpenAI (si configuree et si
   l'appel reussit).
2) Sinon (ou en cas d'echec), on bascule automatiquement et
   silencieusement sur le moteur local base sur mots-cles ci-dessous.

MOTEUR LOCAL - v2 (corrige un bug de double-comptage) :
La version precedente comparait chaque mot de la question a CHAQUE
phrase-mot-cle d'une entree separement, et additionnait les points a
chaque fois. Consequence : une entree avec plusieurs mots-cles contenant
tous le mot "machine" (ex. "vendre ma machine", "revendre ma machine",
"ceder ma machine") accumulait des points en double/triple pour ce seul
mot, et pouvait l'emporter a tort face a une entree plus pertinente mais
avec moins de repetitions.

La v2 corrige ca : chaque mot de la question n'est compte QU'UNE SEULE
FOIS par entree (on garde sa MEILLEURE correspondance dans le
vocabulaire de l'entree, pas la somme de toutes ses correspondances).
Elle ajoute aussi une ponderation inspiree du TF-IDF : les mots qui
apparaissent dans presque toutes les entrees (ex. "facture", "certifie",
"secef") comptent moins qu'un mot distinctif (ex. "panne", "revendre",
"nif") qui n'apparait que dans une ou deux entrees.
"""
import os
import re
import math
import unicodedata
import difflib
from collections import Counter

from cache_data import QA_LIBRARY

# ---------------------------------------------------------------------------
# Partie IA (OpenAI) - optionnelle, activee seulement si configuree
# ---------------------------------------------------------------------------
try:
    from openai import OpenAI
    _client = OpenAI() if os.environ.get("OPENAI_API_KEY") else None
except Exception:
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
    if not _client or not OPENAI_VECTOR_STORE_ID:
        return None
    try:
        response = _client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question_brute},
            ],
            tools=[{"type": "file_search", "vector_store_ids": [OPENAI_VECTOR_STORE_ID], "max_num_results": 4}],
            timeout=OPENAI_TIMEOUT_SECONDS,
        )
        texte = getattr(response, "output_text", "") or ""
        if not texte.strip():
            return None
        return {
            "niveau": 1,
            "reponse": texte.strip(),
            "source": "Reponse generee par l'IA a partir des documents officiels charges",
            "verified": None,
            "question_comprise": question_brute,
            "moteur": "openai",
        }
    except Exception as e:
        print(f"[Fisca AI] Echec de l'appel OpenAI ({type(e).__name__}: {e}) - bascule sur le moteur local.")
        return None


# ---------------------------------------------------------------------------
# Moteur local v2
# ---------------------------------------------------------------------------
MOTS_VIDES = {
    "le", "la", "les", "de", "des", "du", "un", "une", "est", "ce", "cette",
    "que", "qui", "quel", "quelle", "quels", "quelles", "a", "et",
    "en", "pour", "sur", "au", "aux", "par", "avec", "dans", "je", "tu",
    "il", "elle", "vous", "nous", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "si", "ne", "pas", "on", "se", "sont", "ai", "as",
    "faire", "fait", "etre", "dois", "doit", "peut", "peux", "comment",
}


def normaliser(texte):
    """Minuscule, sans accents, sans ponctuation."""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"[^\w\s]", " ", texte)
    texte = re.sub(r"\s+", " ", texte)
    return texte


def _mots_significatifs(texte):
    return [m for m in normaliser(texte).split() if len(m) >= 3 and m not in MOTS_VIDES]


def _construire_vocabulaire(entree):
    """Seuls les 'keywords' (choisis expres pour la recherche) alimentent
    le vocabulaire - PAS le texte de 'question_type', qui est une phrase
    naturelle destinee a l'affichage et qui contient souvent des mots
    parasites sans rapport (ex. 'passe' dans 'que se passe-t-il')."""
    mots = set()
    for mot_cle in entree["keywords"]:
        mots.update(_mots_significatifs(mot_cle))
    return mots


# Vocabulaire de chaque entree + frequence de chaque mot a travers TOUTES
# les entrees (pour ponderer : un mot rare est plus distinctif qu'un mot
# qui revient partout).
_VOCABULAIRES = {entree["id"]: _construire_vocabulaire(entree) for entree in QA_LIBRARY}
_FREQUENCE_MOTS = Counter()
for _vocab in _VOCABULAIRES.values():
    for _mot in _vocab:
        _FREQUENCE_MOTS[_mot] += 1
_NB_ENTREES = max(len(QA_LIBRARY), 1)


def _poids_mot(mot):
    """Poids inspire du TF-IDF : plus un mot est rare parmi les entrees,
    plus il compte. Toujours strictement positif."""
    freq = _FREQUENCE_MOTS.get(mot, 1)
    return math.log((_NB_ENTREES + 1) / freq) + 0.3


def _score_entree(mots_question, entree):
    """Chaque mot de la question ne compte qu'UNE SEULE FOIS pour cette
    entree (on garde sa meilleure correspondance, pas la somme)."""
    vocab = _VOCABULAIRES[entree["id"]]
    score = 0.0
    for mot_q in mots_question:
        meilleure_ratio = 0.0
        for mot_v in vocab:
            if mot_q == mot_v:
                ratio = 1.0
            elif len(mot_q) >= 4 and len(mot_v) >= 4:
                ratio = difflib.SequenceMatcher(None, mot_q, mot_v).ratio()
            else:
                ratio = 1.0 if mot_q == mot_v else 0.0
            if ratio > meilleure_ratio:
                meilleure_ratio = ratio
        if meilleure_ratio >= 0.82:
            score += meilleure_ratio * _poids_mot(mot_q)
    return score


def repondre_locale(question_brute):
    mots_question = _mots_significatifs(question_brute)
    if not mots_question:
        mots_question = normaliser(question_brute).split()

    meilleur = None
    meilleur_score = 0.0
    for entree in QA_LIBRARY:
        score = _score_entree(mots_question, entree)
        if score > meilleur_score:
            meilleur_score = score
            meilleur = entree

    # Seuil : au moins l'equivalent d'un mot assez distinctif bien matche.
    if meilleur and meilleur_score >= 1.0:
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


def repondre(question_brute):
    resultat_ia = repondre_ia(question_brute)
    if resultat_ia is not None:
        return resultat_ia
    return repondre_locale(question_brute)
