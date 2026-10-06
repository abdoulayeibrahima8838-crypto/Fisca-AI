"""
agent.py — Agent Fisca AI (recherche CGI 2026 + calcul + vérification)

Branché sur le RAG existant (rag.py, vocabulaire.py) et appelé depuis
engine.py par repondre_agent(). Désactivé par défaut : il ne s'exécute que
si la variable AGENT_ACTIF vaut "1" sur Render.

Principes :
- Le modèle planifie et rédige ; le calcul et la vérification sont faits en
  code Python (aucun appel au modèle, donc aucun quota consommé).
- Aucun taux n'est inscrit dans le code : chaque taux utilisé dans un calcul
  doit provenir d'un article réellement consulté pendant la requête.
- Nombre d'appels au modèle et durée totale plafonnés. En cas de dépassement
  ou d'erreur, l'agent rend la main (None) et engine.py bascule sur le RAG
  habituel : l'utilisateur obtient toujours une réponse.
"""

import ast
import operator
import os
import re
import time
import unicodedata

from google.genai import types

from rag import embed_question, recherche_hybride, expand_via_refs
from vocabulaire import elargir_question


MAX_APPELS_MODELE = int(os.environ.get("AGENT_MAX_APPELS", "5"))
DUREE_FORCAGE_S = 45   # au-delà, l'appel suivant est forcé à conclure (sans outils)
DUREE_MAX_S = 80       # au-delà, abandon et repli sur le RAG habituel
K_DEFAUT, K_MAX = 5, 8
TEXTE_MAX = 3000       # caractères d'article renvoyés au modèle
HISTORIQUE_MAX = 3     # nombre d'échanges précédents transmis
MAX_OUTPUT_TOKENS = 1500

REGLES_AGENT = """
MODE AGENT — règles supplémentaires impératives :
1. Avant toute affirmation, appelle rechercher_cgi. Tu ne t'appuies QUE sur les articles
   renvoyés par cet outil, jamais sur tes connaissances générales.
2. Tu ne fais jamais de calcul de tête : utilise calculer, en indiquant dans "sources"
   les numéros des articles d'où proviennent les taux, seuils et montants employés.
3. Avant de répondre, vérifie avec verifier_citation chaque taux, délai ou seuil que tu
   cites (l'extrait doit être un passage court et exact de l'article).
4. Si les articles trouvés ne permettent pas de répondre, dis-le clairement.
5. Dans la réponse finale, présente le détail du calcul étape par étape lorsqu'un
   calcul a été effectué, et cite les articles appliqués.
"""


# ---------------------------------------------------------------------------
# Déclaration des outils pour Gemini
# ---------------------------------------------------------------------------

S, T = types.Schema, types.Type

OUTILS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="rechercher_cgi",
        description="Recherche les articles du CGI 2026 pertinents pour une question. "
                    "Peut être appelé plusieurs fois avec des formulations différentes.",
        parameters=S(type=T.OBJECT, properties={
            "question": S(type=T.STRING, description="Requête de recherche, précise et ciblée."),
            "k": S(type=T.INTEGER, description="Nombre d'articles souhaités (1 à 8)."),
        }, required=["question"]),
    ),
    types.FunctionDeclaration(
        name="calculer",
        description="Effectue un calcul arithmétique exact (+, -, *, /, parenthèses, %). "
                    "Exemple : '25000000 * 30%'.",
        parameters=S(type=T.OBJECT, properties={
            "expression": S(type=T.STRING, description="Expression numérique à évaluer."),
            "objet": S(type=T.STRING, description="Ce que représente le calcul (ex. 'IS dû')."),
            "sources": S(type=T.ARRAY, items=S(type=T.STRING),
                         description="Numéros des articles fondant les taux et montants utilisés."),
        }, required=["expression", "objet"]),
    ),
    types.FunctionDeclaration(
        name="verifier_citation",
        description="Vérifie qu'un article existe dans le CGI 2026 et qu'il contient bien l'extrait cité.",
        parameters=S(type=T.OBJECT, properties={
            "article": S(type=T.STRING, description="Numéro de l'article (ex. '120' ou '72 bis')."),
            "extrait": S(type=T.STRING, description="Passage court et exact à retrouver (taux, délai, seuil)."),
        }, required=["article", "extrait"]),
    ),
])


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

SUFFIXES = sorted([
    "bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "nonies",
    "decies", "undecies", "duodecies", "terdecies", "quaterdecies", "quindecies",
    "sexdecies", "septdecies", "octodecies", "novodecies", "vicies",
], key=len, reverse=True)

RE_ARTICLE = re.compile(
    r"\b(?:articles?|art\.)\s+(\d+)\s*(" + "|".join(SUFFIXES) + r")?\b",
    re.IGNORECASE,
)


