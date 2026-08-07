# -*- coding: utf-8 -*-
"""
Fisca AI - serveur (PHASE TEST, sans API OpenAI, avec base PostgreSQL Render).

Ce serveur a besoin d'une variable d'environnement DATABASE_URL, fournie
automatiquement par Render quand tu relies ta base PostgreSQL a ce
service (onglet Environment). Sans elle, le serveur refuse de demarrer
et l'affiche clairement dans les logs.
"""
import hashlib
import hmac
import os
import secrets
import time
from datetime import date, datetime, timedelta

import psycopg2
import psycopg2.extras
import requests
from flask import Flask, g, jsonify, request, send_from_directory, session

from cache_data import DOCUMENT_ACTIF, SUGGESTIONS
from catalogue import CATALOGUE, DOCUMENTS_TELECHARGEABLES, ABONNEMENTS, WHATSAPP_NUMERO, lien_whatsapp_commande
from payments import initier_paiement
from engine import repondre
from calendrier_fiscal_data import get_calendrier_par_mois, DELAIS_EVENEMENTS, MOIS_LABELS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUOTA_GRATUIT_PAR_JOUR = 5
MOT_DE_PASSE_LONGUEUR_MIN = 8

# ---------------------------------------------------------------------------
# Integration WhatsApp Business API (Meta Cloud API). WHATSAPP_VERIFY_TOKEN
# est un mot de passe que TU choisis toi-meme (pas fourni par Meta) - a
# recopier a l'identique dans le tableau de bord Meta au moment de coller
# l'URL du webhook. Les deux autres valeurs viennent de Meta (Etape 1 pour
# l'instant, en attendant le token permanent apres verification).
# ---------------------------------------------------------------------------
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "fisca-ai-verify")
WHATSAPP_API_VERSION = "v21.0"

COMPTES_ILLIMITES = {
    c.strip().lower()
    for c in os.environ.get("COMPTES_ILLIMITES", "").split(",")
    if c.strip()
}


def est_illimite(user):
    return user["contact"].strip().lower() in COMPTES_ILLIMITES

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app = Flask(__name__, static_folder="static", static_url_path="")

_secret_fixe = os.environ.get("FISCA_AI_SECRET")
if not _secret_fixe:
    print(
        "ATTENTION : FISCA_AI_SECRET n'est pas defini sur Render. "
        "Un secret temporaire est genere a chaque redemarrage, ce qui "
        "deconnecte TOUS les utilisateurs a chaque redeploiement. "
        "Ajoute FISCA_AI_SECRET dans Environment sur Render pour corriger ca."
    )
app.secret_key = _secret_fixe or secrets.token_hex(32)

# Cookies de session plus surs : uniquement envoyes en HTTPS, jamais
# lisibles par du JavaScript, et non envoyes lors de navigations
# provenant d'un autre site (limite certaines attaques cross-site).
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


@app.after_request
def ajouter_entetes_securite(response):
    """En-tetes de securite standards, purement defensifs - n'affectent
    pas le fonctionnement normal du site."""
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Protection contre les essais repetes de mot de passe (brute force).
# Stockage en memoire - suffisant en phase test (un seul worker Render,
# voir WEB_CONCURRENCY=1 dans les logs). Si un jour plusieurs workers
# tournent en parallele, il faudra deplacer ce compteur en base de
# donnees ou vers un service comme Redis pour qu'il reste partage entre
# eux.
# ---------------------------------------------------------------------------
MAX_TENTATIVES_CONNEXION = 5
DUREE_BLOCAGE_SECONDES = 15 * 60  # 15 minutes
_tentatives_echouees = {}  # contact -> [timestamps des echecs recents]


def _connexion_bloquee(contact):
    maintenant = time.time()
    historique = _tentatives_echouees.get(contact, [])
    historique = [t for t in historique if maintenant - t < DUREE_BLOCAGE_SECONDES]
    _tentatives_echouees[contact] = historique
    return len(historique) >= MAX_TENTATIVES_CONNEXION


def _enregistrer_echec_connexion(contact):
    _tentatives_echouees.setdefault(contact, []).append(time.time())


def _reinitialiser_tentatives(contact):
    _tentatives_echouees.pop(contact, None)


# Meme principe de blocage, applique aux demandes de code de
# reinitialisation - sans lui, rien n'empechait de redemander un code
# des dizaines de fois de suite pour le meme contact.
MAX_DEMANDES_REINITIALISATION = 5
_demandes_reinitialisation = {}  # contact -> [timestamps]


def _reinitialisation_bloquee(contact):
    maintenant = time.time()
    historique = _demandes_reinitialisation.get(contact, [])
    historique = [t for t in historique if maintenant - t < DUREE_BLOCAGE_SECONDES]
    _demandes_reinitialisation[contact] = historique
    return len(historique) >= MAX_DEMANDES_REINITIALISATION


def _enregistrer_demande_reinitialisation(contact):
    _demandes_reinitialisation.setdefault(contact, []).append(time.time())


