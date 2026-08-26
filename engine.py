# -*- coding: utf-8 -*-
"""
Moteur de comprehension de Fisca AI.

Architecture "filet de securite" a 3 etages :
1) Gemini File Search (PRIORITAIRE) - si configure et si l'appel reussit.
2) OpenAI File Search (SECOURS) - ACTUELLEMENT DESACTIVE (voir
   OPENAI_FALLBACK_ACTIF ci-dessous), le compte OpenAI n'ayant plus de
   credit operationnel. Reactivable a tout moment via une seule
   variable d'environnement, sans toucher au code.
3) Moteur local base sur mots-cles (DERNIER RECOURS) - toujours
   disponible, aucune dependance externe.

ARCHITECTURE TEMPORAIRE ACTUELLE : Question -> Gemini (File Search) ->
si succes, reponse Gemini -> si echec/timeout, moteur local directement
(OpenAI saute).

ARCHITECTURE CIBLE (une fois OpenAI de nouveau credite) : Gemini ->
OpenAI -> moteur local. Pour y repasser, il suffira de positionner
OPENAI_FALLBACK_ACTIF=1 dans les variables d'environnement Render -
aucune modification de code necessaire.

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
import time
import unicodedata
import difflib
from collections import Counter

from cache_data import QA_LIBRARY

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
    "juriste.\n\n"
    "REGLES DE FORMAT STRICTES :\n"
    "- N'utilise JAMAIS de syntaxe Markdown : pas d'etoiles **, pas de "
    "dieses #, pas de tirets de liste, pas de titres. Ecris uniquement "
    "en texte simple, en phrases et paragraphes courts, comme dans une "
    "conversation normale.\n"
    "- Tu dois TOUJOURS synthetiser l'information en une reponse "
    "autonome et complete des le depart - jamais rediger un brouillon "
    "detaille que tu comptes ensuite couper faute de place. Avant "
    "d'ecrire, identifie mentalement l'essentiel : le fait principal, "
    "l'article qui le fonde, et les conditions cles s'il y en a. "
    "Laisse volontairement de cote les details secondaires plutot que "
    "de risquer une reponse interrompue. Une reponse fait normalement "
    "3 a 6 phrases ; va au-dela uniquement si la question exige "
    "vraiment plusieurs points distincts (ex. une liste de sanctions). "
    "Ta reponse doit TOUJOURS etre complete et jamais coupee en plein "
    "milieu d'une phrase ou d'une idee.\n\n"
    "UTILISATION DES BLOCS DE CONTEXTE :\n"
    "- Le contexte qui t'est fourni est organise en blocs distincts "
    "(ARTICLES PRINCIPAUX, SANCTIONS APPLICABLES, EXCEPTIONS ET "
    "DEROGATIONS, PROCEDURES LIEES, AUTRES ARTICLES LIES). Si un bloc "
    "SANCTIONS APPLICABLES est present, mentionne systematiquement la "
    "sanction encourue dans ta reponse, meme si la question ne la "
    "demande pas explicitement - c'est une information que le "
    "contribuable doit connaitre. Si un bloc EXCEPTIONS ET DEROGATIONS "
    "est present, mentionne-le aussi explicitement plutot que de donner "
    "seulement la regle generale.\n\n"
    "REGLE DE PERIMETRE STRICTE :\n"
    "- Tu ne repond qu'a des questions sur la fiscalite nigerienne et la "
    "facture certifiee. Si on te demande de rediger un texte long, un "
    "essai, une histoire, un poeme, du code, ou tout contenu sans lien "
    "avec ce perimetre, refuse poliment et rappelle ton role, sans "
    "produire le contenu demande.\n\n"
    "REGLE DE CONTINUITE DE CONVERSATION :\n"
    "- Si un historique d'echanges precedents t'est fourni, utilise-le "
    "pour comprendre le contexte des questions courtes ou ambigues (ex. "
    "'et mes avantages ?' apres une question sur un metier precis fait "
    "reference a ce meme metier). Ne mentionne jamais explicitement que "
    "tu 'te souviens' ou que tu 'utilises l'historique' - reponds "
    "naturellement, comme le ferait une personne qui suit la "
    "conversation.\n\n"
    "REGLE DE RENVOI VERS LES SOURCES COMPLETES :\n"
    "- Termine chaque reponse par UNE SEULE courte phrase de renvoi (pas "
    "plus). Si la question porte specifiquement sur la facture "
    "certifiee/le SECeF, renvoie vers le livre : 'Pour plus de details "
    "et d'exemples pratiques, consultez mon livre Comprendre la Facture "
    "Certifiee, disponible dans la Bibliotheque de l'application.' Si la "
    "question porte sur un sujet fiscal plus general (hors du perimetre "
    "strict de la facture certifiee), renvoie plutot vers le texte "
    "integral : 'Pour le texte integral et les autres dispositions, "
    "consultez le CGI 2026, telechargeable gratuitement dans la "
    "Bibliotheque de l'application.'"
)

# ---------------------------------------------------------------------------
# Reglages de delai et de volume - centralises en haut du fichier.
#
# GEMINI_TIMEOUT_SECONDS : 12 -> 20 -> 25 -> 35s. Meme a 25s, des appels
# avec File Search actif ont continue a echouer en 504 DEADLINE_EXCEEDED
# tout pres de la limite (ex. 24.4s observes en production) - la
# recherche documentaire sur les 398 pages du CGI 2026 a parfois
# legitimement besoin de plus de temps pour terminer. IMPORTANT : le
# Start Command Gunicorn sur Render doit rester a --timeout 45 minimum
# (marge de 10s) pour que ce delai reste toujours sous celui de
# Gunicorn, sans quoi Gunicorn coupe le processus de force avant que ce
# timeout n'ait la chance de se declencher proprement.
#
# GEMINI_MAX_OUTPUT_TOKENS : 2048 -> 1500 (700 s'est revele trop serre en
# pratique : une partie de ce budget de tokens est consommee par le
# travail de recherche du File Search lui-meme, avant meme l'ecriture
# de la reponse finale - a 700, les reponses se retrouvaient coupees en
# plein milieu au lieu d'etre naturellement courtes comme demande dans
# le SYSTEM_PROMPT). 1500 laisse une vraie marge de securite tout en
# restant nettement en dessous de l'ancienne limite de 2048.
# ---------------------------------------------------------------------------
GEMINI_TIMEOUT_SECONDS = 35
GEMINI_MAX_OUTPUT_TOKENS = 1500
OPENAI_TIMEOUT_SECONDS = 12

# Bascule OpenAI - voir le commentaire d'architecture en tete de fichier.
# Desactive par defaut : passer a "1" sur Render pour reactiver le
# filet de secours OpenAI des que le compte aura de nouveau du credit,
# sans toucher au code.
OPENAI_FALLBACK_ACTIF = os.environ.get("OPENAI_FALLBACK_ACTIF", "0") == "1"

# Bascule du moteur local - SUSPENDU par defaut le temps de retravailler
# en profondeur son contenu (cache_data.py). Tant qu'il reste suspendu,
# une reponse Gemini en echec n'entraine plus une reponse locale
# potentiellement confuse : elle affiche un message d'indisponibilite
# clair et honnete a la place. Repasser a "1" sur Render pour le
# reactiver une fois le travail de fond termine, sans toucher au code.
MOTEUR_LOCAL_ACTIF = os.environ.get("MOTEUR_LOCAL_ACTIF", "0") == "1"

# Bascule de diagnostic - permet de tester Gemini SANS File Search
# (juste le modele, sans recherche documentaire) pour determiner si les
# 504 viennent du modele lui-meme ou specifiquement de la recherche dans
# le File Search Store. Mettre GEMINI_FILE_SEARCH_ACTIF=0 sur Render
# pour ce test, puis remettre a 1 (ou retirer la variable) ensuite.
GEMINI_FILE_SEARCH_ACTIF = os.environ.get("GEMINI_FILE_SEARCH_ACTIF", "1") == "1"

# ---------------------------------------------------------------------------
# Partie IA n°1 - Gemini (PRIORITAIRE) - optionnelle, activee seulement si
# configuree. Utilise le File Search Store cree via Colab.
# ---------------------------------------------------------------------------
try:
    from google import genai
    from google.genai import types as genai_types
    _gemini_client = (
        genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            # Securite de premier niveau : limite le delai par defaut de
            # TOUS les appels passes par ce client. Le vrai filet de
            # securite reste toutefois celui pose directement sur
            # l'appel dans repondre_gemini() ci-dessous (plus fiable
            # selon la documentation officielle du SDK).
            http_options=genai_types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
        )
        if os.environ.get("GEMINI_API_KEY")
        else None
    )
except Exception:
    _gemini_client = None
    genai_types = None

GEMINI_FILE_SEARCH_STORE = os.environ.get("GEMINI_FILE_SEARCH_STORE")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def _construire_contenus_gemini(question_brute, historique):
    """Construit la liste de tours de conversation attendue par Gemini :
    chaque echange precedent (question utilisateur + reponse du modele),
    suivi de la nouvelle question. Sans historique, se comporte comme
    avant (une seule question)."""
    contenus = []
    for question_precedente, reponse_precedente in historique or []:
        contenus.append(genai_types.Content(role="user", parts=[genai_types.Part(text=question_precedente)]))
        contenus.append(genai_types.Content(role="model", parts=[genai_types.Part(text=reponse_precedente)]))
    contenus.append(genai_types.Content(role="user", parts=[genai_types.Part(text=question_brute)]))
    return contenus


def repondre_gemini(question_brute, historique=None):
    """Tente une reponse via Gemini (avec File Search si
    GEMINI_FILE_SEARCH_ACTIF et GEMINI_FILE_SEARCH_STORE sont tous deux
    actifs, sans File Search sinon - utile pour le diagnostic). Retourne
    None si indisponible pour une raison quelconque - l'appelant bascule
    alors sur OpenAI (si actif) puis sur le moteur local.

    'historique' est une liste optionnelle de tuples (question, reponse)
    des echanges precedents de la MEME conversation, transmise pour que
    Gemini comprenne les questions de suivi ('et mes avantages ?').

    Chronometrage detaille : chaque appel (succes ou echec) est logge
    avec sa duree exacte, la taille de la reponse ou le type d'erreur,
    et le nombre d'echanges d'historique transmis - c'est ce qui permet
    de savoir precisement combien de temps Gemini met avant un eventuel
    504 DEADLINE_EXCEEDED, plutot que de deviner."""
    if not _gemini_client:
        return None

    nb_echanges = len(historique or [])
    utilise_file_search = bool(GEMINI_FILE_SEARCH_ACTIF and GEMINI_FILE_SEARCH_STORE)
    debut = time.time()

    config_kwargs = dict(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
        http_options=genai_types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
    )
    if utilise_file_search:
        config_kwargs["tools"] = [
            genai_types.Tool(
                file_search=genai_types.FileSearch(
                    file_search_store_names=[GEMINI_FILE_SEARCH_STORE]
                )
            )
        ]

    try:
        response = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_construire_contenus_gemini(question_brute, historique),
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )
        duree = time.time() - debut
        texte = getattr(response, "text", "") or ""
        if not texte.strip():
            print(
                f"[Fisca AI][Gemini] Reponse VIDE - duree={duree:.1f}s, "
                f"file_search={utilise_file_search}, historique={nb_echanges} echange(s)."
            )
            return None

        print(
            f"[Fisca AI][Gemini] SUCCES - duree={duree:.1f}s, "
            f"file_search={utilise_file_search}, taille_reponse={len(texte)} caracteres, "
            f"historique={nb_echanges} echange(s)."
        )
        return {
            "niveau": 1,
            "reponse": texte.strip(),
            "source": "Reponse generee par l'IA (Gemini) a partir des documents officiels charges",
            "verified": None,
            "question_comprise": question_brute,
            "moteur": "gemini",
        }
    except Exception as e:
        duree = time.time() - debut
        if OPENAI_FALLBACK_ACTIF:
            suite = "OpenAI"
        elif MOTEUR_LOCAL_ACTIF:
            suite = "le moteur local"
        else:
            suite = "un message d'indisponibilite (moteur local suspendu)"
        print(
            f"[Fisca AI][Gemini] ECHEC ({type(e).__name__}: {e}) - duree={duree:.1f}s, "
            f"file_search={utilise_file_search}, historique={nb_echanges} echange(s) - bascule sur {suite}."
        )
        return None


def generer_titre_conversation(question, reponse):
    """Construit un titre court a partir des premiers mots de la
    question - AUCUN appel IA. Le titre n'a pas besoin d'etre parfait ;
    ce deuxieme appel Gemini, declenche a chaque toute premiere question
    d'une conversation, ralentissait inutilement la reponse a cette
    premiere question sans justification suffisante."""
    titre = question.strip()
    if len(titre) > 40:
        coupe = titre[:40].rsplit(" ", 1)[0]
        titre = (coupe or titre[:40]) + "…"
    return titre or "Discussion"


# ---------------------------------------------------------------------------
# Partie IA n°2 - OpenAI (SECOURS) - voir OPENAI_FALLBACK_ACTIF en haut du
# fichier : desactive par defaut le temps que le compte soit recredite.
# ---------------------------------------------------------------------------
try:
    from openai import OpenAI
    _client = OpenAI() if os.environ.get("OPENAI_API_KEY") else None
except Exception:
    _client = None

OPENAI_VECTOR_STORE_ID = os.environ.get("OPENAI_VECTOR_STORE_ID")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def repondre_ia(question_brute, historique=None):
    if not _client or not OPENAI_VECTOR_STORE_ID:
        return None
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for question_precedente, reponse_precedente in historique or []:
            messages.append({"role": "user", "content": question_precedente})
            messages.append({"role": "assistant", "content": reponse_precedente})
        messages.append({"role": "user", "content": question_brute})

        response = _client.responses.create(
            model=OPENAI_MODEL,
            input=messages,
            tools=[{"type": "file_search", "vector_store_ids": [OPENAI_VECTOR_STORE_ID], "max_num_results": 4}],
            max_output_tokens=2048,
            timeout=OPENAI_TIMEOUT_SECONDS,
        )
        texte = getattr(response, "output_text", "") or ""
        if not texte.strip():
            return None
        return {
            "niveau": 1,
            "reponse": texte.strip(),
            "source": "Reponse generee par l'IA (OpenAI) a partir des documents officiels charges",
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


# ---------------------------------------------------------------------------
# RAG maison (CGI 2026 decoupe en 1082 articles, indexes avec pgvector) -
# destine a remplacer progressivement le File Search Gemini, trop lent et
# peu fiable sur le plan gratuit (voir les echecs 504/429 en production).
#
# Desactive par defaut (RAG_ACTIF) - la base pgvector doit d'abord etre
# entierement peuplee (generer_embeddings.py) avant activation. Passer a
# "1" sur Render une fois la recherche validee via test_rag.py.
#
# TROIS NIVEAUX DE REPLI, du plus riche au plus basique :
#   1) Recherche RAG reussie + Gemini redige une vraie reponse -> ideal.
#   2) Recherche RAG reussie mais la REDACTION echoue (quota de
#      generation epuise, timeout...) -> on affiche le texte BRUT du
#      meilleur article trouve, sans reformulation. Moins agreable a
#      lire, mais JAMAIS faux : c'est le vrai texte de loi. Ce niveau ne
#      consomme que le quota d'embedding (1000/jour), quasiment toujours
#      disponible meme quand le quota de generation (20/jour) est grille.
#   3) La RECHERCHE elle-meme echoue (base de donnees injoignable, etc.)
#      -> repondre_rag() retourne None, l'appelant (repondre()) bascule
#      alors sur l'ancien chemin (File Search puis moteur local).
# ---------------------------------------------------------------------------
RAG_ACTIF = os.environ.get("RAG_ACTIF", "0") == "1"

# Point #12 du plan initial : normalisation de la question par un appel
# Gemini supplementaire avant la recherche. COUTE DU QUOTA a chaque
# question - desactive par defaut, a activer uniquement une fois le
# paiement regle et le volume d'usage reel evalue.
NORMALISATION_ACTIVE = os.environ.get("NORMALISATION_ACTIF", "0") == "1"

# Point #15 du plan initial : reranker par IA. COUTE DU QUOTA a chaque
# question (un appel Gemini supplementaire) - desactive par defaut.
RERANKER_ACTIVE = os.environ.get("RERANKER_ACTIF", "0") == "1"

# Point #24 du plan initial : dossier fiscal virtuel (version structuree
# de la normalisation #12). COUTE DU QUOTA - desactive par defaut. Ne pas
# activer en meme temps que NORMALISATION_ACTIVE : les deux enrichissent
# la question de facon similaire, un seul suffit selon le niveau choisi.
DOSSIER_VIRTUEL_ACTIVE = os.environ.get("DOSSIER_VIRTUEL_ACTIF", "0") == "1"

# Point #25 du plan initial : recherche multi-etapes. COUTE DU QUOTA
# (un appel Gemini supplementaire) - desactive par defaut.
MULTI_HOP_ACTIVE = os.environ.get("MULTI_HOP_ACTIF", "0") == "1"


def repondre_rag(question_brute, db, historique=None):
    """Tente une reponse via le RAG maison. Voir le commentaire d'archi-
    tecture juste au-dessus pour la logique des 3 niveaux de repli.
    'db' est une connexion psycopg2 deja ouverte (fournie par app.py).

    Depuis la Phase 3, utilise recherche_hybride (vectoriel + mots-cles,
    fusionnes par rang) au lieu du vectoriel seul, et une expansion des
    renvois ponderee par type de relation (voir rag.py).

    Depuis la Phase 5 : si la question est jugee LARGE ("explique-moi
    toute la taxe professionnelle") ET qu'elle nomme une matiere fiscale
    connue, tente d'abord une reponse basee sur la FICHE recapitulative
    de cette matiere (vue d'ensemble organisee par theme), avant de
    retomber sur la recherche standard 5-articles si ca ne s'applique
    pas ou echoue - aucun changement de comportement pour les questions
    ciblees habituelles."""
    if not _gemini_client or not RAG_ACTIF:
        return None

    from rag import (
        embed_question, recherche_hybride, expand_via_refs,
        build_context_blocks, check_no_hallucinated_articles, call_gemini_llm,
        est_question_large, detecter_matiere_dans_question, construire_contexte_fiche,
    )

    debut = time.time()

    # --- Tentative "fiche" pour les questions larges (Phase 5) ---
    if est_question_large(question_brute):
        matiere = detecter_matiere_dans_question(question_brute)
        if matiere:
            try:
                resultat_fiche = construire_contexte_fiche(matiere, db)
            except Exception as e:
                print(f"[Fisca AI][RAG][Fiche] Échec construction fiche ({type(e).__name__}: {e}) — repli sur la recherche standard.")
                resultat_fiche = None
            if resultat_fiche:
                contexte_fiche, ids_fiche = resultat_fiche
                prompt_fiche = (
                    SYSTEM_PROMPT + "\n\n"
                    "L'utilisateur pose une question large sur un impôt/une matière fiscale entière. "
                    "Voici une vue d'ensemble structurée par thème :\n\n"
                    f"{contexte_fiche}\n\nQuestion : {question_brute}"
                )
                try:
                    reponse_texte = call_gemini_llm(
                        _gemini_client, prompt_fiche, model=GEMINI_MODEL,
                        max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
                        timeout_secondes=GEMINI_TIMEOUT_SECONDS,
                    )
                    if reponse_texte.strip():
                        duree = time.time() - debut
                        suspects = check_no_hallucinated_articles(reponse_texte, ids_fiche)
                        print(f"[Fisca AI][RAG][Fiche] SUCCÈS — matière={matiere}, durée={duree:.1f}s, suspects={suspects or 'aucun'}.")
                        return {
                            "niveau": 1,
                            "reponse": reponse_texte.strip(),
                            "source": f"Vue d'ensemble générée par l'IA (fiche {matiere}) — CGI 2026",
                            "verified": not suspects,
                            "question_comprise": question_brute,
                            "moteur": "rag_fiche",
                        }
                except Exception as e:
                    print(f"[Fisca AI][RAG][Fiche] Rédaction en échec ({type(e).__name__}: {e}) — repli sur la recherche standard.")
                # Pas de "niveau 2" special pour la fiche : on retombe
                # simplement sur le chemin standard ci-dessous plutot que
                # d'inventer un texte brut de synthese qui n'existe pas.

    # --- Chemin standard (question ciblee, ou fiche non applicable/en echec) ---
    try:
        from rag import normaliser_question, construire_dossier_fiscal_virtuel, dossier_vers_texte_recherche

        question_pour_recherche = question_brute
        if DOSSIER_VIRTUEL_ACTIVE:
            # Version structuree (#24), prioritaire si les deux sont actifs
            dossier = construire_dossier_fiscal_virtuel(_gemini_client, question_brute, model=GEMINI_MODEL)
            question_pour_recherche = dossier_vers_texte_recherche(question_brute, dossier)
        elif NORMALISATION_ACTIVE:
            question_pour_recherche = normaliser_question(_gemini_client, question_brute, model=GEMINI_MODEL)

        vecteur_question = embed_question(_gemini_client, question_pour_recherche)

        from rag import reranker_candidats
        top_k_recherche = 12 if RERANKER_ACTIVE else 5
        pivots = recherche_hybride(db, vecteur_question, question_pour_recherche, top_k=top_k_recherche)
        if RERANKER_ACTIVE and pivots:
            pivots = reranker_candidats(_gemini_client, question_brute, pivots, model=GEMINI_MODEL, top_k_final=5)
        if not pivots:
            print(f"[Fisca AI][RAG] Aucun article pertinent trouvé — durée={time.time()-debut:.1f}s.")
            return None
        linked = expand_via_refs(db, pivots)

        if MULTI_HOP_ACTIVE:
            from rag import rechercher_multi_hop
            linked = linked + rechercher_multi_hop(_gemini_client, db, question_brute, pivots, linked, model=GEMINI_MODEL)
    except Exception as e:
        print(f"[Fisca AI][RAG] ÉCHEC RECHERCHE ({type(e).__name__}: {e}) — durée={time.time()-debut:.1f}s — bascule sur l'ancien chemin.")
        return None

    contexte = build_context_blocks(pivots, linked)
    tous_ids = [a.article_id for a in pivots + linked]

    prompt = (
        SYSTEM_PROMPT + "\n\n"
        "Voici les articles du CGI 2026 les plus pertinents pour cette question, "
        "déjà sélectionnés pour toi :\n\n"
        f"{contexte}\n\nQuestion : {question_brute}"
    )

    try:
        reponse_texte = call_gemini_llm(
            _gemini_client, prompt, model=GEMINI_MODEL,
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
            timeout_secondes=GEMINI_TIMEOUT_SECONDS,
        )
        if reponse_texte.strip():
            duree = time.time() - debut
            suspects = check_no_hallucinated_articles(reponse_texte, tous_ids)
            print(
                f"[Fisca AI][RAG] SUCCÈS — durée={duree:.1f}s, "
                f"articles={tous_ids}, suspects={suspects or 'aucun'}."
            )
            return {
                "niveau": 1,
                "reponse": reponse_texte.strip(),
                "source": f"Réponse générée par l'IA (RAG maison) — articles {', '.join(tous_ids)} du CGI 2026",
                "verified": not suspects,
                "question_comprise": question_brute,
                "moteur": "rag",
            }
    except Exception as e:
        print(
            f"[Fisca AI][RAG] Rédaction en échec ({type(e).__name__}: {e}) — "
            f"durée={time.time()-debut:.1f}s — repli sur le texte brut de l'article."
        )

    # Niveau 2 : la recherche a reussi mais la redaction a echoue (ou n'a
    # rien renvoye) - on affiche le texte brut du meilleur article trouve.
    meilleur = pivots[0]
    print(f"[Fisca AI][RAG] Niveau 2 (texte brut) — article {meilleur.article_id}.")
    return {
        "niveau": 2,
        "reponse": (
            "Je n'ai pas pu rédiger une explication complète pour le moment, "
            "mais voici l'article qui semble répondre à votre question :\n\n"
            f"Article {meilleur.article_id} — {meilleur.text}"
        ),
        "source": f"Extrait brut du CGI 2026, article {meilleur.article_id} (rédaction indisponible)",
        "verified": True,
        "question_comprise": question_brute,
        "moteur": "rag_brut",
    }


def repondre(question_brute, historique=None, db=None):
    """Ordre de priorite ACTUEL (temporaire, voir tete de fichier) :
    Gemini (File Search) -> moteur local, SI ce dernier est actif.

    OpenAI est saute tant que OPENAI_FALLBACK_ACTIF n'est pas active
    (compte sans credit). Le moteur local est SUSPENDU par defaut
    (MOTEUR_LOCAL_ACTIF) le temps qu'il soit retravaille en profondeur -
    ses reponses etaient parfois source de confusion. Tant qu'il reste
    suspendu, un echec Gemini renvoie un message d'indisponibilite clair
    plutot qu'une reponse locale potentiellement confuse.

    Chaque etage n'est tente que si le precedent est indisponible ou
    echoue - jamais d'erreur bloquante pour l'utilisateur.

    'historique' est une liste optionnelle de tuples (question, reponse)
    des echanges precedents de la meme conversation - transmise aux
    moteurs IA pour la continuite. Le moteur local, purement base sur
    des mots-cles, ignore ce parametre : il n'a pas la capacite de
    raisonner sur un contexte de conversation.

    'db' est une connexion psycopg2 optionnelle, necessaire uniquement
    pour le RAG maison (voir repondre_rag). Sans elle, ou si RAG_ACTIF
    n'est pas active, ce premier etage est simplement saute."""
    if db is not None:
        resultat = repondre_rag(question_brute, db, historique)
        if resultat is not None:
            return resultat

    resultat = repondre_gemini(question_brute, historique)
    if resultat is not None:
        return resultat

    if OPENAI_FALLBACK_ACTIF:
        resultat = repondre_ia(question_brute, historique)
        if resultat is not None:
            return resultat

    if MOTEUR_LOCAL_ACTIF:
        # Point #35 du plan initial : le moteur enrichi (1096 articles,
        # vocabulaire, themes) est tente en premier ; l'ancien moteur
        # (cache_data.py, ~40 entrees ecrites a la main) ne sert plus que
        # de tout dernier repli si le fichier de donnees enrichi n'a pas
        # pu etre charge pour une raison quelconque.
        from moteur_local_enrichi import repondre_locale_enrichie
        resultat = repondre_locale_enrichie(question_brute)
        if resultat is not None:
            return resultat
        return repondre_locale(question_brute)

    print("[Fisca AI] Tous les moteurs disponibles ont echoue (moteur local suspendu) - message d'indisponibilite renvoye.")
    return {
        "niveau": 3,
        "reponse": (
            "Le service rencontre actuellement une difficulte technique passagere. "
            "Merci de reessayer votre question dans quelques instants."
        ),
        "source": None,
        "verified": None,
        "question_comprise": question_brute,
        "moteur": "indisponible",
    }