def normaliser_texte(t):
    """Minuscules, sans accents, espaces et séparateurs de milliers unifiés."""
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"(?<=\d)[ .](?=\d{3}\b)", "", t)   # 1 000 000 / 1.000.000 -> 1000000
    t = re.sub(r"\s+%", "%", t)                     # 15 % -> 15%
    return re.sub(r"\s+", " ", t).strip()


def normaliser_numero(n):
    """'Article 72 bis' / 'art. 72BIS' -> '72bis' (format de cgi_articles.article_id)."""
    n = normaliser_texte(n)
    n = re.sub(r"^(articles?|art\.?)\s*", "", n)
    return n.replace(" ", "")


_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.UAdd: operator.pos, ast.USub: operator.neg,
}


def _evaluer(noeud):
    if isinstance(noeud, ast.Expression):
        return _evaluer(noeud.body)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)) \
            and not isinstance(noeud.value, bool):
        return noeud.value
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPS:
        return _OPS[type(noeud.op)](_evaluer(noeud.left), _evaluer(noeud.right))
    if isinstance(noeud, ast.UnaryOp) and type(noeud.op) in _OPS:
        return _OPS[type(noeud.op)](_evaluer(noeud.operand))
    raise ValueError("élément non autorisé dans l'expression")


def calcul_sur(expression):
    """Évaluation sûre : aucun nom, aucune fonction, aucun exposant."""
    e = str(expression)
    if len(e) > 300:
        raise ValueError("expression trop longue")
    e = re.sub(r"(?<=\d)[\s\u00a0\u202f](?=\d)", "", e)  # espaces de milliers
    e = e.replace(",", ".").replace("×", "*").replace("÷", "/")
    e = e.replace("%", "/100")
    return _evaluer(ast.parse(e, mode="eval"))


def articles_cites(texte):
    return {f"{num}{(suf or '').lower()}" for num, suf in RE_ARTICLE.findall(texte or "")}


# ---------------------------------------------------------------------------
# Routage : l'agent ne sert que les questions où il apporte une vraie valeur
# ---------------------------------------------------------------------------

MOTS_AGENT = (
    "calcul", "montant", "combien", "penalit", "amende", "interet de retard",
    "interets de retard", "liquid", "fcfa", "f cfa", "million", "milliard",
)
RE_MONTANT = re.compile(r"\d[\d .]{4,}\d")  # ex. 1 500 000 / 25000000


