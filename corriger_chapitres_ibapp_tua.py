#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_chapitres_ibapp_tua.py — A LANCER UNE SEULE FOIS depuis le Shell
Render.

Suite de la verification systematique des chapitres tronques (demandee
apres le cas du regime du forfait / NIF P) : deux autres chapitres
entiers etaient invisibles a la classification par matiere fiscale :

- "Impôt sur les bénéfices d'affaires des" -> vrai titre : "Impôt sur les
  bénéfices d'affaires des personnes physiques" (IBAPP), 14 articles
  (73-86), tous "Non classé" jusqu'ici.
- "Taxe unique sur" -> vrai titre : "Taxe unique sur les assurances"
  (TUA, deja connue dans vocabulaire.py), 10 articles (395-404), tous
  "Non classé" jusqu'ici.

Usage :
    python corriger_chapitres_ibapp_tua.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_complet.json"

ARTICLES_IBAPP = ["73", "74", "75", "76", "77", "78", "79", "80", "81", "82", "83", "84", "85", "86"]
TITRE_IBAPP = "Impôt sur les bénéfices d’affaires des personnes physiques"

ARTICLES_TUA = ["395", "396", "397", "398", "399", "400", "401", "402", "403", "404"]
TITRE_TUA = "Taxe unique sur les assurances"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

nb_corriges = 0
for art in articles:
    if art["article_id"] in ARTICLES_IBAPP:
        art["chapitre_titre"] = TITRE_IBAPP
        art["matiere_fiscale"] = TITRE_IBAPP
        nb_corriges += 1
        print(f"Article {art['article_id']} (IBAPP) corrigé.")
    elif art["article_id"] in ARTICLES_TUA:
        art["chapitre_titre"] = TITRE_TUA
        art["matiere_fiscale"] = TITRE_TUA
        nb_corriges += 1
        print(f"Article {art['article_id']} (TUA) corrigé.")

with open(CHEMIN_FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n{nb_corriges}/{len(ARTICLES_IBAPP) + len(ARTICLES_TUA)} articles corrigés.")
