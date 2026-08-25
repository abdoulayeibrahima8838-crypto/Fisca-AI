# -*- coding: utf-8 -*-
"""
enrichir_groupe_b_final.py — Derniers sujets du Groupe B (Espace Procédures) :
Déductions et Transaction/remise gracieuse. Contrairement aux autres sujets
du Groupe B (qui se sont reveles etre des sections deja existantes, juste
mal exploitees), ceux-ci sont genuinement disperses a travers de nombreuses
matieres fiscales - pas de section unique a exploiter. Classification par
tag transversal (un article peut porter plusieurs tags a la fois).

Usage : python3 enrichir_groupe_b_final.py
Lit/Ecrit : cgi2026_articles_complet.json (ajoute le champ "procedures_transversales")
"""
import json
import re

FICHIER = "cgi2026_articles_complet.json"

with open(FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

MOTIFS = {
    "Déductions": [r"déductible", r"droit à déduction", r"charges? déductibles?"],
    "Transaction et remise gracieuse": [r"remises? ou modérations?", r"voie de transaction", r"procédure de transaction", r"transaction fiscale"],
}

nb_tags = {k: 0 for k in MOTIFS}
for a in articles:
    texte_lower = a["text"].lower()
    tags = []
    for sujet, motifs in MOTIFS.items():
        if any(re.search(m, texte_lower) for m in motifs):
            tags.append(sujet)
            nb_tags[sujet] += 1
    a["procedures_transversales"] = tags

with open(FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print("Classification transversale terminée.")
for sujet, n in nb_tags.items():
    print(f"  {sujet} : {n} article(s) taggés")
