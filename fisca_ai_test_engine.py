#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fisca_ai_test_engine.py — FISCA AI TEST ENGINE (version gratuite, sans
LLM Judge). Remplace executer_tests.py avec une vraie architecture
d'evaluation, inspiree du document de conception du systeme de test
interne, mais limitee aux composants qui NE COUTENT AUCUN QUOTA GEMINI.

CE QUI EST FAIT ICI (gratuit - embeddings uniquement, 1000/jour) :
  - Test Orchestrator (file de tests, execution, capture des resultats)
  - RAG Evaluator : Recall@1, Recall@3, Recall@5, Recall@10, MRR
  - Controles deterministes : verification programmatique des taux/
    montants/delais attendus dans le texte de l'article retrouve
  - Classification des erreurs (RETRIEVAL_ERROR, RANKING_ERROR, etc.)
  - Critical Fail : un echec sur une question marquee "critical" est
    signale separement, independamment du score global
  - Suivi de version + Regression Engine : chaque execution est
    sauvegardee dans un historique JSON, comparee a la precedente
  - Rapport final automatique, au format du document de conception

CE QUI EST VOLONTAIREMENT ABSENT ICI (coute du quota Gemini - a ajouter
apres le paiement, voir le fichier PHASE_QUOTA_ULTERIEURE.md) :
  - LLM-as-a-Judge (evaluation semantique de la REDACTION finale, pas
    seulement de la recherche) - necessite un appel Gemini par question
  - Generation automatique de variantes de questions (4 par question x
    200 = 800 questions supplementaires) - necessite un appel Gemini
    par variante generee
  - Test de coherence semantique entre variantes (necessite les
    variantes ci-dessus, donc indirectement du quota)
  - Test de stabilite (memes questions x5 executions) - techniquement
    gratuit en recherche pure, mais n'a de sens que combine au Judge
    pour evaluer la redaction, pas juste la recherche

Usage, depuis le Shell Render :
    python fisca_ai_test_engine.py [--version "1.0"]
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from google import genai

from rag import (
    embed_question, recherche_hybride,
    detecter_acte_dans_question, detecter_procedure_dans_question,
)
from vocabulaire import elargir_question

FICHIER_BANQUE = "banque_200_questions.json"
FICHIER_HISTORIQUE = "test_runs_history.json"

# ---------------------------------------------------------------------------
# Classification des erreurs (§20 du document de conception) - limitee aux
# codes pertinents pour une evaluation RETRIEVAL SEULE (pas de generation
# ici, donc pas de HALLUCINATION/WRONG_RATE au sens generation - seulement
# ce qui concerne la recherche elle-meme).
# ---------------------------------------------------------------------------
RETRIEVAL_ERROR = "RETRIEVAL_ERROR"        # article attendu absent meme du top 10
RANKING_ERROR = "RANKING_ERROR"            # article present mais mal classe (hors top 3)
ROUTING_ERROR = "ROUTING_ERROR"            # question large n'a declenche aucun chemin acte/procedure
VOCAB_ERROR = "VOCAB_ERROR"                # elargissement du vocabulaire incorrect (a tort ou absent)
DETERMINISTIC_VALUE_MISSING = "DETERMINISTIC_VALUE_MISSING"  # taux/montant attendu absent du texte retrouve
NO_RESULT = "NO_RESULT"                    # aucun resultat du tout (erreur technique)
FAUX_POSITIF_HORS_SUJET = "FAUX_POSITIF_HORS_SUJET"  # score trop confiant sur une question qui ne devrait rien trouver

# Seuil de score en-dessous duquel on considere qu'aucune vraie correspondance
# n'a ete trouvee - heuristique calibree sur nos scores RRF observes cette
# session (rang 1 seul ~0.016, avec bonus ~0.03-0.13 pour un vrai match).
# IMPORTANT : ceci est un PROXY sans LLM Judge - un score bas ne prouve pas
# que Gemini refuserait de repondre, juste que rien ne matche fortement.
SEUIL_SCORE_HORS_SUJET = 0.025


def calculer_reciprocal_rank(ids_trouves, ids_attendus):
    """Position du premier resultat correct (1-indexe), 0 si absent -
    utilise pour le MRR (Mean Reciprocal Rank, §13)."""
    for rang, article_id in enumerate(ids_trouves, start=1):
        if article_id in ids_attendus:
            return 1.0 / rang
    return 0.0


