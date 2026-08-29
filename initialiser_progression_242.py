#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
initialiser_progression_242.py

Marque toutes les questions ACTUELLEMENT presentes dans banque_200_questions.json
comme "presumees validees", SANS appeler Gemini et SANS consommer le moindre
quota d'embeddings - c'est une decision de gestion (on considere que ce lot
est deja couvert), pas une verification reelle.

Chaque entree est etiquetee "presume": true et datee, pour que ce soit
tracable plus tard si tu veux un jour les revalider pour de vrai avec
--refaire-tout sur fisca_ai_test_engine.py.

Usage, depuis le Shell Render :
    python initialiser_progression_242.py
"""
import json
import os
from datetime import datetime, timezone

FICHIER_BANQUE = "banque_200_questions.json"
FICHIER_PROGRESSION = "progression_campagne.json"


def main():
    with open(FICHIER_BANQUE, encoding="utf-8") as f:
        tests = json.load(f)

    if os.path.exists(FICHIER_PROGRESSION):
        with open(FICHIER_PROGRESSION, encoding="utf-8") as f:
            progression = json.load(f)
        print(f"Fichier de progression existant trouvé ({len(progression)} entrée(s)) — les nouvelles entrées seront ajoutées sans écraser ce qui existe déjà.")
    else:
        progression = {}

    horodatage = datetime.now(timezone.utc).isoformat()
    nb_ajoutees = 0
    nb_deja_presentes = 0

    for test in tests:
        tid = test["id"]
        if tid in progression:
            nb_deja_presentes += 1
            continue
        progression[tid] = {
            "id": tid,
            "categorie": test["categorie"],
            "critical": test.get("critical", False),
            "statut": "PASS",
            "presume": True,
            "note_gestion": "Considéré comme validé par décision du 29/08/2026, sans nouvelle vérification quota — pas un vrai résultat de test.",
            "date_presomption": horodatage,
        }
        nb_ajoutees += 1

    with open(FICHIER_PROGRESSION, "w", encoding="utf-8") as f:
        json.dump(progression, f, ensure_ascii=False, indent=2)

    print(f"\n{nb_ajoutees} question(s) marquée(s) comme présumées validées.")
    if nb_deja_presentes:
        print(f"{nb_deja_presentes} question(s) déjà présentes dans la progression (inchangées).")
    print(f"Total dans {FICHIER_PROGRESSION} : {len(progression)} question(s).")
    print("\nAucun appel Gemini effectué — quota intact.")
    print("Les prochaines exécutions de fisca_ai_test_engine.py sauteront toutes ces questions")
    print("et ne testeront que les nouvelles questions ajoutées à la banque vers 500.")


if __name__ == "__main__":
    main()
