"""
llm.py — Point d'entrée UNIQUE de Fisca AI vers les modèles d'IA.

Tout le reste du projet (rag.py, engine.py, agent.py) passe par ce fichier
et ne connaît plus aucun fournisseur. Pour changer de fournisseur, seul ce
fichier est à modifier : on ajoute une branche pour le nouveau fournisseur
dans chacune des fonctions ci-dessous.

Fonctions offertes au reste du projet :
  - disponible()                 : l'IA est-elle configurée ?
  - rediger(...)                 : générer un texte (réponse, normalisation, reranking…)
  - rediger_avec_file_search(...) : ancien chemin File Search (propre à Gemini)
  - vectoriser_question(texte)   : embedding d'une question (recherche pgvector)
  - vectoriser_document(...)     : embedding d'un article (indexation)
  - SessionOutils                : conversation avec outils, pour les agents

Variables d'environnement (Render) :
  LLM_FOURNISSEUR        fournisseur de rédaction et des agents (défaut : gemini)
  LLM_MODELE             modèle de rédaction (défaut : GEMINI_MODEL, puis gemini-3.6-flash)
  EMBEDDING_FOURNISSEUR  fournisseur des vecteurs (défaut : gemini). Le garder sur
                         gemini lors d'une migration évite de régénérer toute la base :
                         des vecteurs produits par deux modèles différents ne sont pas
                         comparables entre eux.
"""

import os

FOURNISSEUR = os.environ.get("LLM_FOURNISSEUR", "gemini").strip().lower()
FOURNISSEUR_EMBEDDING = os.environ.get("EMBEDDING_FOURNISSEUR", "gemini").strip().lower()
MODELE = os.environ.get("LLM_MODELE") or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

TIMEOUT_DEFAUT_S = 35

# Doivent correspondre à la base existante (schema.sql, generer_embeddings.py)
EMBEDDING_MODELE = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 1536


class FournisseurNonPrisEnCharge(Exception):
    """Le fournisseur configuré n'est pas (encore) implémenté dans llm.py."""


def _non_pris_en_charge(fournisseur, fonction):
    return FournisseurNonPrisEnCharge(
        f"Le fournisseur « {fournisseur} » n'est pas encore pris en charge par llm.{fonction}()."
    )


# ===========================================================================
# GEMINI
# ===========================================================================

_client_gemini = None


def _gemini():
    """Client Gemini unique, créé au premier usage. None si la clé est absente."""
    global _client_gemini
    if _client_gemini is None:
        cle = os.environ.get("GEMINI_API_KEY")
        if not cle:
            return None
        from google import genai
        from google.genai import types
        _client_gemini = genai.Client(
            api_key=cle,
            http_options=types.HttpOptions(timeout=TIMEOUT_DEFAUT_S * 1000),
        )
    return _client_gemini


def _exiger_gemini():
    client = _gemini()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY absente : Gemini n'est pas configuré.")
    return client


def _contenus_gemini(historique, texte):
    """Échanges précédents (question, réponse) puis le nouveau message."""
    from google.genai import types
    contenus = []
    for question_precedente, reponse_precedente in historique or []:
        contenus.append(types.Content(role="user", parts=[types.Part(text=str(question_precedente))]))
        contenus.append(types.Content(role="model", parts=[types.Part(text=str(reponse_precedente))]))
    contenus.append(types.Content(role="user", parts=[types.Part(text=texte)]))
    return contenus


def _schema_gemini(schema):
    """Schéma JSON neutre (types en minuscules) -> types.Schema de Gemini."""
    from google.genai import types
    kw = {"type": getattr(types.Type, str(schema.get("type", "object")).upper())}
    if schema.get("description"):
        kw["description"] = schema["description"]
    if schema.get("properties"):
        kw["properties"] = {k: _schema_gemini(v) for k, v in schema["properties"].items()}
    if schema.get("required"):
        kw["required"] = list(schema["required"])
    if schema.get("items"):
        kw["items"] = _schema_gemini(schema["items"])
    return types.Schema(**kw)