def verifier_valeurs_deterministes(expected_values, textes_articles_trouves):
    """Controle deterministe (§14/§16) : verifie que les taux/montants/
    delais attendus apparaissent bien dans le texte des articles
    retrouves - sans utiliser de LLM, juste une recherche de sous-chaine.
    Retourne (ok: bool, valeurs_manquantes: list)."""
    if not any(expected_values.values()):
        return True, []  # rien a verifier pour cette question

    texte_complet = " ".join(textes_articles_trouves).lower()
    manquantes = []
    for categorie, valeurs in expected_values.items():
        for valeur in valeurs:
            if valeur.lower() not in texte_complet:
                manquantes.append(f"{categorie}:{valeur}")
    return len(manquantes) == 0, manquantes


def executer_test_hors_perimetre(test, client, conn):
    """Test heuristique (SANS LLM Judge) pour les questions hors-perimetre
    et articles inexistants (§7.6/§7.10 du document de conception) : verifie
    que le MEILLEUR score trouve reste bas, signe qu'aucune vraie
    correspondance n'existe. Ne verifie PAS que Gemini refuserait
    effectivement de repondre (ca, seul le LLM Judge peut le confirmer) -
    c'est un proxy honnete, pas une preuve."""
    resultat = {
        "id": test["id"], "categorie": test["categorie"],
        "critical": test.get("critical", False), "erreurs": [],
    }
    try:
        vecteur = embed_question(client, test["question"])
        pivots = recherche_hybride(conn, vecteur, test["question"], top_k=5)
        meilleur_score = max((a.score for a in pivots), default=0.0)
        resultat["meilleur_score"] = round(meilleur_score, 4)

        if meilleur_score < SEUIL_SCORE_HORS_SUJET:
            resultat["statut"] = "PASS"
        else:
            resultat["statut"] = "FAIL"
            resultat["erreurs"].append(FAUX_POSITIF_HORS_SUJET)

        for cle in ("recall_1", "recall_3", "recall_5", "recall_10"):
            resultat[cle] = 1 if resultat["statut"] == "PASS" else 0
        resultat["mrr"] = 1.0 if resultat["statut"] == "PASS" else 0.0
        resultat["controle_deterministe_ok"] = True
    except Exception as e:
        resultat["erreurs"].append(NO_RESULT)
        resultat["statut"] = "FAIL"
        resultat["exception"] = f"{type(e).__name__}: {e}"
        for cle in ("recall_1", "recall_3", "recall_5", "recall_10"):
            resultat[cle] = 0
        resultat["mrr"] = 0.0
        resultat["controle_deterministe_ok"] = True
    return resultat


def executer_test_recherche(test, client, conn):
    """Execute UN test de type recherche standard, calcule toutes les
    metriques RAG et deterministes. Retourne un dict de resultat complet."""
    resultat = {
        "id": test["id"], "categorie": test["categorie"],
        "critical": test.get("critical", False),
        "erreurs": [],
    }
    try:
        vecteur = embed_question(client, test["question"])
        pivots = recherche_hybride(conn, vecteur, test["question"], top_k=10)
        ids_trouves = [a.article_id for a in pivots]
        textes_trouves = [a.text for a in pivots]
        attendus = set(test["articles_attendus"])

        # --- Metriques RAG (§13) ---
        resultat["recall_1"] = 1 if ids_trouves[:1] and set(ids_trouves[:1]) & attendus else 0
        resultat["recall_3"] = 1 if set(ids_trouves[:3]) & attendus else 0
        resultat["recall_5"] = 1 if set(ids_trouves[:5]) & attendus else 0
        resultat["recall_10"] = 1 if set(ids_trouves[:10]) & attendus else 0
        resultat["mrr"] = calculer_reciprocal_rank(ids_trouves, attendus)
        resultat["articles_trouves"] = ids_trouves[:5]

        # --- Controles deterministes (§14/§16) ---
        expected_values = test.get("expected_values") or {}
        ok_deterministe, manquantes = verifier_valeurs_deterministes(expected_values, textes_trouves[:5])
        resultat["controle_deterministe_ok"] = ok_deterministe
        if not ok_deterministe:
            resultat["erreurs"].append(DETERMINISTIC_VALUE_MISSING)

        # --- Classification et PASS/FAIL ---
        if resultat["recall_10"] == 0:
            resultat["erreurs"].append(RETRIEVAL_ERROR)
            resultat["statut"] = "FAIL"
        elif resultat["recall_3"] == 0:
            resultat["erreurs"].append(RANKING_ERROR)
            resultat["statut"] = "FAIL" if not ok_deterministe else "À ANALYSER"
        elif not ok_deterministe:
            resultat["statut"] = "À ANALYSER"
        else:
            resultat["statut"] = "PASS"

    except Exception as e:
        resultat["erreurs"].append(NO_RESULT)
        resultat["statut"] = "FAIL"
        resultat["exception"] = f"{type(e).__name__}: {e}"
        resultat["recall_1"] = resultat["recall_3"] = resultat["recall_5"] = resultat["recall_10"] = 0
        resultat["mrr"] = 0.0
        resultat["controle_deterministe_ok"] = True

    return resultat


