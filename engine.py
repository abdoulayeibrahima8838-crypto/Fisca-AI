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
    "que", "qui", "quel", "quelle", "quels", "quelles", "quoi", "a", "et",
    "en", "pour", "sur", "au", "aux", "par", "avec", "dans", "je", "tu",
    "il", "elle", "vous", "nous", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "si", "ne", "on", "se", "sont", "ai", "as",
    "faire", "fait", "etre", "dois", "doit", "peut", "peux", "comment",
    # NOTE v6 : "pas" a ete retire de cette liste (voir plus bas) - la
    # negation est un signal fiscal essentiel ("je n'ai PAS de secef" vs
    # "j'ai un secef" sont juridiquement opposes), et plusieurs entrees de
    # cache_data.py comptaient deja dessus dans leurs keywords ("pas de
    # machine", "pas de nif"...) sans que ca ait jamais eu d'effet tant
    # que "pas" etait supprime avant meme d'arriver au matching. "quoi",
    # a l'inverse, a ete AJOUTE ici : interrogatif generique ("c'est
    # quoi...", "je risque quoi...") sans valeur distinctive, qui causait
    # des collisions du meme type que "facture"/"certifiee".
}

# Mots PLAFONNES specifiques au domaine : dans un corpus qui ne parle QUE
# de facture certifiee/SECeF, des mots comme "facture" ou "certifiee"
# reviennent dans la quasi-totalite des questions, et n'ont donc quasiment
# aucune valeur distinctive - meme si, par accident de redaction, ils
# n'apparaissent comme keyword que dans 1 ou 2 entrees de cache_data.py
# (ce qui leur donnerait sinon un poids IDF artificiellement eleve, cf.
# le cas "phases-deploiement" qui raflait la mise sur toute question
# contenant "facture"+"certifiee"). On NE LES EXCLUT PAS (l'entree
# "definition-facture", qui definit precisement ce terme, a besoin de
# pouvoir matcher dessus) : on plafonne simplement leur poids a une
# valeur volontairement faible, qu'importe leur frequence reelle dans
# cache_data.py.
POIDS_PLAFONNE_DOMAINE = {
    "facture": 0.3, "factures": 0.3,
    "certifie": 0.3, "certifiee": 0.3, "certifies": 0.3, "certifiees": 0.3,
    "non": 0.3,
    # "pas" reste utile comme signal de negation, mais il est lui aussi
    # tres frequent dans des keywords sans rapport entre eux ("pas de
    # machine", "pas de nif", "pas de connexion", "il ne veut pas
    # donner"...) : plafonne bas pour eviter les faux positifs. La vraie
    # distinction "avec/sans systeme" repose sur le champ "expressions",
    # pas sur le poids brut de ce seul mot.
    "pas": 0.4,
    # "loi" n'est keyword-liste QUE dans l'entree "pourquoi" ("but de la
    # loi", "cette loi existe"), ce qui lui donne un poids IDF tres eleve
    # (mot "rare" dans le corpus) alors que c'est un mot generique que
    # n'importe quelle question fiscale peut naturellement contenir
    # ("respecter la loi", "que dit la loi"...). Meme piege que
    # "facture"/"certifiee".
    "loi": 0.4,
}

# v6 : bonus attribue quand une expression complete de l'entree ("expressions"
# dans cache_data.py) apparait telle quelle dans la question. Une expression
# exacte ("remplacer la facture certifiee") est un signal bien plus fort et
# fiable qu'une addition de mots isoles - elle merite un bonus consequent et
# une couverture forcee au maximum, car elle prouve que la question porte
# specifiquement sur cette entree, meme si les mots pris individuellement
# sont trop generiques ou trop rares pour bien scorer seuls.
POIDS_EXPRESSION_COMPLETE = 6.0

# Reglages du moteur - centralises ici pour etre faciles a ajuster
# une fois que tu auras des vrais logs de production.
SEUIL_SCORE = 1.0        # score absolu minimal (inchange par rapport a la v2)
SEUIL_COUVERTURE = 0.30  # part MINIMALE (ponderee) des mots de la question
                          # (parmi ceux qui existent quelque part dans le
                          # corpus) qui doit etre retrouvee dans l'entree
                          # gagnante. Volontairement modere : le but est
                          # d'ecarter les entrees qui ne partagent quasi
                          # rien avec la question (cas du hors-sujet
                          # historique/TVA), pas de punir des entrees a
                          # keywords courts et cibles (design voulu de
                          # cache_data.py).
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