def _outils_gemini(outils):
    from google.genai import types
    declarations = []
    for o in outils:
        parametres = o.get("parametres") or {}
        declarations.append(types.FunctionDeclaration(
            name=o["nom"],
            description=o.get("description", ""),
            parameters=_schema_gemini(parametres) if parametres.get("properties") else None,
        ))
    return types.Tool(function_declarations=declarations)


# ===========================================================================
# FONCTIONS PUBLIQUES
# ===========================================================================

def disponible():
    """True si le fournisseur de rédaction est configuré et utilisable."""
    try:
        if FOURNISSEUR == "gemini":
            return _gemini() is not None
    except Exception as e:
        print(f"[Fisca AI][LLM] Fournisseur « {FOURNISSEUR} » indisponible ({type(e).__name__}: {e}).")
    return False


def client_brut():
    """Client natif du fournisseur (ou None). Réservé aux scripts annexes qui
    n'ont pas encore été convertis ; le code de production ne doit pas l'utiliser
    pour appeler le modèle directement."""
    return _gemini() if FOURNISSEUR == "gemini" and disponible() else None


def rediger(prompt, *, systeme=None, historique=None, modele=None,
            max_output_tokens=1500, timeout_secondes=TIMEOUT_DEFAUT_S, format_json=False):
    """Génère un texte. Renvoie "" si le modèle ne répond rien ; lève une
    exception en cas d'erreur (délai dépassé, quota…) : c'est à l'appelant de
    décider du repli, comme avant."""
    if FOURNISSEUR == "gemini":
        from google.genai import types
        client = _exiger_gemini()
        config = dict(
            max_output_tokens=max_output_tokens,
            http_options=types.HttpOptions(timeout=timeout_secondes * 1000),
        )
        if systeme:
            config["system_instruction"] = systeme
        if format_json:
            config["response_mime_type"] = "application/json"
        reponse = client.models.generate_content(
            model=modele or MODELE,
            contents=_contenus_gemini(historique, prompt) if historique else prompt,
            config=types.GenerateContentConfig(**config),
        )
        return getattr(reponse, "text", "") or ""
    raise _non_pris_en_charge(FOURNISSEUR, "rediger")


def rediger_avec_file_search(question, *, store, systeme=None, historique=None, modele=None,
                             max_output_tokens=1500, timeout_secondes=TIMEOUT_DEFAUT_S):
    """Ancien chemin « File Search » : la recherche documentaire est faite par
    Gemini lui-même. Propre à Gemini, sans équivalent direct ailleurs : avec un
    autre fournisseur, lève FournisseurNonPrisEnCharge (l'appelant bascule alors
    sur le moteur suivant)."""
    if FOURNISSEUR == "gemini":
        from google.genai import types
        client = _exiger_gemini()
        config = dict(
            max_output_tokens=max_output_tokens,
            http_options=types.HttpOptions(timeout=timeout_secondes * 1000),
            tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store]))],
        )
        if systeme:
            config["system_instruction"] = systeme
        reponse = client.models.generate_content(
            model=modele or MODELE,
            contents=_contenus_gemini(historique, question),
            config=types.GenerateContentConfig(**config),
        )
        return getattr(reponse, "text", "") or ""
    raise _non_pris_en_charge(FOURNISSEUR, "rediger_avec_file_search")


def vectoriser_question(texte):
    """Embedding d'une QUESTION (task_type RETRIEVAL_QUERY), pour pgvector."""
    if FOURNISSEUR_EMBEDDING == "gemini":
        from google.genai import types
        resultat = _exiger_gemini().models.embed_content(
            model=EMBEDDING_MODELE,
            contents=texte,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )
        return resultat.embeddings[0].values
    raise _non_pris_en_charge(FOURNISSEUR_EMBEDDING, "vectoriser_question")


