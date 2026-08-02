# -*- coding: utf-8 -*-
"""
Moteur de comprehension de Fisca AI.

Architecture "filet de securite" :
1) On tente d'abord une reponse via l'API OpenAI (si configuree et si
   l'appel reussit).
2) Sinon (ou en cas d'echec), on bascule automatiquement et
   silencieusement sur le moteur local base sur mots-cles ci-dessous.

MOTEUR LOCAL - v3 (ajoute un seuil de couverture) :
La v2 corrigeait le double-comptage (chaque mot de la question ne
compte qu'une fois par entree, ponderation type TF-IDF).

Mais la v2 avait un angle mort : le seuil final etait un score ABSOLU,
jamais rapporte a la question. Consequence : une entree qui ne
partageait que 2 mots tres communs (donc a faible poids chacun, mais
dont la somme depassait quand meme le seuil) pouvait "gagner" alors que
la moitie des mots de la question (souvent les plus specifiques, comme
"tva" ou "impact") n'avaient AUCUNE correspondance dans son vocabulaire.

La v3 ajoute une COUVERTURE PONDEREE : la part du poids total de la
question qui a effectivement trouve une correspondance dans l'entree.
On exige maintenant score >= seuil ET couverture >= seuil_couverture.
Une entree qui ne repond qu'a une petite fraction "par hasard" de la
question, meme avec un score cumule correct, est desormais rejetee.
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
# Moteur local v3
# ---------------------------------------------------------------------------
MOTS_VIDES = {
    "le", "la", "les", "de", "des", "du", "un", "une", "est", "ce", "cette",
    "que", "qui", "quel", "quelle", "quels", "quelles", "a", "et",
    "en", "pour", "sur", "au", "aux", "par", "avec", "dans", "je", "tu",
    "il", "elle", "vous", "nous", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "si", "ne", "pas", "on", "se", "sont", "ai", "as",
    "faire", "fait", "etre", "dois", "doit", "peut", "peux", "comment",
}

# Reglages du moteur - centralises ici pour etre faciles a ajuster
# une fois que tu auras des vrais logs de production.
SEUIL_SCORE = 1.0        # score absolu minimal (inchange par rapport a la v2)
SEUIL_COUVERTURE = 0.45  # part MINIMALE (ponderee) des mots de la question
                          # qui doit etre retrouvee dans l'entree gagnante
DEBUG_MOTEUR = os.environ.get("DEBUG_MOTEUR", "0") == "1"


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
    entree (on garde sa meilleure correspondance, pas la somme).

    Retourne (score, couverture) :
    - score : somme ponderee des correspondances (comme avant)
    - couverture : part du poids TOTAL de la question qui a trouve une
      correspondance dans cette entree (0.0 a 1.0). C'est ce qui manquait
      en v2 : un score correct obtenu en ne matchant qu'une petite partie
      de la question (souvent les mots les moins specifiques) ne doit pas
      suffire a "gagner".
    """
    vocab = _VOCABULAIRES[entree["id"]]
    score = 0.0
    poids_total = 0.0
    poids_matche = 0.0
    for mot_q in mots_question:
        p = _poids_mot(mot_q)
        poids_total += p

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
            score += meilleure_ratio * p
            poids_matche += meilleure_ratio * p

    couverture = (poids_matche / poids_total) if poids_total > 0 else 0.0
    return score, couverture


def repondre_locale(question_brute):
    mots_question = _mots_significatifs(question_brute)
    if not mots_question:
        mots_question = normaliser(question_brute).split()

    candidats = []
    for entree in QA_LIBRARY:
        score, couverture = _score_entree(mots_question, entree)
        if score > 0:
            candidats.append((score, couverture, entree))

    candidats.sort(key=lambda c: c[0], reverse=True)

    if DEBUG_MOTEUR and candidats:
        print(f"[Fisca AI][debug] Question: {question_brute!r}")
        for score, couverture, entree in candidats[:5]:
            print(
                f"    id={entree['id']!r} score={score:.2f} "
                f"couverture={couverture:.0%} -> {entree['question_type']!r}"
            )

    if candidats:
        meilleur_score, meilleure_couverture, meilleur = candidats[0]
        if meilleur_score >= SEUIL_SCORE and meilleure_couverture >= SEUIL_COUVERTURE:
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
