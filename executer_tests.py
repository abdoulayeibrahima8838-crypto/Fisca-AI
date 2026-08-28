#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
executer_tests.py — Lance la banque de 200 questions de test (150
normales + 50 pieges) contre le RAG, pour detecter les regressions apres
chaque modification de rag.py ou engine.py.

Version mise a jour pour la banque de 200 questions (remplace la version
a 15 questions). Trois types de verification selon la question :

1. Recherche standard (la majorite) : verifie qu'au moins un des articles
   attendus apparait dans les resultats de recherche_hybride. COUTE 1
   appel embedding par question (quota abondant, 1000/jour).

2. Vocabulaire local (questions dont la note mentionne "vocabulaire.py") :
   verifie juste que elargir_question() ne modifie PAS la question a
   tort. AUCUN cout, 100% local.

3. Detection de chemin (categorie "piège_large") : verifie qu'au moins
   un des mecanismes de routage (acte/procedure) se declenche. AUCUN
   cout, 100% local - ne verifie pas la redaction finale par Gemini,
   seulement que le bon aiguillage est pris.

Usage, depuis le Shell Render :
    python executer_tests.py
"""
import json
import os
from collections import defaultdict

import psycopg2
import psycopg2.extras
from google import genai

from rag import (
    embed_question, recherche_hybride,
    detecter_acte_dans_question, detecter_procedure_dans_question,
)
from vocabulaire import elargir_question

FICHIER_BANQUE = "banque_200_questions.json"

DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

with open(FICHIER_BANQUE, encoding="utf-8") as f:
    tests = json.load(f)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

nb_reussis = 0
nb_echecs = 0
nb_sans_verification = 0
resultats_par_categorie = defaultdict(lambda: {"reussis": 0, "echecs": 0, "sans_verif": 0})
echecs_detail = []

print(f"=== Exécution de {len(tests)} tests ===\n")

for test in tests:
    cat = test["categorie"]
    print(f"[{test['id']}] ({cat}) {test['question']}")

    # --- Cas 1 : test de vocabulaire local (aucun cout) ---
    if test["articles_attendus"] is None and "vocabulaire.py" in (test.get("note") or ""):
        resultat = elargir_question(test["question"])
        note = test.get("note") or ""
        est_test_positif = "NE DOIT PAS rester inchange" in note or "doit bien" in note

        if est_test_positif:
            # Test positif : le sigle DOIT declencher un elargissement
            if resultat != test["question"]:
                print(f"  ✅ OK — élargi comme attendu : {resultat[len(test['question']):].strip()!r}")
                nb_reussis += 1
                resultats_par_categorie[cat]["reussis"] += 1
            else:
                print("  ❌ ÉCHEC — aurait dû s'élargir, ne l'a pas fait")
                nb_echecs += 1
                resultats_par_categorie[cat]["echecs"] += 1
                echecs_detail.append(test["id"])
        else:
            # Test negatif : ne doit surtout PAS s'elargir a tort
            if resultat == test["question"]:
                print("  ✅ OK — aucun élargissement à tort (comme attendu)")
                nb_reussis += 1
                resultats_par_categorie[cat]["reussis"] += 1
            else:
                print(f"  ❌ ÉCHEC — élargi à tort : {resultat!r}")
                nb_echecs += 1
                resultats_par_categorie[cat]["echecs"] += 1
                echecs_detail.append(test["id"])
        print()
        continue

    # --- Cas 2 : test de detection de chemin (acte/procedure, aucun cout) ---
    if cat == "piège_large":
        acte = detecter_acte_dans_question(test["question"])
        procedure = detecter_procedure_dans_question(test["question"])
        if acte or procedure:
            chemin = f"acte={acte}" if acte else f"procédure={procedure}"
            print(f"  ✅ OK — routage détecté ({chemin})")
            nb_reussis += 1
            resultats_par_categorie[cat]["reussis"] += 1
        else:
            print("  ❌ ÉCHEC — aucun routage acte/procédure détecté (passera par la recherche standard, ou fiche par impôt)")
            nb_echecs += 1
            resultats_par_categorie[cat]["echecs"] += 1
            echecs_detail.append(test["id"])
        print()
        continue

    # --- Cas 3 : pas de verification automatique possible (piege ambigu assume) ---
    if test["articles_attendus"] is None:
        print(f"  ⚠️  Pas de vérification automatique — note : {test['note']}")
        nb_sans_verification += 1
        resultats_par_categorie[cat]["sans_verif"] += 1
        print()
        continue

    # --- Cas 4 (le plus courant) : recherche standard ---
    try:
        vecteur = embed_question(client, test["question"])
        pivots = recherche_hybride(conn, vecteur, test["question"], top_k=5)
        ids_trouves = [a.article_id for a in pivots]

        attendus = set(test["articles_attendus"])
        trouves = set(ids_trouves)
        if attendus & trouves:
            print(f"  ✅ OK — trouvé {sorted(attendus & trouves)} parmi {ids_trouves}")
            nb_reussis += 1
            resultats_par_categorie[cat]["reussis"] += 1
        else:
            print(f"  ❌ ÉCHEC — attendu un de {sorted(attendus)}, trouvé {ids_trouves}")
            nb_echecs += 1
            resultats_par_categorie[cat]["echecs"] += 1
            echecs_detail.append(test["id"])
    except Exception as e:
        print(f"  ❌ ERREUR — {type(e).__name__}: {e}")
        nb_echecs += 1
        resultats_par_categorie[cat]["echecs"] += 1
        echecs_detail.append(test["id"])
    print()

conn.close()

print("=" * 60)
print(f"RÉSUMÉ GLOBAL : {nb_reussis} réussis, {nb_echecs} échec(s), {nb_sans_verification} sans vérification")
print("=" * 60)
print("\nDétail par catégorie :")
for cat, r in sorted(resultats_par_categorie.items()):
    total = r["reussis"] + r["echecs"] + r["sans_verif"]
    print(f"  {cat:25s} : {r['reussis']}/{total} réussis" + (f", {r['echecs']} échec(s)" if r["echecs"] else ""))

if echecs_detail:
    print(f"\n⚠️  Échecs à examiner en priorité : {', '.join(echecs_detail)}")