def get_db():
    if "db" not in g:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL n'est pas defini. Va dans Render > ton service "
                "fisca-ai > Environment, et ajoute DATABASE_URL avec "
                "l'Internal Database URL de ta base PostgreSQL."
            )
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    if not DATABASE_URL:
        print("ATTENTION : DATABASE_URL absent, la base ne sera pas initialisee.")
        return
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL,
            contact TEXT UNIQUE NOT NULL,
            sel TEXT NOT NULL,
            mot_de_passe_hash TEXT NOT NULL,
            cree_le TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            question_brute TEXT NOT NULL,
            question_comprise TEXT,
            reponse TEXT NOT NULL,
            source TEXT,
            niveau INTEGER,
            cree_le TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            question_log_id INTEGER NOT NULL REFERENCES questions_log(id),
            type TEXT NOT NULL,
            cree_le TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS commandes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            produit_id TEXT NOT NULL,
            nom_produit TEXT NOT NULL,
            statut TEXT NOT NULL DEFAULT 'en_attente',
            cree_le TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS paiements (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            type TEXT NOT NULL,
            reference_id TEXT NOT NULL,
            description TEXT NOT NULL,
            montant_fcfa INTEGER NOT NULL,
            fournisseur TEXT,
            reference_externe TEXT,
            statut TEXT NOT NULL DEFAULT 'en_attente',
            cree_le TIMESTAMP NOT NULL,
            paye_le TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reinitialisations_mdp (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            code TEXT NOT NULL,
            cree_le TIMESTAMP NOT NULL,
            expire_le TIMESTAMP NOT NULL,
            utilise BOOLEAN NOT NULL DEFAULT FALSE
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()
    print("Base PostgreSQL initialisee (tables verifiees/creees).")


def hacher_mot_de_passe(mot_de_passe, sel):
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel.encode("utf-8"), 100_000).hex()


# ---------------------------------------------------------------------------
# Reinitialisation de mot de passe - solution temporaire "manuelle" en
# attendant que l'envoi automatique par WhatsApp Business API soit pret
# (une fois le compte Meta Business valide). Le code est genere et
# stocke cote serveur, mais c'est l'administrateur (toi) qui le
# transmet manuellement via WhatsApp pour l'instant - voir /admin/codes.
# ---------------------------------------------------------------------------
DUREE_VALIDITE_CODE_MINUTES = 15


def generer_code_reinitialisation():
    return f"{secrets.randbelow(1_000_000):06d}"


def lien_whatsapp_demande_code(contact):
    """Lien pre-rempli vers TON WhatsApp (WHATSAPP_NUMERO), pour que la
    personne te signale sa demande de reinitialisation."""
    texte = f"Bonjour, j'ai oublie mon mot de passe Fisca AI. Mon contact : {contact}"
    texte_encode = texte.replace(" ", "%20").replace(",", "%2C").replace(".", "%2E").replace(":", "%3A")
    return f"https://wa.me/{WHATSAPP_NUMERO}?text={texte_encode}"


# ---------------------------------------------------------------------------
# Fonctions WhatsApp - envoi de message, identification automatique par
# numero (pas de mot de passe necessaire, WhatsApp garantit deja
# l'identite), et detection d'une intention d'abonnement.
# ---------------------------------------------------------------------------
def envoyer_message_whatsapp(numero_destinataire, texte):
    """Envoie un message texte via l'API WhatsApp. Ne fait jamais planter
    l'appelant : retourne simplement False et log l'erreur en cas de
    souci (cle absente, echec reseau, etc.)."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print("[WhatsApp] WHATSAPP_ACCESS_TOKEN ou WHATSAPP_PHONE_NUMBER_ID manquant - message non envoye.")
        return False
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": numero_destinataire,
        "type": "text",
        "text": {"body": texte[:4096]},  # WhatsApp limite la taille d'un message
    }
    try:
        reponse = requests.post(url, headers=headers, json=payload, timeout=10)
        if reponse.status_code >= 400:
            print(f"[WhatsApp] Echec de l'envoi ({reponse.status_code}) : {reponse.text}")
            return False
        return True
    except Exception as e:
        print(f"[WhatsApp] Erreur reseau lors de l'envoi : {e}")
        return False


def utilisateur_whatsapp(numero):
    """Trouve le compte lie a ce numero WhatsApp, ou le cree
    automatiquement s'il n'existe pas encore - sans mot de passe,
    puisque WhatsApp a deja garanti l'identite du numero. Si ce numero
    correspond a un compte deja cree sur le site (meme contact), c'est
    exactement le meme compte qui est utilise - meme quota, meme
    historique."""
    contact = numero.strip().lower()
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE contact = %s", (contact,))
    user = cur.fetchone()
    if user:
        return user

    sel = secrets.token_hex(16)
    mot_de_passe_genere = secrets.token_hex(16)  # jamais communique ni utilise directement
    hash_mdp = hacher_mot_de_passe(mot_de_passe_genere, sel)
    cur.execute(
        """INSERT INTO users (nom, contact, sel, mot_de_passe_hash, cree_le)
           VALUES (%s, %s, %s, %s, %s) RETURNING *""",
        (f"Utilisateur WhatsApp ({numero[-4:]})", contact, sel, hash_mdp, datetime.now()),
    )
    user = cur.fetchone()
    db.commit()
    return user


MOTS_CLES_ABONNEMENT = {"abonnement", "abonnements", "abonner", "s'abonner", "souscrire", "premium", "payant"}

# Sur WhatsApp, seule la formule Standard est proposee (volontairement, pour
# rester simple au demarrage) - Expert reste disponible uniquement sur le
# site web. A elargir plus tard en ajoutant "expert" a cet ensemble.
PLANS_DISPONIBLES_WHATSAPP = {"standard"}


def intention_abonnement(texte):
    texte_normalise = texte.lower().strip()
    return any(mot in texte_normalise for mot in MOTS_CLES_ABONNEMENT)


def reponse_abonnement_whatsapp(texte, numero, user):
    """Gere la conversation d'abonnement en 2 temps : d'abord presenter
    la formule Standard (seule proposee sur WhatsApp), puis enregistrer
    la commande si la personne confirme avec 'OUI STANDARD'. Le paiement
    reste manuel (via MyNITA/iMoney) tant que ces fournisseurs ne sont
    pas branches - voir payments.py."""
    texte_normalise = texte.lower().strip()

    if texte_normalise == "oui expert":
        return (
            "La formule Expert Fiscal n'est pas proposee via WhatsApp pour "
            "le moment. Elle est disponible sur notre site web : "
            "https://fisca-ai.onrender.com (rubrique Bibliotheque > Abonnements)."
        )

    if texte_normalise == "oui standard":
        plan = next((p for p in ABONNEMENTS if p["id"] == "standard"), None)
        if not plan or not plan.get("disponible") or "standard" not in PLANS_DISPONIBLES_WHATSAPP:
            return (
                "Cette formule n'est pas encore disponible a la souscription. "
                "Contactez-nous directement pour plus d'informations."
            )
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """INSERT INTO commandes (user_id, produit_id, nom_produit, statut, cree_le)
               VALUES (%s, %s, %s, 'en_attente', %s)""",
            (user["id"], "abonnement-standard", f"Abonnement {plan['nom']}", datetime.now()),
        )
        db.commit()
        montant = f"{plan['prix_fcfa']:,} FCFA".replace(",", " ") if plan.get("prix_fcfa") else "un montant a confirmer"
        return (
            f"Commande enregistree pour l'abonnement {plan['nom']} ({montant}/mois).\n\n"
            f"Pour finaliser, envoyez {montant} via MyNITA ou iMoney au numero "
            f"{WHATSAPP_NUMERO}.\n\n"
            "Une fois le paiement effectue, repondez ici avec une capture d'ecran de "
            "votre recu de transaction pour confirmer. Nous verifierons et activerons "
            "votre compte des reception."
        )

    lignes = ["Voici notre formule d'abonnement disponible sur WhatsApp :", ""]
    for plan in ABONNEMENTS:
        if plan["id"] not in PLANS_DISPONIBLES_WHATSAPP or not plan.get("disponible"):
            continue
        prix = f"{plan['prix_fcfa']:,} FCFA/mois".replace(",", " ") if plan.get("prix_fcfa") else "prix a venir"
        lignes.append(f"{plan['nom'].upper()} ({prix}) : " + ", ".join(plan["avantages"]))
    lignes.append("")
    lignes.append("Pour confirmer, repondez : OUI STANDARD")
    lignes.append("(La formule Expert Fiscal est disponible sur notre site web : https://fisca-ai.onrender.com)")


def utilisateur_courant():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    return cur.fetchone()


def questions_posees_aujourdhui(user_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) as n FROM questions_log WHERE user_id = %s AND date(cree_le) = %s",
        (user_id, date.today()),
    )
    return cur.fetchone()["n"]


@app.route("/api/inscription", methods=["POST"])
def inscription():
    data = request.get_json(silent=True) or {}
    nom = (data.get("nom") or "").strip()
    contact = (data.get("contact") or "").strip().lower()
    mot_de_passe = data.get("mot_de_passe") or ""

    if not nom or not contact or len(mot_de_passe) < MOT_DE_PASSE_LONGUEUR_MIN:
        return jsonify({"erreur": f"Nom, contact et mot de passe ({MOT_DE_PASSE_LONGUEUR_MIN} caracteres minimum) sont requis."}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE contact = %s", (contact,))
    if cur.fetchone():
        return jsonify({"erreur": "Un compte existe deja avec ce contact."}), 409

    sel = secrets.token_hex(16)
    hash_mdp = hacher_mot_de_passe(mot_de_passe, sel)
    cur.execute(
        "INSERT INTO users (nom, contact, sel, mot_de_passe_hash, cree_le) VALUES (%s, %s, %s, %s, %s) RETURNING id, nom",
        (nom, contact, sel, hash_mdp, datetime.now()),
    )
    user = cur.fetchone()
    db.commit()
    session["user_id"] = user["id"]
    return jsonify({"ok": True, "nom": user["nom"]})


@app.route("/api/connexion", methods=["POST"])
def connexion():
    data = request.get_json(silent=True) or {}
    contact = (data.get("contact") or "").strip().lower()
    mot_de_passe = data.get("mot_de_passe") or ""

    if _connexion_bloquee(contact):
        return jsonify({
            "erreur": "Trop de tentatives incorrectes. Reessayez dans 15 minutes, ou reinitialisez votre mot de passe."
        }), 429

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE contact = %s", (contact,))
    user = cur.fetchone()
    if not user or hacher_mot_de_passe(mot_de_passe, user["sel"]) != user["mot_de_passe_hash"]:
        _enregistrer_echec_connexion(contact)
        return jsonify({"erreur": "Contact ou mot de passe incorrect."}), 401

    _reinitialiser_tentatives(contact)
    session["user_id"] = user["id"]
    return jsonify({"ok": True, "nom": user["nom"]})


@app.route("/api/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/session", methods=["GET"])
def etat_session():
    user = utilisateur_courant()
    if not user:
        return jsonify({"connecte": False, "document_actif": DOCUMENT_ACTIF, "suggestions": SUGGESTIONS})
    posees = questions_posees_aujourdhui(user["id"])
    if est_illimite(user):
        questions_restantes = "illimité"
    else:
        questions_restantes = max(0, QUOTA_GRATUIT_PAR_JOUR - posees)
    return jsonify(
        {
            "connecte": True,
            "nom": user["nom"],
            "questions_restantes": questions_restantes,
            "quota_total": QUOTA_GRATUIT_PAR_JOUR,
            "document_actif": DOCUMENT_ACTIF,
            "suggestions": SUGGESTIONS,
        }
    )


@app.route("/api/question", methods=["POST"])
def poser_question():
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Vous devez etre connecte pour poser une question."}), 401

    data = request.get_json(silent=True) or {}
    texte = (data.get("texte") or "").strip()
    if not texte:
        return jsonify({"erreur": "La question est vide."}), 400

    posees = questions_posees_aujourdhui(user["id"])
    illimite = est_illimite(user)
    if not illimite and posees >= QUOTA_GRATUIT_PAR_JOUR:
        return jsonify({"erreur": "quota_atteint", "message": "Vous avez atteint votre limite de questions pour aujourd'hui."}), 429

    resultat = repondre(texte)

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """INSERT INTO questions_log
           (user_id, question_brute, question_comprise, reponse, source, niveau, cree_le)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (
            user["id"],
            texte,
            resultat["question_comprise"],
            resultat["reponse"],
            resultat["source"],
            resultat["niveau"],
            datetime.now(),
        ),
    )
    id_question = cur.fetchone()["id"]
    db.commit()

    return jsonify(
        {
            "id_question": id_question,
            "reponse": resultat["reponse"],
            "source": resultat["source"],
            "verified": resultat["verified"],
            "niveau": resultat["niveau"],
            "questions_restantes": "illimité" if illimite else max(0, QUOTA_GRATUIT_PAR_JOUR - posees - 1),
        }
    )


