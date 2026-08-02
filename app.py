# -*- coding: utf-8 -*-
"""
Fisca AI - serveur (PHASE TEST, sans API OpenAI, avec base PostgreSQL Render).

Ce serveur a besoin d'une variable d'environnement DATABASE_URL, fournie
automatiquement par Render quand tu relies ta base PostgreSQL a ce
service (onglet Environment). Sans elle, le serveur refuse de demarrer
et l'affiche clairement dans les logs.
"""
import hashlib
import os
import secrets
from datetime import date, datetime

import psycopg2
import psycopg2.extras
from flask import Flask, g, jsonify, request, send_from_directory, session

from cache_data import DOCUMENT_ACTIF, SUGGESTIONS
from catalogue import CATALOGUE, DOCUMENTS_TELECHARGEABLES, ABONNEMENTS, lien_whatsapp_commande
from payments import initier_paiement
from engine import repondre

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUOTA_GRATUIT_PAR_JOUR = 5

# Comptes qui n'ont pas de limite quotidienne (pour tes propres tests).
# Sur Render, ajoute la variable COMPTES_ILLIMITES avec ton contact
# (le meme que celui utilise pour te connecter), ex: "90000000" ou
# plusieurs separes par des virgules : "90000000,tonemail@exemple.com"
COMPTES_ILLIMITES = {
    c.strip().lower()
    for c in os.environ.get("COMPTES_ILLIMITES", "").split(",")
    if c.strip()
}


def est_illimite(user):
    return user["contact"].strip().lower() in COMPTES_ILLIMITES

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Certains fournisseurs donnent l'ancien prefixe ; psycopg2 accepte
    # les deux, mais on normalise pour eviter toute surprise.
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.environ.get("FISCA_AI_SECRET", secrets.token_hex(32))


# ---------------------------------------------------------------------------
# Base de donnees (PostgreSQL)
# ---------------------------------------------------------------------------
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
        """
    )
    conn.commit()
    cur.close()
    conn.close()
    print("Base PostgreSQL initialisee (tables verifiees/creees).")


# ---------------------------------------------------------------------------
# Mots de passe (hachage avec sel, sans dependance externe)
# ---------------------------------------------------------------------------
def hacher_mot_de_passe(mot_de_passe, sel):
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel.encode("utf-8"), 100_000).hex()


# ---------------------------------------------------------------------------
# Aides
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Routes API
# ---------------------------------------------------------------------------
@app.route("/api/inscription", methods=["POST"])
def inscription():
    data = request.get_json(silent=True) or {}
    nom = (data.get("nom") or "").strip()
    contact = (data.get("contact") or "").strip().lower()
    mot_de_passe = data.get("mot_de_passe") or ""

    if not nom or not contact or len(mot_de_passe) < 4:
        return jsonify({"erreur": "Nom, contact et mot de passe (4 caracteres minimum) sont requis."}), 400

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

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE contact = %s", (contact,))
    user = cur.fetchone()
    if not user or hacher_mot_de_passe(mot_de_passe, user["sel"]) != user["mot_de_passe_hash"]:
        return jsonify({"erreur": "Contact ou mot de passe incorrect."}), 401

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


# ---------------------------------------------------------------------------
# Frontend statique
# ---------------------------------------------------------------------------
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
    if len(nouveau) < 4:
        return jsonify({"erreur": "Le nouveau mot de passe doit faire au moins 4 caracteres."}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE users SET mot_de_passe_hash = %s WHERE id = %s",
        (hacher_mot_de_passe(nouveau, user["sel"]), user["id"]),
    )
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

    # Repli automatique : circuit manuel via WhatsApp (deja fonctionnel)
    lien = lien_whatsapp_commande(description, user["nom"])
    return jsonify({"ok": True, "mode": "whatsapp", "lien_paiement": lien})


@app.route("/api/paiement/webhook/<fournisseur>", methods=["POST"])
def webhook_paiement(fournisseur):
    """Emplacement reserve pour recevoir les confirmations de paiement
    de MyNITA/iMoney. NON ACTIF tant que ces fournisseurs ne sont pas
    branches : a completer avec la verification de signature et le
    format exacts fournis par chaque prestataire."""
    # --- A COMPLETER lors du branchement reel du fournisseur ---
    # data = request.get_json(silent=True) or {}
    # verifier la signature/authenticite selon la doc du fournisseur
    # retrouver le paiement via reference_externe, passer statut='paye', paye_le=datetime.now()
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


@app.route("/admin")
def admin():
    """Page de consultation simple, protegee par mot de passe (ADMIN_PASSWORD).
    Usage : https://ton-site.onrender.com/admin?motdepasse=xxxxx
    """
    mot_de_passe_attendu = os.environ.get("ADMIN_PASSWORD")
    if not mot_de_passe_attendu:
        return "ADMIN_PASSWORD n'est pas configure. Ajoute cette variable d'environnement sur Render pour activer cette page.", 503

    fourni = request.args.get("motdepasse", "")
    if fourni != mot_de_passe_attendu:
        return "Mot de passe manquant ou incorrect. Utilise : /admin?motdepasse=TON_MOT_DE_PASSE", 401

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
