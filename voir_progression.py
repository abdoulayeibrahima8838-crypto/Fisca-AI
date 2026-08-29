#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voir_progression.py

Affiche un etat des lieux complet de la campagne de test, a partir des
fichiers deja sur disque - AUCUN appel Gemini, AUCUNE connexion base de
donnees, donc zero cout de quota et execution quasi instantanee.

Utile pour verifier ou en est la campagne avant de decider de relancer
fisca_ai_test_engine.py, ou pour suivre l'avancement pendant la montee
vers 500 questions.

Usage, depuis le Shell Render :
    python voir_progression.py
"""
import json
import os
from collections import defaultdict

FICHIER_BANQUE = "banque_200_questions.json"
FICHIER_PROGRESSION = "progression_campagne.json"


def main():
    if not os.path.exists(FICHIER_BANQUE):
        print(f"❌ {FICHIER_BANQUE} introuvable dans le dossier courant.")
        return
    if not os.path.exists(FICHIER_PROGRESSION):
        print(f"❌ {FICHIER_PROGRESSION} introuvable — aucune campagne n'a encore ecrit de progression.")
        return

    with open(FICHIER_BANQUE, encoding="utf-8") as f:
        tests = json.load(f)
    with open(FICHIER_PROGRESSION, encoding="utf-8") as f:
        progression = json.load(f)

    ids_testables = {
        t["id"] for t in tests
        if t["articles_attendus"] is not None or "vocabulaire.py" in (t.get("note") or "")
        or t["categorie"] in ("piège_large", "piège_hors_perimetre", "piège_article_inexistant")
    }

    total_banque = len(tests)
    total_testables = len(ids_testables)
    total_progression = len(progression)

    nb_reel_pass = 0
    nb_reel_fail = 0
    nb_reel_analyse = 0
    nb_presume = 0
    critical_fails = []
    a_analyser = []
    par_categorie = defaultdict(lambda: {"pass_reel": 0, "presume": 0, "fail": 0, "analyse": 0, "jamais_teste": 0, "total": 0})

    for tid in ids_testables:
        entree = progression.get(tid)
        cat = next((t["categorie"] for t in tests if t["id"] == tid), "?")
        par_categorie[cat]["total"] += 1

        if entree is None:
            par_categorie[cat]["jamais_teste"] += 1
            continue

        statut = entree.get("statut")
        est_presume = entree.get("presume", False)

        if statut == "PASS" and est_presume:
            nb_presume += 1
            par_categorie[cat]["presume"] += 1
        elif statut == "PASS":
            nb_reel_pass += 1
            par_categorie[cat]["pass_reel"] += 1
        elif statut == "FAIL":
            nb_reel_fail += 1
            par_categorie[cat]["fail"] += 1
            if entree.get("critical"):
                critical_fails.append((tid, cat, entree.get("erreurs", [])))
        elif statut == "À ANALYSER":
            nb_reel_analyse += 1
            par_categorie[cat]["analyse"] += 1
            a_analyser.append((tid, cat, entree.get("erreurs", [])))

    jamais_testees = sorted(ids_testables - set(progression.keys()))

    print("=" * 60)
    print("ÉTAT DE LA CAMPAGNE — FISCA AI TEST ENGINE")
    print("=" * 60)
    print(f"\nQuestions dans la banque : {total_banque} (dont {total_testables} testables)")
    print(f"Couvertes par la progression : {total_progression}/{total_testables}")
    print(f"\n  ✅ PASS réel (vraiment vérifié)     : {nb_reel_pass}")
    print(f"  🟡 PASS présumé (jamais reverifié)  : {nb_presume}")
    print(f"  ❌ FAIL                              : {nb_reel_fail}")
    print(f"  ⚠️  À ANALYSER                        : {nb_reel_analyse}")
    print(f"  ⏳ Jamais testées                    : {len(jamais_testees)}")

    if critical_fails:
        print(f"\n🔴 CRITICAL FAILS ACTUELS ({len(critical_fails)}) :")
        for tid, cat, erreurs in critical_fails:
            print(f"   [{tid}] {cat} — {', '.join(erreurs)}")

    if a_analyser:
        print(f"\n⚠️  À ANALYSER ({len(a_analyser)}) :")
        for tid, cat, erreurs in a_analyser:
            print(f"   [{tid}] {cat} — {', '.join(erreurs)}")

    if jamais_testees:
        print(f"\n⏳ JAMAIS TESTÉES ({len(jamais_testees)}) :")
        print(f"   {', '.join(jamais_testees[:40])}" + (" ..." if len(jamais_testees) > 40 else ""))

    print("\nPerformance par catégorie (PASS réel + présumé / total) :")
    for cat, c in sorted(par_categorie.items(), key=lambda x: -x[1]["total"]):
        couverts = c["pass_reel"] + c["presume"] + c["fail"] + c["analyse"]
        print(f"  {cat:25s} : {couverts}/{c['total']:3d} couvertes"
              f" (réel={c['pass_reel']}, présumé={c['presume']}, fail={c['fail']}, analyse={c['analyse']}, jamais={c['jamais_teste']})")

    # --- Cout estime d'un prochain lancement ---
    a_retester = nb_reel_fail + nb_reel_analyse + len(jamais_testees)
    print(f"\n💡 Un prochain lancement de fisca_ai_test_engine.py testera environ {a_retester} question(s)")
    print(f"   ({nb_reel_fail} FAIL + {nb_reel_analyse} À ANALYSER + {len(jamais_testees)} jamais testées)")
    print(f"   — largement sous la limite de 1000 embeddings/jour.")


if __name__ == "__main__":
    main()
