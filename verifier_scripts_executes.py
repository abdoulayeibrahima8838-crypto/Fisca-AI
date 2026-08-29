#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verifier_scripts_executes.py — Ne modifie RIEN, verifie juste quels
scripts de correction ont deja ete executes sur ce serveur, en inspectant
l'etat actuel des donnees. A lancer depuis le Shell Render.

Usage :
    python verifier_scripts_executes.py
"""
import json
import os

print("=== Vérification de l'état des scripts de correction ===\n")

# --- 1) Fichiers JSON de correction des articles ---
if not os.path.exists("cgi2026_articles_complet.json"):
    print("❌ cgi2026_articles_complet.json introuvable ici — vérifie le dossier courant.")
else:
    with open("cgi2026_articles_complet.json", encoding="utf-8") as f:
        articles = json.load(f)
    par_id = {a["article_id"]: a for a in articles}

    verifications = [
        ("corriger_chapitre_regimes_imposition.py", "120", "matiere_fiscale", "Impôt sur les sociétés"),
        ("corriger_sections_procedures.py", "781", "section_titre", "Représentation des contribuables"),
        ("corriger_chapitre_regimes_imposition_complement.py", "123", "matiere_fiscale", "Impôt sur les sociétés"),
        ("corriger_chapitres_ibapp_tua.py", "73", "matiere_fiscale", "Impôt sur les bénéfices d’affaires des personnes physiques"),
        ("corriger_chapitres_licences_reseaux.py", "297", "matiere_fiscale", "Contribution des licences"),
    ]

    for nom_script, article_id, champ, valeur_attendue in verifications:
        art = par_id.get(article_id)
        if art is None:
            print(f"❓ {nom_script:55s} — article {article_id} introuvable")
            continue
        valeur_actuelle = art.get(champ)
        fait = valeur_actuelle == valeur_attendue
        marqueur = "✅ DÉJÀ FAIT" if fait else "❌ PAS ENCORE FAIT"
        print(f"{marqueur:20s} {nom_script:50s} (art. {article_id}: {champ}={valeur_actuelle!r})")

print()

# --- 2) Table journal_conversations (base de données) ---
try:
    import psycopg2
    DATABASE_URL = os.environ["DATABASE_URL"]
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'journal_conversations')")
    existe = cur.fetchone()[0]
    marqueur = "✅ DÉJÀ FAIT" if existe else "❌ PAS ENCORE FAIT"
    print(f"{marqueur:20s} creer_table_journal.py (table 'journal_conversations' {'existe' if existe else 'absente'})")
    conn.close()
except Exception as e:
    print(f"❓ Impossible de vérifier la table journal_conversations : {type(e).__name__}: {e}")
