#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
executer_tests.py — Point #34 du plan initial : lance la banque de
questions de test contre le RAG, pour detecter les regressions apres
chaque modification de rag.py ou engine.py.

Teste UNIQUEMENT LA RECHERCHE (pas la redaction par Gemini) - consomme
donc seulement le quota d'EMBEDDING (1000/jour, abondant), jamais le
quota de generation (20/jour, rare). Un test avec recherche = 1 appel
embedding ; les tests de vocabulaire (categorie "vocabulaire_piege") ne
consomment rien du tout.

Usage, depuis le Shell Render :
    python executer_tests.py
"""
import json
import os

import psycopg2
import psycopg2.extras
from google import genai

from rag import embed_question, recherche_hybride
from vocabulaire import elargir_question

DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

with open("banque_questions_test.json", encoding="utf-8") as f:
    tests = json.load(f)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

nb_reussis = 0
nb_echecs = 0
nb_sans_verification = 0

print(f"=== Exécution de {len(tests)} tests ===\n")

for test in tests:
    print(f"[{test['id']}] {test['question']}")

    if test["categorie"] == "vocabulaire_piege":
        # Test 100% local, sans recherche BDD ni appel API - verifie
        # juste que vocabulaire.py ne se declenche pas a tort.
        resultat = elargir_question(test["question"])
        if resultat == test["question"]:
            print("  ✅ OK — aucun élargissement à tort (comme attendu)")
            nb_reussis += 1
        else:
            print(f"  ❌ ÉCHEC — élargi à tort : {resultat!r}")
            nb_echecs += 1
        print()
        continue

    if test["articles_attendus"] is None:
        print(f"  ⚠️  Pas de vérification automatique — note : {test['note']}")
        nb_sans_verification += 1
        print()
        continue

    try:
        vecteur = embed_question(client, test["question"])
        pivots = recherche_hybride(conn, vecteur, test["question"], top_k=5)
        ids_trouves = [a.article_id for a in pivots]

        attendus = set(test["articles_attendus"])
        trouves = set(ids_trouves)
        if attendus & trouves:
            print(f"  ✅ OK — trouvé {sorted(attendus & trouves)} parmi {ids_trouves}")
            nb_reussis += 1
        else:
            print(f"  ❌ ÉCHEC — attendu un de {sorted(attendus)}, trouvé {ids_trouves}")
            nb_echecs += 1
    except Exception as e:
        print(f"  ❌ ERREUR — {type(e).__name__}: {e}")
        nb_echecs += 1
    print()

conn.close()
print(
    f"=== Résumé : {nb_reussis} réussis, {nb_echecs} échec(s), "
    f"{nb_sans_verification} sans vérification automatique ==="
)
