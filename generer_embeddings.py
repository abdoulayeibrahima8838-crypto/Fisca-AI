#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_embeddings.py — Génère les embeddings de tous les articles du CGI
2026 via gemini-embedding-001 et les insère dans la table cgi_articles.

À EXÉCUTER SUR RENDER (accès réseau requis pour appeler l'API Gemini) —
ne fonctionnera pas dans un environnement sans sortie internet.

Idempotent : si un article a déjà un embedding en base, il est sauté.
Peut donc être relancé sans risque après une interruption (timeout,
redémarrage du service, etc.) — reprend là où il s'était arrêté.

Variables d'environnement requises (les mêmes que engine.py) :
  GEMINI_API_KEY
  DATABASE_URL   (URL de connexion Postgres, fournie par Render)

Usage (depuis le Shell Render du service) :
  python generate_embeddings.py
"""

import os
import sys
import json
import time

import psycopg2
from psycopg2.extras import execute_values

try:
    from google import genai
except ImportError:
    print("Le package 'google-genai' n'est pas installé. Ajoutez-le à requirements.txt.")
    sys.exit(1)

ARTICLES_JSON = os.path.join(os.path.dirname(__file__), "cgi2026_articles_corrige.json")
GEMINI_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "3072"))
BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "20"))
PAUSE_ENTRE_LOTS_SECONDES = float(os.environ.get("EMBEDDING_PAUSE_SECONDS", "1.0"))

DATABASE_URL = os.environ.get("DATABASE_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not DATABASE_URL:
    print("ERREUR : la variable d'environnement DATABASE_URL est absente.")
    sys.exit(1)
if not GEMINI_API_KEY:
    print("ERREUR : la variable d'environnement GEMINI_API_KEY est absente.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)


def charger_articles():
    with open(ARTICLES_JSON, encoding="utf-8") as f:
        return json.load(f)


def articles_deja_embeddes(conn):
    """Renvoie l'ensemble des article_id qui ont déjà un embedding en base
    — permet de reprendre le travail après une interruption sans tout
    refaire ni consommer inutilement des appels API déjà payés."""
    with conn.cursor() as cur:
        cur.execute("SELECT article_id FROM cgi_articles WHERE embedding IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def upsert_article_sans_embedding(conn, art):
    """Insère ou met à jour les métadonnées de l'article (sans embedding
    pour l'instant) — sépare le remplissage des métadonnées de l'appel
    IA, pour que la structure soit dans tous les cas à jour même si un
    embedding échoue."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cgi_articles (
                article_id, article_num, article_suffix, page,
                livre_num, livre_titre, titre_num, titre_titre,
                chapitre_num, chapitre_titre, section_num, section_titre,
                ssection_num, ssection_titre, text
            ) VALUES (
                %(article_id)s, %(article_num)s, %(article_suffix)s, %(page)s,
                %(livre_num)s, %(livre_titre)s, %(titre_num)s, %(titre_titre)s,
                %(chapitre_num)s, %(chapitre_titre)s, %(section_num)s, %(section_titre)s,
                %(ssection_num)s, %(ssection_titre)s, %(text)s
            )
            ON CONFLICT (article_id) DO UPDATE SET
                article_num = EXCLUDED.article_num,
                article_suffix = EXCLUDED.article_suffix,
                page = EXCLUDED.page,
                livre_num = EXCLUDED.livre_num,
                livre_titre = EXCLUDED.livre_titre,
                titre_num = EXCLUDED.titre_num,
                titre_titre = EXCLUDED.titre_titre,
                chapitre_num = EXCLUDED.chapitre_num,
                chapitre_titre = EXCLUDED.chapitre_titre,
                section_num = EXCLUDED.section_num,
                section_titre = EXCLUDED.section_titre,
                ssection_num = EXCLUDED.ssection_num,
                ssection_titre = EXCLUDED.ssection_titre,
                text = EXCLUDED.text
            """,
            art,
        )
    conn.commit()


def generer_embedding(texte):
    """Appelle gemini-embedding-001 pour un article. Retourne la liste de
    flottants, ou None en cas d'échec (l'appelant réessaiera au prochain
    lancement du script plutôt que de bloquer tout le lot)."""
    try:
        response = client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL,
            contents=texte,
            config={"output_dimensionality": EMBEDDING_DIM},
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"  [erreur embedding] {type(e).__name__}: {e}")
        return None


def enregistrer_embedding(conn, article_id, vecteur):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE cgi_articles SET embedding = %s WHERE article_id = %s",
            (vecteur, article_id),
        )
    conn.commit()


def main():
    articles = charger_articles()
    print(f"{len(articles)} articles chargés depuis {ARTICLES_JSON}")

    conn = psycopg2.connect(DATABASE_URL)

    # 1) S'assure que toutes les métadonnées sont à jour en base, avant
    #    même de s'occuper des embeddings.
    print("Mise à jour des métadonnées de tous les articles...")
    for art in articles:
        upsert_article_sans_embedding(conn, art)
    print("Métadonnées à jour.")

    # 2) Génère les embeddings manquants uniquement.
    deja_faits = articles_deja_embeddes(conn)
    a_traiter = [a for a in articles if a["article_id"] not in deja_faits]
    print(f"{len(deja_faits)} articles déjà embeddés (sautés), {len(a_traiter)} restants à traiter.")

    reussis, echoues = 0, []
    for i, art in enumerate(a_traiter, start=1):
        vecteur = generer_embedding(art["text"])
        if vecteur is None:
            echoues.append(art["article_id"])
        else:
            enregistrer_embedding(conn, art["article_id"], vecteur)
            reussis += 1

        if i % BATCH_SIZE == 0:
            print(f"  ... {i}/{len(a_traiter)} traités ({reussis} réussis, {len(echoues)} échecs)")
            time.sleep(PAUSE_ENTRE_LOTS_SECONDES)

    print(f"\nTerminé : {reussis} embeddings générés avec succès, {len(echoues)} échecs.")
    if echoues:
        print("Articles en échec (relancez le script pour réessayer, il reprendra automatiquement) :")
        print(echoues)

    conn.close()


if __name__ == "__main__":
    main()
