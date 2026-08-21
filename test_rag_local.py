#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rag_local.py — Teste la recherche vectorielle SANS consommer le moindre
quota Gemini, en réutilisant l'embedding d'un article déjà stocké en base
comme "question" de test, au lieu d'en générer un nouveau via l'API.

Principe du test : si on cherche avec le vecteur de l'article X lui-même,
cet article X doit ressortir en tout premier résultat (distance quasi
nulle avec lui-même) — une bonne vérification que la recherche vectorielle
(index pgvector/HNSW) fonctionne correctement.

Usage, depuis le Shell Render :
    python test_rag_local.py 209
    (209 = numéro d'un article déjà en base — sans argument, en prend un au hasard)
"""
import os
import sys

import psycopg2
import psycopg2.extras

from rag import search_pivot_articles, expand_via_refs

DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

article_id_test = sys.argv[1] if len(sys.argv) > 1 else None

conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

if article_id_test:
    cur.execute(
        "SELECT article_id, embedding, text FROM cgi_articles WHERE article_id = %s AND embedding IS NOT NULL",
        (article_id_test,),
    )
else:
    cur.execute("SELECT article_id, embedding, text FROM cgi_articles WHERE embedding IS NOT NULL LIMIT 1")

ligne = cur.fetchone()
if not ligne:
    print(f"Aucun article trouvé avec embedding pour cet identifiant ({article_id_test!r}).")
    sys.exit(1)

print(f"Article de référence utilisé comme 'question' test : {ligne['article_id']}")
print(f"Texte : {ligne['text'][:150]}...\n")

vecteur_test = ligne["embedding"]

print("Recherche des articles les plus proches (l'article lui-même devrait ressortir en 1er) :")
pivots = search_pivot_articles(conn, vecteur_test, top_k=5)
for i, a in enumerate(pivots, start=1):
    marque = " <-- l'article de référence lui-même" if a.article_id == ligne["article_id"] else ""
    print(f"  {i}. [Art. {a.article_id}] {a.chapitre_titre or a.livre_titre} — {a.text[:80]}...{marque}")

print("\nExpansion par renvois explicites :")
linked = expand_via_refs(conn, pivots)
if linked:
    for a in linked:
        print(f"  [Art. {a.article_id}] (lié) {a.text[:80]}...")
else:
    print("  Aucun renvoi trouvé pour ces articles.")

conn.close()
print("\nTerminé — aucun appel API Gemini consommé (embedding réutilisé depuis la base).")

if pivots and pivots[0].article_id == ligne["article_id"]:
    print("\n✅ TEST RÉUSSI : l'article de référence ressort bien en 1ère position.")
else:
    print("\n⚠️ À vérifier : l'article de référence n'est pas ressorti en 1ère position.")