def doit_utiliser_agent(question):
    q = normaliser_texte(question)
    return any(m in q for m in MOTS_AGENT) or bool(RE_MONTANT.search(question or ""))


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class FiscaAgent:
    """Une instance par question (état propre à la requête)."""

    def __init__(self, client, db, model, consignes=""):
        self.client = client
        self.db = db
        self.model = model
        self.systeme = (consignes or "") + "\n" + REGLES_AGENT
        self._outils = {
            "rechercher_cgi": self._outil_rechercher,
            "calculer": self._outil_calculer,
            "verifier_citation": self._outil_verifier,
        }

    # --- outils -----------------------------------------------------------

    def _outil_rechercher(self, s, args):
        question = str(args.get("question", "")).strip()
        if not question:
            return {"erreur": "Question de recherche vide."}
        try:
            k = max(1, min(int(args.get("k") or K_DEFAUT), K_MAX))
        except (TypeError, ValueError):
            k = K_DEFAUT

        question_elargie = elargir_question(question)
        vecteur = embed_question(self.client, question_elargie)
        pivots = recherche_hybride(self.db, vecteur, question_elargie, top_k=k)
        lies = expand_via_refs(self.db, pivots) if pivots else []

        resultats = []
        for a in pivots + lies:
            s["articles"][normaliser_numero(a.article_id)] = a.text or ""
            resultats.append({
                "article": a.article_id,
                "chapitre": a.chapitre_titre,
                "role": a.role if a.role == "pivot" else f"lié ({a.type_relation or 'renvoi'})",
                "texte": (a.text or "")[:TEXTE_MAX],
            })
        if not resultats:
            return {"resultats": [], "note": "Aucun article trouvé. Reformulez ou concluez à l'absence de base légale trouvée."}
        return {"resultats": resultats}

    def _outil_calculer(self, s, args):
        sources = [str(x) for x in (args.get("sources") or [])]
        non_consultes = [x for x in sources if normaliser_numero(x) not in s["articles"]]
        if non_consultes:
            return {"erreur": "Articles non consultés : " + ", ".join(non_consultes)
                              + ". Recherchez-les avant de les utiliser dans un calcul."}
        try:
            valeur = calcul_sur(args.get("expression", ""))
        except (ValueError, SyntaxError, ZeroDivisionError) as e:
            return {"erreur": f"Expression invalide : {e}"}
        entree = {
            "objet": args.get("objet", ""),
            "expression": args.get("expression", ""),
            "resultat": round(valeur, 2),
            "resultat_arrondi_fcfa": round(valeur),
            "sources": sources,
        }
        s["calculs"].append(entree)
        if not sources:
            s["alertes"].append(f"Calcul « {entree['objet']} » effectué sans article source indiqué.")
        return entree

    def _lire_article(self, article_id):
        cur = self.db.cursor()
        cur.execute("SELECT text FROM cgi_articles WHERE article_id = %s", (article_id,))
        ligne = cur.fetchone()
        return ligne["text"] if ligne else None

    def _outil_verifier(self, s, args):
        brut = str(args.get("article", ""))
        cle = normaliser_numero(brut)
        texte = s["articles"].get(cle)
        if texte is None:
            texte = self._lire_article(cle)
        if texte is None:
            return {"article_existe": False,
                    "conclusion": "Article introuvable dans le CGI 2026 : ne pas le citer."}
        s["articles"].setdefault(cle, texte)
        extrait = normaliser_texte(args.get("extrait", ""))
        trouve = bool(extrait) and extrait in normaliser_texte(texte)
        s["verifications"].append({"article": cle, "extrait": args.get("extrait", ""), "conforme": trouve})
        return {
            "article_existe": True,
            "extrait_trouve": trouve,
            "conclusion": "Citation conforme." if trouve
                          else "Extrait absent du texte de l'article : reformuler ou retirer l'affirmation.",
        }

    # --- boucle -----------------------------------------------------------

    def _config(self, sans_outils):
        return types.GenerateContentConfig(
            system_instruction=self.systeme,
            temperature=0.1,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            tools=[OUTILS],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                mode="NONE" if sans_outils else "AUTO")),
        )

    def _contenus_initiaux(self, question, historique):
        contenus = []
        for q, r in (historique or [])[-HISTORIQUE_MAX:]:
            contenus.append(types.Content(role="user", parts=[types.Part(text=str(q))]))
            contenus.append(types.Content(role="model", parts=[types.Part(text=str(r)[:1500])]))
        contenus.append(types.Content(role="user", parts=[types.Part(text=question)]))
        return contenus

    def repondre(self, question, historique=None):
        """Renvoie un dict de résultat, ou None si l'agent doit rendre la main."""
        s = {"articles": {}, "calculs": [], "verifications": [], "alertes": [], "trace": []}
        contenus = self._contenus_initiaux(question, historique)
        debut = time.time()

        for i in range(MAX_APPELS_MODELE):
            ecoule = time.time() - debut
            if ecoule > DUREE_MAX_S:
                print(f"[Fisca AI][Agent] Durée maximale dépassée ({ecoule:.0f}s) — repli sur le RAG.")
                return None
            conclure = i == MAX_APPELS_MODELE - 1 or ecoule > DUREE_FORCAGE_S

            reponse = self.client.models.generate_content(
                model=self.model, contents=contenus, config=self._config(sans_outils=conclure))
            appels = reponse.function_calls or []

            if not appels:
                return self._finaliser(getattr(reponse, "text", "") or "", s, i + 1, debut)

            contenus.append(reponse.candidates[0].content)
            parties = []
            for appel in appels:
                args = dict(appel.args or {})
                fonction = self._outils.get(appel.name)
                try:
                    resultat = fonction(s, args) if fonction else {"erreur": "Outil inconnu."}
                except Exception as e:  # une erreur d'outil ne doit pas faire tomber la requête
                    print(f"[Fisca AI][Agent] Échec de l'outil {appel.name} ({type(e).__name__}: {e}).")
                    resultat = {"erreur": "Échec technique de l'outil."}
                s["trace"].append({"etape": i + 1, "outil": appel.name, "args": args})
                parties.append(types.Part.from_function_response(name=appel.name, response=resultat))
            contenus.append(types.Content(role="user", parts=parties))

        return None

    # --- contrôle final déterministe ----------------------------------------

    def _finaliser(self, texte, s, nb_appels, debut):
        if not texte.strip():
            return None
        cites = articles_cites(texte)
        non_consultes = sorted(c for c in cites if c not in s["articles"])
        if non_consultes:
            s["alertes"].append("Articles cités sans avoir été consultés : " + ", ".join(non_consultes))
        if any(not v["conforme"] for v in s["verifications"]):
            s["alertes"].append("Au moins une citation n'a pas été retrouvée dans le texte de l'article.")

        return {
            "reponse": texte.strip(),
            "articles_consultes": sorted(s["articles"].keys()),
            "articles_cites": sorted(cites),
            "articles_non_consultes": non_consultes,
            "calculs": s["calculs"],
            "verifications": s["verifications"],
            "alertes": s["alertes"],
            "trace": s["trace"],
            "appels_modele": nb_appels,
            "duree_s": round(time.time() - debut, 2),
        }