def vectoriser_document(texte, titre=None):
    """Embedding d'un ARTICLE (task_type RETRIEVAL_DOCUMENT), pour l'indexation."""
    if FOURNISSEUR_EMBEDDING == "gemini":
        from google.genai import types
        config = dict(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=EMBEDDING_DIMENSIONS)
        if titre:
            config["title"] = titre
        resultat = _exiger_gemini().models.embed_content(
            model=EMBEDDING_MODELE, contents=texte, config=types.EmbedContentConfig(**config),
        )
        return resultat.embeddings[0].values
    raise _non_pris_en_charge(FOURNISSEUR_EMBEDDING, "vectoriser_document")


# ===========================================================================
# CONVERSATION AVEC OUTILS (agents)
# ===========================================================================

class AppelOutil:
    """Un outil que le modèle demande d'exécuter."""

    def __init__(self, nom, args, identifiant=None):
        self.nom = nom
        self.args = args
        self.identifiant = identifiant  # utile pour les fournisseurs qui numérotent les appels


class ReponseModele:
    def __init__(self, texte="", appels=None, tokens_entree=0, tokens_sortie=0):
        self.texte = texte
        self.appels = appels or []
        self.tokens_entree = tokens_entree
        self.tokens_sortie = tokens_sortie


class SessionOutils:
    """Conversation entre un agent et le modèle, indépendante du fournisseur.

    Les outils sont décrits dans un format neutre :
        {"nom": "calculer", "description": "...",
         "parametres": {"type": "object", "properties": {...}, "required": [...]}}

    Usage :
        session = SessionOutils(systeme, outils, question, historique)
        reponse = session.envoyer()                 # le modèle répond ou demande des outils
        session.ajouter_resultats([(appel, {...})])  # on lui renvoie les résultats
        reponse = session.envoyer(conclure=True)    # dernier tour : réponse forcée, sans outils
    """

    def __init__(self, systeme, outils, question, historique=None, *, modele=None,
                 max_output_tokens=1500, temperature=0.1, timeout_secondes=TIMEOUT_DEFAUT_S):
        self.systeme = systeme
        self.outils = outils
        self.modele = modele or MODELE
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.timeout_secondes = timeout_secondes

        if FOURNISSEUR == "gemini":
            self._contenus = _contenus_gemini(historique, question)
            self._outils_natifs = _outils_gemini(outils)
        else:
            raise _non_pris_en_charge(FOURNISSEUR, "SessionOutils")

    def envoyer(self, conclure=False):
        if FOURNISSEUR == "gemini":
            from google.genai import types
            config = types.GenerateContentConfig(
                system_instruction=self.systeme,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                http_options=types.HttpOptions(timeout=self.timeout_secondes * 1000),
                tools=[self._outils_natifs],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                    mode="NONE" if conclure else "AUTO")),
            )
            reponse = _exiger_gemini().models.generate_content(
                model=self.modele, contents=self._contenus, config=config)

            usage = getattr(reponse, "usage_metadata", None)
            appels_natifs = reponse.function_calls or []
            if appels_natifs and reponse.candidates:
                self._contenus.append(reponse.candidates[0].content)
            return ReponseModele(
                texte="" if appels_natifs else (getattr(reponse, "text", "") or ""),
                appels=[AppelOutil(a.name, dict(a.args or {}), getattr(a, "id", None)) for a in appels_natifs],
                tokens_entree=(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0,
                tokens_sortie=(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0,
            )
        raise _non_pris_en_charge(FOURNISSEUR, "SessionOutils.envoyer")

    def ajouter_resultats(self, resultats):
        """resultats : liste de (AppelOutil, dict de résultat)."""
        if FOURNISSEUR == "gemini":
            from google.genai import types
            parties = [types.Part.from_function_response(name=appel.nom, response=resultat)
                       for appel, resultat in resultats]
            self._contenus.append(types.Content(role="user", parts=parties))
            return
        raise _non_pris_en_charge(FOURNISSEUR, "SessionOutils.ajouter_resultats")
