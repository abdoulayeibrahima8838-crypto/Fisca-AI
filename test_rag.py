#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rag.py — Teste UNIQUEMENT la recherche (étapes 1 et 2 du RAG), sans
génération de réponse finale. Consomme un seul appel d'embedding — rien à
voir avec le quota de génération (20/jour) ni celui d'embedding (1000/jour,
déjà bien entamé).

Usage, depuis le Shell Render :
    python test_rag.py "Quelles sont les sanctions en cas de facture non certifiée ?"
"""
import os
import sys

import psycopg2
import psycopg2.extras
from google import genai

from rag import search_pivot_articles, expand_via_refs, build_context_blocks, embed_question

DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

question = sys.argv[1] if len(sys.argv) > 1 else "Quelles sont les obligations liées à la facture certifiée ?"

print(f"Question testée : {question}\n")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

print("1. Transformation de la question en vecteur...")
vecteur_question = embed_question(client, question)
print(f"   OK — vecteur de {len(vecteur_question)} dimensions.\n")

print("2. Recherche des articles les plus proches...")
pivots = search_pivot_articles(conn, vecteur_question, top_k=5)
for a in pivots:
    print(f"   [Art. {a.article_id}] {a.chapitre_titre or a.livre_titre} — {a.text[:80]}...")
print()

print("3. Expansion par renvois explicites...")
linked = expand_via_refs(conn, pivots)
if linked:
    for a in linked:
        print(f"   [Art. {a.article_id}] (lié) {a.text[:80]}...")
else:
    print("   Aucun renvoi trouvé pour ces articles.")
print()

print("4. Contexte final qui serait envoyé à Gemini pour rédaction :\n")
print("=" * 60)
print(build_context_blocks(pivots, linked))
print("=" * 60)

conn.close()
print("\nTerminé — aucune génération de réponse effectuée (pour ne pas consommer le quota de génération).")
