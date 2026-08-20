#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generer_embeddings.py — A LANCER UNE SEULE FOIS (ou re-lancer si interrompu,
il est conçu pour reprendre là où il s'est arrêté sans tout refaire).

Usage, depuis le Shell Render du service fisca-ai :
    python generer_embeddings.py

Ce script :
1. Crée les tables cgi_articles et article_refs si elles n'existent pas
   (execute schema.sql).
2. Pour chaque article de cgi2026_articles_corrige.json qui n'a PAS encore
   d'embedding en base, appelle gemini-embedding-001 et l'insere.
3. Insere les 316 renvois de cgi2026_refs.json (sans erreur si deja presents).

Robuste aux coupures : si le Shell se ferme en cours de route, relance
simplement le script - il reprendra uniquement les articles qui n'ont pas
encore d'embedding, sans dupliquer ni refaire ce qui est deja fait.

Necessite dans l'environnement (deja presentes normalement sur Render pour
Fisca AI) : DATABASE_URL, GEMINI_API_KEY.
Necessite dans le meme dossier : schema.sql, cgi2026_articles_corrige.json,
cgi2026_refs.json.
"""
import json
import os
import sys
import time

import psycopg2
import psycopg2.extras

from google import genai
from google.genai import types as genai_types

# ---------------------------------------------------------------------------
# Connexion base de donnees - meme logique que app.py (Render fournit parfois
# une URL commencant par "postgres://" qu'il faut adapter pour psycopg2).
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERREUR : DATABASE_URL n'est pas defini dans l'environnement. Arret.")
    sys.exit(1)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERREUR : GEMINI_API_KEY n'est pas defini dans l'environnement. Arret.")
    sys.exit(1)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 1536  # reduit de 3072 - pgvector HNSW ne supporte pas plus de 2000 dimensions ; doit correspondre a vector(1536) dans schema.sql
MAX_ESSAIS_PAR_ARTICLE = 3
DELAI_ENTRE_ESSAIS_SECONDES = 5

client = genai.Client(api_key=GEMINI_API_KEY)
conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
conn.autocommit = False


def creer_tables():
    print("Étape 1/3 — Création des tables (si elles n'existent pas déjà)...")
    with open("schema.sql", encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("  Tables prêtes.\n")


def embedding_pour_texte(texte, titre_pour_contexte):
    """Appelle Gemini pour UN seul texte (le modele n'accepte qu'une entree
    par appel). Reessaie automatiquement en cas d'erreur passagere."""
    for essai in range(1, MAX_ESSAIS_PAR_ARTICLE + 1):
        try:
            resultat = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texte,
                config=genai_types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                    title=titre_pour_contexte,
                ),
            )
            return resultat.embeddings[0].values
        except Exception as e:
            print(f"    Essai {essai}/{MAX_ESSAIS_PAR_ARTICLE} échoué ({type(e).__name__}: {e})")
            if essai < MAX_ESSAIS_PAR_ARTICLE:
                time.sleep(DELAI_ENTRE_ESSAIS_SECONDES)
    return None


def generer_embeddings_articles():
    print("Étape 2/3 — Génération des embeddings des articles...")
    with open("cgi2026_articles_corrige.json", encoding="utf-8") as f:
        articles = json.load(f)
    print(f"  {len(articles)} articles au total dans le fichier source.")

    with conn.cursor() as cur:
        cur.execute("SELECT article_id FROM cgi_articles WHERE embedding IS NOT NULL")
        deja_faits = {row["article_id"] for row in cur.fetchall()}
    print(f"  {len(deja_faits)} articles déjà en base avec un embedding — seront ignorés.\n")

    restants = [a for a in articles if a["article_id"] not in deja_faits]
    total_restants = len(restants)
    if total_restants == 0:
        print("  Rien à faire : tous les articles ont déjà leur embedding.\n")
        return

    echecs = []
    for i, article in enumerate(restants, start=1):
        titre_contexte = f"Article {article['article_num']}{article.get('article_suffix') or ''} - {article.get('chapitre_titre') or article.get('livre_titre') or ''}"
        vecteur = embedding_pour_texte(article["text"], titre_contexte)

        if vecteur is None:
            echecs.append(article["article_id"])
            print(f"  [{i}/{total_restants}] Art. {article['article_id']} — ÉCHEC après {MAX_ESSAIS_PAR_ARTICLE} essais, ignoré (relancer le script le reprendra).")
            continue

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cgi_articles (
                    article_id, article_num, article_suffix, page,
                    livre_num, livre_titre, titre_num, titre_titre,
                    chapitre_num, chapitre_titre, section_num, section_titre,
                    ssection_num, ssection_titre, text, embedding
                ) VALUES (
                    %(article_id)s, %(article_num)s, %(article_suffix)s, %(page)s,
                    %(livre_num)s, %(livre_titre)s, %(titre_num)s, %(titre_titre)s,
                    %(chapitre_num)s, %(chapitre_titre)s, %(section_num)s, %(section_titre)s,
                    %(ssection_num)s, %(ssection_titre)s, %(text)s, %(embedding)s
                )
                ON CONFLICT (article_id) DO UPDATE SET
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding
                """,
                {**article, "embedding": vecteur},
            )
        conn.commit()

        if i % 20 == 0 or i == total_restants:
            print(f"  [{i}/{total_restants}] progression — dernier traité : Art. {article['article_id']}")

    print(f"\n  Terminé : {total_restants - len(echecs)} embeddings générés, {len(echecs)} échec(s).")
    if echecs:
        print(f"  Articles en échec (relancer le script pour réessayer) : {echecs}\n")
    else:
        print()


def inserer_renvois():
    print("Étape 3/3 — Insertion des renvois entre articles...")
    with open("cgi2026_refs.json", encoding="utf-8") as f:
        refs = json.load(f)
    print(f"  {len(refs)} renvois à traiter.")

    reussis = 0
    ignores = []
    for r in refs:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO article_refs (source_article_id, target_article_id, ref_type)
                    VALUES (%(source_article_id)s, %(target_article_id)s, %(ref_type)s)
                    ON CONFLICT (source_article_id, target_article_id, ref_type) DO NOTHING
                    """,
                    r,
                )
            conn.commit()
            reussis += 1
        except psycopg2.errors.ForeignKeyViolation:
            # L'article source ou cible n'existe pas encore en base - le plus
            # souvent parce que son embedding a echoue a l'etape precedente.
            # On ignore CE renvoi precis et on continue, plutot que de tout
            # arreter : relancer le script plus tard (une fois l'article
            # manquant corrige) inserera automatiquement ce renvoi.
            conn.rollback()
            ignores.append(r)
        except Exception as e:
            conn.rollback()
            print(f"    Erreur inattendue sur un renvoi ({r}) : {type(e).__name__}: {e}")

    print(f"  {reussis} renvoi(s) inséré(s) avec succès.")
    if ignores:
        articles_manquants = sorted({r["target_article_id"] for r in ignores} | {r["source_article_id"] for r in ignores})
        print(f"  {len(ignores)} renvoi(s) ignoré(s) car un article lié n'existe pas encore en base.")
        print(f"  Article(s) manquant(s) probable(s) (embedding en échec) : {articles_manquants}")
        print("  -> Corrige ces articles puis relance le script : ces renvois s'inséreront automatiquement.")
    print()


if __name__ == "__main__":
    print("=== Génération du RAG Fisca AI — CGI 2026 ===\n")
    creer_tables()
    generer_embeddings_articles()
    inserer_renvois()
    conn.close()
    print("=== Terminé. La base pgvector est prête. ===")

