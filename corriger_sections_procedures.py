#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_sections_procedures.py — A LANCER UNE SEULE FOIS depuis le Shell
Render.

Complete l'Espace Procedures : restitue les derniers titres de section
tronques trouves en construisant les fiches par procedure / par acte,
tous verifies directement contre le PDF source du CGI 2026.

Un seul cas (article 814) reste volontairement NON MODIFIE : aucun titre
de sous-section propre n'a ete retrouve dans le texte source malgre
plusieurs recherches - par prudence, on ne force pas un titre invente.

Usage :
    python corriger_sections_procedures.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_complet.json"

CORRECTIONS_SECTION = {
    "638": "Procédure d’identification des marchandises et magasins",
    "639": "Procédure d’identification des marchandises et magasins",
    "675": "Conséquences des irrégularités de la procédure",
    "762": "Hypothèque légale du Trésor",
    "763": "Hypothèque légale du Trésor",
    "764": "Hypothèque légale du Trésor",
    "765": "Hypothèque légale du Trésor",
    "781": "Représentation des contribuables",
    "782": "Représentation des contribuables",
    "815": "Sanctions relatives aux retenues à la source",
    "816": "Sanctions relatives à l’enregistrement et au timbre",
    "817": "Sanctions relatives à l’enregistrement et au timbre",
}

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

nb_corriges = 0
for art in articles:
    if art["article_id"] in CORRECTIONS_SECTION:
        art["section_titre"] = CORRECTIONS_SECTION[art["article_id"]]
        nb_corriges += 1
        print(f"Article {art['article_id']} : section = {art['section_titre']!r}")

with open(CHEMIN_FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n{nb_corriges}/{len(CORRECTIONS_SECTION)} articles corrigés.")
print("Note : l'article 814 n'a volontairement pas été modifié — aucun titre")
print("de sous-section propre retrouvé dans le PDF source malgré vérification.")