def executer_test_vocabulaire(test):
    resultat = {"id": test["id"], "categorie": test["categorie"], "critical": test.get("critical", False), "erreurs": []}
    note = test.get("note") or ""
    resultat_elargi = elargir_question(test["question"])
    est_positif = "NE DOIT PAS rester inchange" in note or "doit bien" in note

    if est_positif:
        ok = resultat_elargi != test["question"]
    else:
        ok = resultat_elargi == test["question"]

    resultat["statut"] = "PASS" if ok else "FAIL"
    if not ok:
        resultat["erreurs"].append(VOCAB_ERROR)
    for cle in ("recall_1", "recall_3", "recall_5", "recall_10"):
        resultat[cle] = 1 if ok else 0
    resultat["mrr"] = 1.0 if ok else 0.0
    resultat["controle_deterministe_ok"] = True
    return resultat


def executer_test_routage(test):
    resultat = {"id": test["id"], "categorie": test["categorie"], "critical": test.get("critical", False), "erreurs": []}
    acte = detecter_acte_dans_question(test["question"])
    procedure = detecter_procedure_dans_question(test["question"])
    ok = bool(acte or procedure)
    resultat["statut"] = "PASS" if ok else "FAIL"
    if not ok:
        resultat["erreurs"].append(ROUTING_ERROR)
    for cle in ("recall_1", "recall_3", "recall_5", "recall_10"):
        resultat[cle] = 1 if ok else 0
    resultat["mrr"] = 1.0 if ok else 0.0
    resultat["controle_deterministe_ok"] = True
    return resultat


def charger_historique():
    if os.path.exists(FICHIER_HISTORIQUE):
        with open(FICHIER_HISTORIQUE, encoding="utf-8") as f:
            return json.load(f)
    return []


def sauvegarder_execution(historique, resume, version):
    historique.append({
        "date": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "resume": resume,
    })
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, ensure_ascii=False, indent=2)