@app.route("/api/retour", methods=["POST"])
def deposer_retour():
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Non connecte."}), 401

    data = request.get_json(silent=True) or {}
    id_question = data.get("id_question")
    type_retour = data.get("type")  # "utile" ou "erreur"
    if type_retour not in ("utile", "erreur") or not id_question:
        return jsonify({"erreur": "Requete invalide."}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO feedback (question_log_id, type, cree_le) VALUES (%s, %s, %s)",
        (id_question, type_retour, datetime.now()),
    )
    db.commit()
    return jsonify({"ok": True})


DOCUMENTS_BIBLIOTHEQUE = [
    {
        "id": "cgi2026",
        "titre": "Code General des Impots 2026",
        "auteur": "Republique du Niger",
        "type": "Texte legal",
        "description": "Extrait des articles du CGI 2026 relatifs a la facture certifiee et au systeme electronique certifie de facturation (SECeF).",
        "statut": "Integre",
    },
    {
        "id": "livre",
        "titre": "Comprendre la Facture Certifiee",
        "auteur": "Moutari Abdoulaye",
        "type": "Livre",
        "description": "Ouvrage de reference sur la facture certifiee au Niger : cadre juridique, technique, sanctions et cas pratiques.",
        "statut": "Integre",
    },
    {
        "id": "arrete473",
        "titre": "Arrete N°00473 du 20 novembre 2020",
        "auteur": "Ministere des Finances - DGI",
        "type": "Arrete",
        "description": "Conditions de commercialisation et de distribution des systemes electroniques certifies de facturation (SECeF) au Niger.",
        "statut": "Integre",
    },
    {
        "id": "arrete474",
        "titre": "Arrete N°00474 du 20 novembre 2020",
        "auteur": "Ministere des Finances - DGI",
        "type": "Arrete",
        "description": "Modalites d'utilisation des systemes electroniques de facturation et obligations des utilisateurs.",
        "statut": "Integre",
    },
]


