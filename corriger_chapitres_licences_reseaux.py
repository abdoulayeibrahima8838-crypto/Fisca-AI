#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_chapitres_licences_reseaux.py — A LANCER UNE SEULE FOIS depuis
le Shell Render.

Dernier volet de la verification systematique des chapitres tronques
(suite du cas regime du forfait / NIF P) :

- "Contribution des l" -> vrai titre : "Contribution des licences",
  5 articles (297-301), "Non classé" jusqu'ici.
- "Taxe sur l'utilisation des réseaux" -> vrai titre : "Taxe sur
  l'utilisation des réseaux de télécommunications", 7 articles
  (405-411), "Non classé" jusqu'ici.

Avec ce script, la verification systematique des chapitres tronques est
terminee : seul l'article 1 (dispositions generales, legitimement sans
chapitre specifique) reste "Non classé", ce qui est normal.

Usage :
    python corriger_chapitres_licences_reseaux.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_complet.json"

ARTICLES_LICENCES = ["297", "298", "299", "300", "301"]
TITRE_LICENCES = "Contribution des licences"

ARTICLES_RESEAUX = ["405", "406", "407", "408", "409", "410", "411"]
TITRE_RESEAUX = "Taxe sur l’utilisation des réseaux de télécommunications"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

nb_corriges = 0
for art in articles:
    if art["article_id"] in ARTICLES_LICENCES:
        art["chapitre_titre"] = TITRE_LICENCES
        art["matiere_fiscale"] = TITRE_LICENCES
        nb_corriges += 1
        print(f"Article {art['article_id']} (Licences) corrigé.")
    elif art["article_id"] in ARTICLES_RESEAUX:
        art["chapitre_titre"] = TITRE_RESEAUX
        art["matiere_fiscale"] = TITRE_RESEAUX
        nb_corriges += 1
        print(f"Article {art['article_id']} (Réseaux télécom) corrigé.")

with open(CHEMIN_FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n{nb_corriges}/{len(ARTICLES_LICENCES) + len(ARTICLES_RESEAUX)} articles corrigés.")
