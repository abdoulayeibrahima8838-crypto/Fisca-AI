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
from engine import repondre

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUOTA_GRATUIT_PAR_JOUR = 10

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
    return jsonify(
        {
            "connecte": True,
            "nom": user["nom"],
            "questions_restantes": max(0, QUOTA_GRATUIT_PAR_JOUR - posees),
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
    if posees >= QUOTA_GRATUIT_PAR_JOUR:
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
            "questions_restantes": max(0, QUOTA_GRATUIT_PAR_JOUR - posees - 1),
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
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


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