# Tous les mots qui apparaissent comme keyword d'AU MOINS UNE entree.
# Un mot de la question absent de cet ensemble ne pourra structurellement
# JAMAIS matcher aucune entree (il n'existe dans aucun vocabulaire) : il
# ne doit donc jamais etre compte contre une entree dans le calcul de la
# couverture, sous peine de punir a tort des entrees par ailleurs
# correctes simplement parce que la question est formulee avec des mots
# (ex. "impact", "consequence") absents de toute liste de keywords.
_VOCAB_GLOBAL = set(_FREQUENCE_MOTS.keys())


def _mot_potentiellement_matchable(mot_q):
    """True si ce mot a ne serait-ce qu'une chance de matcher AU MOINS
    une entree du corpus (exactement ou par ressemblance floue, avec la
    meme tolerance que le scoring). Sert uniquement a decider si un mot
    doit compter dans le denominateur de la couverture."""
    if mot_q in _VOCAB_GLOBAL:
        return True
    if len(mot_q) >= 5:
        for mot_v in _VOCAB_GLOBAL:
            if len(mot_v) >= 5 and difflib.SequenceMatcher(None, mot_q, mot_v).ratio() >= 0.82:
                return True
    return False


def _poids_mot(mot):
    """Poids inspire du TF-IDF : plus un mot est rare parmi les entrees,
    plus il compte. Toujours strictement positif. Plafonne pour les
    quelques mots generiques au domaine (voir POIDS_PLAFONNE_DOMAINE)."""
    if mot in POIDS_PLAFONNE_DOMAINE:
        return POIDS_PLAFONNE_DOMAINE[mot]
    freq = _FREQUENCE_MOTS.get(mot, 1)
    return math.log((_NB_ENTREES + 1) / freq) + 0.3


# v6 : negations metier (section 5 du cahier d'amelioration). Une simple
# comparaison d'ensembles de mots ne suffit pas a detecter une negation -
# "pas" et "secef" peuvent co-occurrer dans une question SANS exprimer
# une absence ("j'ai un secef... mais... pas... facturer"). Ces regex
# exigent une PROXIMITE CONTIGUE ("pas de secef", "sans machine") pour
# n'allumer le concept que quand la negation porte reellement sur le mot
# qui suit.
NEGATIONS_METIER = {
    r"\bpas de (secef|machine|systeme|dispositif)\b": "ABSENCE_SYSTEME",
    r"\bsans (secef|machine|systeme)\b": "ABSENCE_SYSTEME",
    r"\baucune? (secef|machine|systeme|dispositif|equipement)\b": "ABSENCE_SYSTEME",
    r"\bne l utilise pas\b": "NON_UTILISATION_SYSTEME",
    r"\bn utilise pas\b": "NON_UTILISATION_SYSTEME",
    r"\bnon utilisee?\b": "NON_UTILISATION_SYSTEME",
    r"\bne m en sers pas\b": "NON_UTILISATION_SYSTEME",
    r"\bne facture pas avec\b": "NON_UTILISATION_SYSTEME",
    r"\bne facture pas dessus\b": "NON_UTILISATION_SYSTEME",
}


def _detecter_concepts_negation(texte_normalise):
    concepts = set()
    for pattern, concept in NEGATIONS_METIER.items():
        if re.search(pattern, texte_normalise):
            concepts.add(concept)
    return concepts


def _bonus_expression(mots_question_set, entree):
    """True si TOUS les mots significatifs d'au moins une expression de
    l'entree (champ optionnel 'expressions' dans cache_data.py) sont
    presents dans la question - independamment de l'ordre ou des mots de
    liaison autour ("d'une", "l'", etc.). Plus robuste qu'une comparaison
    de sous-chaine litterale face aux reformulations naturelles."""
    for expression in entree.get("expressions", []):
        mots_expression = set(_mots_significatifs(expression))
        if mots_expression and mots_expression.issubset(mots_question_set):
            return True
    return False


