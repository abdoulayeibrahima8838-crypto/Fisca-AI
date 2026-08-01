# -*- coding: utf-8 -*-
"""
Fisca AI - serveur de test local (PHASE TEST, sans API OpenAI).

Lancement :
    pip install -r requirements.txt
    python app.py
Puis ouvrir : http://127.0.0.1:5000

Ce serveur remplace pour l'instant l'API OpenAI + File Search par le
moteur local (engine.py) qui cherche dans cache_data.py. Le jour ou tu as
une cle API OpenAI, on remplace juste la fonction repondre() par un vrai
appel API - tout le reste (comptes, quota, journal) ne bouge pas.
"""
import hashlib
import os
import secrets
import sqlite3
from datetime import date, datetime

from flask import Flask, g, jsonify, request, send_from_directory, session

from cache_data import DOCUMENT_ACTIF, SUGGESTIONS
from engine import repondre

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "fisca_ai.db")
QUOTA_GRATUIT_PAR_JOUR = 10

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.environ.get("FISCA_AI_SECRET", secrets.token_hex(32))


# ---------------------------------------------------------------------------
# Base de donnees
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            contact TEXT UNIQUE NOT NULL,
            sel TEXT NOT NULL,
            mot_de_passe_hash TEXT NOT NULL,
            cree_le TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_brute TEXT NOT NULL,
            question_comprise TEXT,
            reponse TEXT NOT NULL,
            source TEXT,
            niveau INTEGER,
            cree_le TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_log_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            cree_le TEXT NOT NULL,
            FOREIGN KEY(question_log_id) REFERENCES questions_log(id)
        );
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Mots de passe (hachage simple avec sel, sans dependance externe)
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
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def questions_posees_aujourdhui(user_id):
    db = get_db()
    aujourdhui = date.today().isoformat()
    row = db.execute(
        "SELECT COUNT(*) as n FROM questions_log WHERE user_id = ? AND date(cree_le) = ?",
        (user_id, aujourdhui),
    ).fetchone()
    return row["n"]


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
    existe = db.execute("SELECT id FROM users WHERE contact = ?", (contact,)).fetchone()
    if existe:
        return jsonify({"erreur": "Un compte existe deja avec ce contact."}), 409

    sel = secrets.token_hex(16)
    hash_mdp = hacher_mot_de_passe(mot_de_passe, sel)
    db.execute(
        "INSERT INTO users (nom, contact, sel, mot_de_passe_hash, cree_le) VALUES (?, ?, ?, ?, ?)",
        (nom, contact, sel, hash_mdp, datetime.now().isoformat()),
    )
    db.commit()
    user = db.execute("SELECT * FROM users WHERE contact = ?", (contact,)).fetchone()
    session["user_id"] = user["id"]
    return jsonify({"ok": True, "nom": user["nom"]})


@app.route("/api/connexion", methods=["POST"])
def connexion():
    data = request.get_json(silent=True) or {}
    contact = (data.get("contact") or "").strip().lower()
    mot_de_passe = data.get("mot_de_passe") or ""

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE contact = ?", (contact,)).fetchone()
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
    cursor = db.execute(
        """INSERT INTO questions_log
           (user_id, question_brute, question_comprise, reponse, source, niveau, cree_le)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user["id"],
            texte,
            resultat["question_comprise"],
            resultat["reponse"],
            resultat["source"],
            resultat["niveau"],
            datetime.now().isoformat(),
        ),
    )
    db.commit()

    return jsonify(
        {
            "id_question": cursor.lastrowid,
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
    db.execute(
        "INSERT INTO feedback (question_log_id, type, cree_le) VALUES (?, ?, ?)",
        (id_question, type_retour, datetime.now().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Frontend statique
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FISCA_AI_DEBUG", "0") == "1"
    print(f"Fisca AI (phase test) - port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