def comparer_a_execution_precedente(historique, resume_actuel):
    """Regression Engine (§34) simplifie : compare le taux de reussite par
    categorie a la derniere execution enregistree, signale les baisses."""
    if not historique:
        return None
    precedent = historique[-1]["resume"]
    regressions = []
    for cat, stats in resume_actuel["par_categorie"].items():
        if cat in precedent.get("par_categorie", {}):
            taux_avant = precedent["par_categorie"][cat]["taux_reussite"]
            taux_apres = stats["taux_reussite"]
            if taux_apres < taux_avant - 0.001:  # tolerance flottante
                regressions.append((cat, taux_avant, taux_apres))
    return regressions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=datetime.now().strftime("%Y%m%d-%H%M"))
    args = parser.parse_args()

    DATABASE_URL = os.environ["DATABASE_URL"]
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    with open(FICHIER_BANQUE, encoding="utf-8") as f:
        tests = json.load(f)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True  # CRITIQUE : sans ceci, une seule requete en erreur bloque
                              # TOUTE la connexion (transaction "abortee") pour le reste
                              # de l'execution - chaque question doit rester independante
                              # des autres, une erreur ne doit jamais faire echouer en
                              # cascade les questions suivantes qui n'ont rien a voir.

    print(f"=== FISCA AI TEST ENGINE — version {args.version} ===")
    print(f"=== {len(tests)} tests à exécuter (recherche uniquement, aucun coût de génération) ===\n")

    resultats = []
    for test in tests:
        cat = test["categorie"]
        note = test.get("note") or ""

        if test["articles_attendus"] is None and "vocabulaire.py" in note:
            r = executer_test_vocabulaire(test)
        elif cat == "piège_large":
            r = executer_test_routage(test)
        elif cat in ("piège_hors_perimetre", "piège_article_inexistant"):
            r = executer_test_hors_perimetre(test, client, conn)
        elif test["articles_attendus"] is None:
            continue  # informationnel seul, pas de metrique
        else:
            r = executer_test_recherche(test, client, conn)

        resultats.append(r)
        marqueur = "🔴 CRITICAL" if (r["statut"] == "FAIL" and r["critical"]) else ("✅" if r["statut"] == "PASS" else "⚠️" if r["statut"] == "À ANALYSER" else "❌")
        print(f"[{r['id']}] {marqueur} {r['statut']} — {cat}" + (f" — {', '.join(r['erreurs'])}" if r["erreurs"] else ""))

    conn.close()

    # --- Agregation des scores ---
    par_categorie = defaultdict(lambda: {"pass": 0, "fail": 0, "analyse": 0, "total": 0})
    critical_fails = []
    for r in resultats:
        c = par_categorie[r["categorie"]]
        c["total"] += 1
        if r["statut"] == "PASS":
            c["pass"] += 1
        elif r["statut"] == "FAIL":
            c["fail"] += 1
            if r["critical"]:
                critical_fails.append(r["id"])
        else:
            c["analyse"] += 1

    for cat, c in par_categorie.items():
        c["taux_reussite"] = round(c["pass"] / c["total"], 4) if c["total"] else 0.0

    total_pass = sum(c["pass"] for c in par_categorie.values())
    total_tests = len(resultats)
    recall_1_moyen = sum(r.get("recall_1", 0) for r in resultats) / total_tests if total_tests else 0
    recall_3_moyen = sum(r.get("recall_3", 0) for r in resultats) / total_tests if total_tests else 0
    recall_5_moyen = sum(r.get("recall_5", 0) for r in resultats) / total_tests if total_tests else 0
    mrr_moyen = sum(r.get("mrr", 0) for r in resultats) / total_tests if total_tests else 0

    resume = {
        "total_tests": total_tests,
        "success_rate": round(total_pass / total_tests, 4) if total_tests else 0,
        "recall_1": round(recall_1_moyen, 4),
        "recall_3": round(recall_3_moyen, 4),
        "recall_5": round(recall_5_moyen, 4),
        "mrr": round(mrr_moyen, 4),
        "critical_fails": len(critical_fails),
        "par_categorie": {cat: dict(c) for cat, c in par_categorie.items()},
    }

    # --- Regression Engine (§34) ---
    historique = charger_historique()
    regressions = comparer_a_execution_precedente(historique, resume)
    sauvegarder_execution(historique, resume, args.version)

    # --- Rapport final (§48) ---
    print("\n" + "=" * 60)
    print("FISCA AI INTERNAL EVALUATION")
    print(f"VERSION: {args.version}")
    print("=" * 60)
    print(f"\nTests exécutés          : {total_tests}")
    print(f"Success Rate            : {resume['success_rate']*100:.1f}%")
    print(f"Critical Fail           : {resume['critical_fails']}")
    print(f"Recall@1                : {resume['recall_1']*100:.1f}%")
    print(f"Recall@3                : {resume['recall_3']*100:.1f}%")
    print(f"Recall@5                : {resume['recall_5']*100:.1f}%")
    print(f"MRR                     : {resume['mrr']:.3f}")

    print("\nPerformance par catégorie :")
    for cat, c in sorted(par_categorie.items(), key=lambda x: -x[1]["total"]):
        print(f"  {cat:25s} : {c['taux_reussite']*100:5.1f}%  ({c['pass']}/{c['total']})")

    if critical_fails:
        print(f"\n🔴 CRITICAL FAILS À EXAMINER EN PRIORITÉ : {', '.join(critical_fails)}")

    if regressions:
        print(f"\n⚠️  RÉGRESSIONS DÉTECTÉES depuis la dernière exécution ({historique[-2]['version'] if len(historique) > 1 else '?'}) :")
        for cat, avant, apres in regressions:
            print(f"  {cat:25s} : {avant*100:.1f}% → {apres*100:.1f}% (baisse de {(avant-apres)*100:.1f} points)")
    elif len(historique) > 1:
        print("\n✅ Aucune régression détectée depuis la dernière exécution.")

    print("\nRECOMMANDATION :", "PASS" if resume["critical_fails"] == 0 and resume["success_rate"] >= 0.85 else "À EXAMINER AVANT DÉPLOIEMENT")


if __name__ == "__main__":
    main()