@app.route("/api/bibliotheque", methods=["GET"])
def bibliotheque():
    return jsonify({"documents": DOCUMENTS_BIBLIOTHEQUE})


@app.route("/api/calendrier-fiscal", methods=["GET"])
def calendrier_fiscal():
    """Calendrier des echeances fiscales (CGI 2026), organise par mois +
    delais lies a un evenement. Route publique (pas besoin d'etre
    connecte), comme /api/bibliotheque."""
    calendrier = get_calendrier_par_mois()
    calendrier_json = {
        str(m): {"label": data["label"], "echeances": data["echeances"]}
        for m, data in calendrier.items()
    }
    return jsonify({
        "calendrier": calendrier_json,
        "delais_evenements": DELAIS_EVENEMENTS,
        "mois_labels": {str(k): v for k, v in MOIS_LABELS.items()},
    })


@app.route("/api/historique", methods=["GET"])
def historique():
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Non connecte."}), 401

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """SELECT id, question_brute, reponse, source, niveau, cree_le
           FROM questions_log WHERE user_id = %s
           ORDER BY cree_le DESC LIMIT 100""",
        (user["id"],),
    )
    lignes = cur.fetchall()

    aujourdhui = date.today()
    groupes = {}
    for ligne in lignes:
        cree_le = ligne["cree_le"]
        jour = cree_le.date() if hasattr(cree_le, "date") else aujourdhui
        if jour == aujourdhui:
            cle = "Aujourd'hui"
        elif (aujourdhui - jour).days == 1:
            cle = "Hier"
        elif (aujourdhui - jour).days <= 7:
            cle = "Cette semaine"
        else:
            cle = "Plus ancien"
        groupes.setdefault(cle, []).append(
            {
                "id": ligne["id"],
                "question": ligne["question_brute"],
                "reponse": ligne["reponse"],
                "source": ligne["source"],
                "trouve": ligne["niveau"] == 1,
                "date": cree_le.isoformat() if hasattr(cree_le, "isoformat") else str(cree_le),
            }
        )

    ordre = ["Aujourd'hui", "Hier", "Cette semaine", "Plus ancien"]
    resultat = [{"groupe": g, "questions": groupes[g]} for g in ordre if g in groupes]
    return jsonify({"historique": resultat})


