#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_chapitre_regimes_imposition_complement.py — A LANCER UNE SEULE
FOIS depuis le Shell Render.

COMPLEMENT au script corriger_chapitre_regimes_imposition.py de la
session precedente : celui-ci n'avait corrige que 6 articles (118, 119,
120, 121, 122, 131) sur les 23 que compte reellement le chapitre
"Dispositions communes à l'impôt sur les sociétés et à l'impôt sur les
bénéfices d'affaires des personnes physiques" - 17 articles etaient
restes "Non classe" sans qu'on s'en apercoive, decouverts en verifiant
si le probleme du regime du forfait (NIF P) pouvait toucher d'autres
points.

Usage :
    python corriger_chapitre_regimes_imposition_complement.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_complet.json"

ARTICLES_MANQUES = [
    "113", "114", "115", "116", "117", "123", "124", "125", "126",
    "127", "128", "129", "130", "132", "133", "134", "135",
]
VRAI_TITRE_CHAPITRE = (
    "Dispositions communes à l’impôt sur les sociétés et à l’impôt sur "
    "les bénéfices d’affaires des personnes physiques"
)

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

nb_corriges = 0
for art in articles:
    if art["article_id"] in ARTICLES_MANQUES:
        art["chapitre_titre"] = VRAI_TITRE_CHAPITRE
        art["matiere_fiscale"] = "Impôt sur les sociétés"
        nb_corriges += 1
        print(f"Article {art['article_id']} corrigé : chapitre restitué, matière = Impôt sur les sociétés.")

with open(CHEMIN_FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n{nb_corriges}/{len(ARTICLES_MANQUES)} articles corrigés.")
print("Avec les 6 déjà corrigés hier soir (118,119,120,121,122,131),")
print("les 23 articles du chapitre sont maintenant tous correctement classés.")