def _score_entree(mots_question, entree, mots_question_set=None, concepts_negation=None):
    """Chaque mot de la question ne compte qu'UNE SEULE FOIS pour cette
    entree (on garde sa meilleure correspondance, pas la somme).

    Retourne (score, couverture) :
    - score : somme ponderee des correspondances, plus le bonus
      d'expression complete / de concept de negation le cas echeant ;
    - couverture : part du poids TOTAL de la question qui a trouve une
      correspondance dans cette entree (0.0 a 1.0), forcee a 1.0 si une
      expression complete ou un concept de negation a matche (signal a
      lui seul suffisamment fort).
    """
    vocab = _VOCABULAIRES[entree["id"]]
    score = 0.0
    poids_total = 0.0
    poids_matche = 0.0
    for mot_q in mots_question:
        # Un mot absent de TOUT le corpus (aucune entree ne l'a comme
        # keyword) ne peut par construction jamais matcher : on l'ignore
        # completement, plutot que de penaliser la couverture de chaque
        # entree pour un mot qu'aucune n'a jamais eu de chance de matcher.
        if not _mot_potentiellement_matchable(mot_q):
            continue

        p = _poids_mot(mot_q)
        poids_total += p

        meilleure_ratio = 0.0
        for mot_v in vocab:
            if mot_q == mot_v:
                ratio = 1.0
            elif len(mot_q) >= 5 and len(mot_v) >= 5:
                ratio = difflib.SequenceMatcher(None, mot_q, mot_v).ratio()
            else:
                ratio = 1.0 if mot_q == mot_v else 0.0
            if ratio > meilleure_ratio:
                meilleure_ratio = ratio

        if meilleure_ratio >= 0.82:
            score += meilleure_ratio * p
            poids_matche += meilleure_ratio * p

    couverture = (poids_matche / poids_total) if poids_total > 0 else 0.0
    signal_fort = False

    if mots_question_set and _bonus_expression(mots_question_set, entree):
        score += POIDS_EXPRESSION_COMPLETE
        couverture = 1.0
        signal_fort = True

    if concepts_negation and set(entree.get("concepts_negation", [])) & concepts_negation:
        score += POIDS_EXPRESSION_COMPLETE
        couverture = 1.0
        signal_fort = True

    return score, couverture, signal_fort





# v6 : seuils de detection d'ambiguite (section 9 du cahier d'amelioration).
# Si les deux meilleurs candidats sont trop proches, mieux vaut demander
# une precision que de choisir arbitrairement - une mauvaise reponse
# donnee avec assurance est pire qu'une question de clarification.
MARGE_MINIMALE_ABSOLUE = 1.0
RATIO_AMBIGUITE = 0.90


def repondre_locale(question_brute):
    mots_question = _mots_significatifs(question_brute)
    if not mots_question:
        mots_question = normaliser(question_brute).split()
    mots_question_set = set(mots_question)
    concepts_negation = _detecter_concepts_negation(normaliser(question_brute))

    candidats = []
    for entree in QA_LIBRARY:
        score, couverture, signal_fort = _score_entree(mots_question, entree, mots_question_set, concepts_negation)
        if score > 0:
            candidats.append((score, couverture, entree, signal_fort))

    candidats.sort(key=lambda c: c[0], reverse=True)

    if DEBUG_MOTEUR and candidats:
        print(f"[Fisca AI][debug] Question: {question_brute!r}")
        for score, couverture, entree, signal_fort in candidats[:5]:
            marque = " [SIGNAL FORT]" if signal_fort else ""
            print(
                f"    id={entree['id']!r} score={score:.2f} "
                f"couverture={couverture:.0%} -> {entree['question_type']!r}{marque}"
            )

    if candidats:
        meilleur_score, meilleure_couverture, meilleur, meilleur_signal_fort = candidats[0]
        if meilleur_score >= SEUIL_SCORE and meilleure_couverture >= SEUIL_COUVERTURE:

            # Le candidat #1 est valable individuellement - mais est-il
            # NETTEMENT devant le #2, ou est-ce trop serre pour trancher
            # sans risque ? On saute cette verification si le candidat #1
            # a matche sur un signal fort (expression complete ou concept
            # de negation) : ce signal est deliberement pose par un humain
            # dans cache_data.py pour CETTE situation precise, il fait donc
            # autorite meme si un autre candidat accumule un score proche
            # par la simple coincidence de quelques mots generiques.
            if not meilleur_signal_fort and len(candidats) >= 2:
                deuxieme_score, deuxieme_couverture, deuxieme, _ = candidats[1]
                if deuxieme_score >= SEUIL_SCORE:
                    ecart = meilleur_score - deuxieme_score
                    ratio = deuxieme_score / meilleur_score if meilleur_score > 0 else 0
                    if ecart < MARGE_MINIMALE_ABSOLUE or ratio > RATIO_AMBIGUITE:
                        return {
                            "niveau": 2,
                            "reponse": (
                                "Votre question peut correspondre a plusieurs sujets. "
                                "Pourriez-vous preciser laquelle vous interesse ?\n\n"
                                f"1. {meilleur['question_type']}\n"
                                f"2. {deuxieme['question_type']}"
                            ),
                            "source": None,
                            "verified": None,
                            "question_comprise": question_brute,
                            "moteur": "local",
                        }

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
