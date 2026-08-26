#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_chapitre_regimes_imposition.py — A LANCER UNE SEULE FOIS depuis
le Shell Render.

Corrige un titre de chapitre tronque ("Dispositions communes à l'impôt
sur les") qui empechait 6 articles cles (118, 119, 120, 121, 122, 131 -
les VRAIS articles definisseurs des regimes reel normal/simplifie/forfait,
notamment le regime du forfait pour NIF P, jusqu'ici invisibles a la
classification par matiere fiscale) d'etre correctement classes.

Vrai titre retrouve dans le PDF source : "Dispositions communes à
l'impôt sur les sociétés et à l'impôt sur les bénéfices d'affaires des
personnes physiques".

Usage :
    python corriger_chapitre_regimes_imposition.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_complet.json"

ARTICLES_CONCERNES = ["118", "119", "120", "121", "122", "131"]
VRAI_TITRE_CHAPITRE = (
    "Dispositions communes à l’impôt sur les sociétés et à l’impôt sur "
    "les bénéfices d’affaires des personnes physiques"
)

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

nb_corriges = 0
for art in articles:
    if art["article_id"] in ARTICLES_CONCERNES:
        art["chapitre_titre"] = VRAI_TITRE_CHAPITRE
        art["matiere_fiscale"] = "Impôt sur les sociétés"
        nb_corriges += 1
        print(f"Article {art['article_id']} corrigé : chapitre restitué, matière = Impôt sur les sociétés.")

with open(CHEMIN_FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n{nb_corriges}/{len(ARTICLES_CONCERNES)} articles corrigés et sauvegardés dans {CHEMIN_FICHIER}.")
print("N'oublie pas : le texte des articles lui-même n'a pas changé, seules les métadonnées de classification sont corrigées.")