@app.route("/api/profil", methods=["GET"])
def voir_profil():
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Non connecte."}), 401
    posees = questions_posees_aujourdhui(user["id"])
    cree_le = user["cree_le"]
    return jsonify(
        {
            "nom": user["nom"],
            "contact": user["contact"],
            "cree_le": cree_le.isoformat() if hasattr(cree_le, "isoformat") else str(cree_le),
            "questions_restantes": max(0, QUOTA_GRATUIT_PAR_JOUR - posees),
            "quota_total": QUOTA_GRATUIT_PAR_JOUR,
        }
    )


@app.route("/api/profil", methods=["POST"])
def modifier_profil():
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Non connecte."}), 401
    data = request.get_json(silent=True) or {}
    nouveau_nom = (data.get("nom") or "").strip()
    if not nouveau_nom:
        return jsonify({"erreur": "Le nom ne peut pas etre vide."}), 400
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE users SET nom = %s WHERE id = %s", (nouveau_nom, user["id"]))
    db.commit()
    return jsonify({"ok": True, "nom": nouveau_nom})


@app.route("/api/mot-de-passe", methods=["POST"])
def changer_mot_de_passe():
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Non connecte."}), 401
    data = request.get_json(silent=True) or {}
    ancien = data.get("ancien_mot_de_passe") or ""
    nouveau = data.get("nouveau_mot_de_passe") or ""

    if hacher_mot_de_passe(ancien, user["sel"]) != user["mot_de_passe_hash"]:
        return jsonify({"erreur": "Ancien mot de passe incorrect."}), 401
    if len(nouveau) < MOT_DE_PASSE_LONGUEUR_MIN:
        return jsonify({"erreur": f"Le nouveau mot de passe doit faire au moins {MOT_DE_PASSE_LONGUEUR_MIN} caracteres."}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE users SET mot_de_passe_hash = %s WHERE id = %s",
        (hacher_mot_de_passe(nouveau, user["sel"]), user["id"]),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/mot-de-passe/oublie", methods=["POST"])
def demander_reinitialisation():
    """Genere un code de reinitialisation valable 15 minutes. Repond
    toujours 'ok' meme si le contact n'existe pas, pour ne jamais
    reveler quels contacts ont un compte (bonne pratique de securite)."""
    data = request.get_json(silent=True) or {}
    contact = (data.get("contact") or "").strip().lower()
    lien_whatsapp = lien_whatsapp_demande_code(contact)

    if not contact:
        return jsonify({"erreur": "Merci d'indiquer votre contact."}), 400

    if _reinitialisation_bloquee(contact):
        return jsonify({"erreur": "Trop de demandes recentes pour ce contact. Reessayez dans 15 minutes."}), 429
    _enregistrer_demande_reinitialisation(contact)

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE contact = %s", (contact,))
    user = cur.fetchone()
    if user:
        code = generer_code_reinitialisation()
        expire_le = datetime.now() + timedelta(minutes=DUREE_VALIDITE_CODE_MINUTES)
        cur.execute(
            "INSERT INTO reinitialisations_mdp (user_id, code, cree_le, expire_le, utilise) VALUES (%s, %s, %s, %s, FALSE)",
            (user["id"], code, datetime.now(), expire_le),
        )
        db.commit()

    return jsonify({
        "ok": True,
        "message": "Si ce contact existe, un code a ete prepare. Contactez-nous sur WhatsApp pour le recevoir.",
        "lien_whatsapp": lien_whatsapp,
    })


@app.route("/api/mot-de-passe/reinitialiser", methods=["POST"])
def reinitialiser_avec_code():
    data = request.get_json(silent=True) or {}
    contact = (data.get("contact") or "").strip().lower()
    code = (data.get("code") or "").strip()
    nouveau = data.get("nouveau_mot_de_passe") or ""

    if len(nouveau) < MOT_DE_PASSE_LONGUEUR_MIN:
        return jsonify({"erreur": f"Le nouveau mot de passe doit faire au moins {MOT_DE_PASSE_LONGUEUR_MIN} caracteres."}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE contact = %s", (contact,))
    user = cur.fetchone()
    if not user:
        return jsonify({"erreur": "Code invalide ou expire."}), 400

    cur.execute(
        """SELECT * FROM reinitialisations_mdp
           WHERE user_id = %s AND code = %s AND utilise = FALSE AND expire_le > %s
           ORDER BY cree_le DESC LIMIT 1""",
        (user["id"], code, datetime.now()),
    )
    demande = cur.fetchone()
    if not demande:
        return jsonify({"erreur": "Code invalide ou expire."}), 400

    cur.execute(
        "UPDATE users SET mot_de_passe_hash = %s WHERE id = %s",
        (hacher_mot_de_passe(nouveau, user["sel"]), user["id"]),
    )
    cur.execute("UPDATE reinitialisations_mdp SET utilise = TRUE WHERE id = %s", (demande["id"],))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/paiement/initier", methods=["POST"])
def initier_le_paiement():
    """Initie un paiement (abonnement, livre ou formation). Si aucun
    fournisseur (MyNITA/iMoney) n'est encore configure, redirige
    automatiquement vers le circuit manuel WhatsApp deja fonctionnel -
    l'utilisateur n'est jamais bloque."""
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Vous devez etre connecte."}), 401

    data = request.get_json(silent=True) or {}
    type_paiement = data.get("type")  # "abonnement", "livre" ou "formation"
    reference_id = data.get("reference_id")
    montant_fcfa = data.get("montant_fcfa")
    description = data.get("description", "")

    if not type_paiement or not reference_id or not montant_fcfa:
        return jsonify({"erreur": "Requete de paiement incomplete."}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """INSERT INTO paiements (user_id, type, reference_id, description, montant_fcfa, statut, cree_le)
           VALUES (%s, %s, %s, %s, %s, 'en_attente', %s) RETURNING id""",
        (user["id"], type_paiement, reference_id, description, montant_fcfa, datetime.now()),
    )
    id_paiement = cur.fetchone()["id"]
    db.commit()

    resultat = initier_paiement(montant_fcfa, description, f"fiscaai-{id_paiement}")

    if resultat["ok"]:
        cur.execute(
            "UPDATE paiements SET fournisseur = %s WHERE id = %s",
            (resultat["fournisseur"], id_paiement),
        )
        db.commit()
        return jsonify({"ok": True, "mode": "en_ligne", "lien_paiement": resultat["lien_paiement"]})

    lien = lien_whatsapp_commande(description, user["nom"])
    return jsonify({"ok": True, "mode": "whatsapp", "lien_paiement": lien})


@app.route("/api/paiement/webhook/<fournisseur>", methods=["POST"])
def webhook_paiement(fournisseur):
    """Emplacement reserve pour recevoir les confirmations de paiement
    de MyNITA/iMoney. NON ACTIF tant que ces fournisseurs ne sont pas
    branches."""
    return jsonify({"recu": True, "note": "Webhook non actif - fournisseur non encore integre"}), 200


@app.route("/api/catalogue", methods=["GET"])
def catalogue():
    return jsonify(
        {
            "livres": CATALOGUE,
            "documents_telechargeables": DOCUMENTS_TELECHARGEABLES,
        }
    )


@app.route("/api/commande", methods=["POST"])
def passer_commande():
    user = utilisateur_courant()
    if not user:
        return jsonify({"erreur": "Vous devez etre connecte pour commander."}), 401

    data = request.get_json(silent=True) or {}
    produit_id = data.get("produit_id")
    produit = next((p for p in CATALOGUE if p["id"] == produit_id), None)
    if not produit:
        return jsonify({"erreur": "Produit introuvable."}), 404
    if not produit["disponible_a_la_vente"]:
        return jsonify({"erreur": "Ce produit n'est pas encore disponible a la vente."}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """INSERT INTO commandes (user_id, produit_id, nom_produit, statut, cree_le)
           VALUES (%s, %s, %s, 'en_attente', %s)""",
        (user["id"], produit_id, produit["titre"], datetime.now()),
    )
    db.commit()

    lien = lien_whatsapp_commande(produit["titre"], user["nom"])
    return jsonify({"ok": True, "lien_whatsapp": lien})


@app.route("/api/abonnements", methods=["GET"])
def abonnements():
    return jsonify({"abonnements": ABONNEMENTS})


@app.route("/telechargements/<nom_fichier>")
def telecharger_document(nom_fichier):
    dossier = os.path.join(app.static_folder, "telechargements")
    return send_from_directory(dossier, nom_fichier, as_attachment=True)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def _acces_admin_valide():
    """Verifie l'authentification HTTP Basic pour la page /admin.
    Comparaison a temps constant (hmac.compare_digest) pour eviter une
    attaque par mesure de temps."""
    mot_de_passe_attendu = os.environ.get("ADMIN_PASSWORD")
    if not mot_de_passe_attendu:
        return False, "ADMIN_PASSWORD n'est pas configure. Ajoute cette variable d'environnement sur Render pour activer cette page."
    auth = request.authorization
    if not auth or not hmac.compare_digest(auth.password or "", mot_de_passe_attendu):
        return False, None
    return True, None


@app.route("/admin")
def admin():
    """Page de consultation simple, protegee par identifiants HTTP Basic
    (le mot de passe ne transite donc plus jamais dans l'URL, ni dans
    l'historique du navigateur ou les journaux serveur).
    Usage : ouvrir /admin, le navigateur demande un identifiant/mot de
    passe - utilisateur libre (ex. "admin"), mot de passe = ADMIN_PASSWORD.
    """
    valide, message_config = _acces_admin_valide()
    if message_config:
        return message_config, 503
    if not valide:
        return (
            "Authentification requise.",
            401,
            {"WWW-Authenticate": 'Basic realm="Fisca AI Admin"'},
        )

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) as n FROM users")
    nb_users = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as n FROM questions_log")
    nb_questions = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as n FROM feedback WHERE type = 'utile'")
    nb_utile = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as n FROM feedback WHERE type = 'erreur'")
    nb_erreur = cur.fetchone()["n"]

    cur.execute("SELECT nom, contact, cree_le FROM users ORDER BY cree_le DESC LIMIT 50")
    users = cur.fetchall()

    cur.execute(
        """SELECT q.question_brute, q.question_comprise, q.reponse, q.niveau, q.cree_le, u.nom
           FROM questions_log q JOIN users u ON u.id = q.user_id
           ORDER BY q.cree_le DESC LIMIT 50"""
    )
    questions = cur.fetchall()

    def echapper(texte):
        if texte is None:
            return ""
        return (
            str(texte).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    lignes_users = "".join(
        f"<tr><td>{echapper(u['nom'])}</td><td>{echapper(u['contact'])}</td><td>{echapper(u['cree_le'])}</td></tr>"
        for u in users
    )
    lignes_questions = "".join(
        f"<tr><td>{echapper(q['nom'])}</td><td>{echapper(q['question_brute'])}</td>"
        f"<td>{echapper(q['question_comprise'])}</td><td>{'Trouvee' if q['niveau']==1 else 'Non trouvee'}</td>"
        f"<td>{echapper(q['cree_le'])}</td></tr>"
        for q in questions
    )

    html = f"""
    <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fisca AI - Admin</title>
    <style>
      body{{font-family:sans-serif; padding:16px; background:#FBF9F4; color:#172227;}}
      h1{{color:#0E2A3A;}} h2{{color:#0E2A3A; margin-top:28px;}}
      .stats{{display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px;}}
      .stat{{background:#fff; border:1px solid #E5DCC7; border-radius:10px; padding:12px 16px;}}
      .stat b{{display:block; font-size:22px; color:#E07A3F;}}
      table{{width:100%; border-collapse:collapse; background:#fff; font-size:13px;}}
      th, td{{border:1px solid #E5DCC7; padding:6px 8px; text-align:left; vertical-align:top;}}
      th{{background:#0E2A3A; color:#fff;}}
    </style></head><body>
    <h1>Fisca AI — Tableau de bord (phase test)</h1>
    <div class="stats">
      <div class="stat"><b>{nb_users}</b>Comptes créés</div>
      <div class="stat"><b>{nb_questions}</b>Questions posées</div>
      <div class="stat"><b>{nb_utile}</b>👍 Utile</div>
      <div class="stat"><b>{nb_erreur}</b>👎 Signalé</div>
    </div>
    <h2>Derniers comptes (50 max)</h2>
    <table><tr><th>Nom</th><th>Contact</th><th>Créé le</th></tr>{lignes_users}</table>
    <h2>Dernières questions (50 max)</h2>
    <table><tr><th>Utilisateur</th><th>Question posée</th><th>Comprise comme</th><th>Résultat</th><th>Date</th></tr>{lignes_questions}</table>
    </body></html>
    """
    return html


@app.route("/admin/codes")
def admin_codes():
    """Liste les demandes de reinitialisation en attente (code non
    utilise, pas encore expire), pour que tu puisses le transmettre
    manuellement via WhatsApp en attendant l'envoi automatique."""
    valide, message_config = _acces_admin_valide()
    if message_config:
        return message_config, 503
    if not valide:
        return (
            "Authentification requise.",
            401,
            {"WWW-Authenticate": 'Basic realm="Fisca AI Admin"'},
        )

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """SELECT r.code, r.cree_le, r.expire_le, u.nom, u.contact
           FROM reinitialisations_mdp r JOIN users u ON u.id = r.user_id
           WHERE r.utilise = FALSE AND r.expire_le > %s
           ORDER BY r.cree_le DESC""",
        (datetime.now(),),
    )
    demandes = cur.fetchall()

    def echapper(texte):
        if texte is None:
            return ""
        return str(texte).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lignes = "".join(
        f"<tr><td>{echapper(d['nom'])}</td><td>{echapper(d['contact'])}</td>"
        f"<td style='font-weight:700; font-size:18px; letter-spacing:2px;'>{echapper(d['code'])}</td>"
        f"<td>{echapper(d['expire_le'])}</td></tr>"
        for d in demandes
    )
    if not demandes:
        lignes = "<tr><td colspan='4' style='text-align:center; color:#8A8071;'>Aucune demande en attente</td></tr>"

    return f"""
    <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fisca AI - Codes de reinitialisation</title>
    <style>
      body{{font-family:sans-serif; padding:16px; background:#FBF9F4; color:#172227;}}
      h1{{color:#0E2A3A; font-size:20px;}}
      table{{width:100%; border-collapse:collapse; background:#fff; font-size:14px; margin-top:16px;}}
      th, td{{border:1px solid #E5DCC7; padding:10px 8px; text-align:left;}}
      th{{background:#0E2A3A; color:#fff;}}
      p{{color:#5C6B70; font-size:13px;}}
    </style></head><body>
    <h1>Codes de reinitialisation en attente</h1>
    <p>Valables 15 minutes. Recopie le code et renvoie-le a la personne sur WhatsApp.</p>
    <table><tr><th>Nom</th><th>Contact</th><th>Code</th><th>Expire le</th></tr>{lignes}</table>
    </body></html>
    """


@app.route("/webhook/whatsapp", methods=["GET"])
def whatsapp_verification():
    """Meta appelle cette route UNE SEULE FOIS, au moment ou tu colles
    l'URL du webhook dans son tableau de bord, pour verifier que tu es
    bien le proprietaire de ce serveur."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge, 200
    return "Verification echouee.", 403


@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_message_recu():
    """Recoit chaque message entrant sur le numero WhatsApp Fisca AI.
    Repond toujours 200 rapidement a Meta (sinon Meta considere l'appel
    en echec et reessaie en boucle), quel que soit ce qui se passe a
    l'interieur."""
    data = request.get_json(silent=True) or {}

    try:
        valeur = data["entry"][0]["changes"][0]["value"]
        messages = valeur.get("messages")
        if not messages:
            # Meta envoie aussi des notifications de statut (message
            # livre, lu...) sans "messages" - on les ignore simplement.
            return jsonify({"ok": True})
        message = messages[0]
        numero_expediteur = message["from"]
        texte = (message.get("text", {}) or {}).get("body", "").strip()
    except (KeyError, IndexError, TypeError):
        return jsonify({"ok": True})  # format inattendu, on ignore sans erreur

    if not texte:
        return jsonify({"ok": True})

    user = utilisateur_whatsapp(numero_expediteur)

    if intention_abonnement(texte) or texte.lower().strip() in ("oui standard", "oui expert"):
        reponse_texte = reponse_abonnement_whatsapp(texte, numero_expediteur, user)
        envoyer_message_whatsapp(numero_expediteur, reponse_texte)
        return jsonify({"ok": True})

    posees = questions_posees_aujourdhui(user["id"])
    illimite = est_illimite(user)
    if not illimite and posees >= QUOTA_GRATUIT_PAR_JOUR:
        envoyer_message_whatsapp(
            numero_expediteur,
            "Vous avez atteint votre limite de 5 questions gratuites aujourd'hui. "
            "Ecrivez ABONNEMENT pour decouvrir nos formules illimitees.",
        )
        return jsonify({"ok": True})

    resultat = repondre(texte)

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """INSERT INTO questions_log
           (user_id, question_brute, question_comprise, reponse, source, niveau, cree_le)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            user["id"], texte, resultat["question_comprise"], resultat["reponse"],
            resultat["source"], resultat["niveau"], datetime.now(),
        ),
    )
    db.commit()

    envoyer_message_whatsapp(numero_expediteur, resultat["reponse"])
    return jsonify({"ok": True})


@app.route("/api/sante")
def sante():
    """Petite route pour verifier rapidement que la base repond."""
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT 1")
        return jsonify({"ok": True, "base_de_donnees": "connectee"})
    except Exception as e:
        return jsonify({"ok": False, "erreur": str(e)}), 500


with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FISCA_AI_DEBUG", "0") == "1"
    print(f"Fisca AI (phase test) - port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)


