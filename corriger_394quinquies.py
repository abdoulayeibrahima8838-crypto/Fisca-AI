#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_394quinquies.py — A LANCER UNE SEULE FOIS depuis le Shell Render.

Cas particulier : l'article "394quinquies" contenait en realite 15 articles
distincts fusionnes par erreur (394quinquies a 394noniesdecies), avec en
plus des metadonnees de chapitre/section incorrectes (copiees d'un article
plus ancien). Ce script :
1. Corrige le texte ET les metadonnees de 394quinquies.
2. CREE 14 nouvelles entrees d'articles qui n'existaient pas du tout
   auparavant (394sexies a 394noniesdecies).

Usage :
    python corriger_394quinquies.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_corrige.json"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

BASE_METADATA = {
    "article_num": 394,
    "livre_num": "2",
    "livre_titre": "Impôts indirects",
    "titre_num": "3",
    "titre_titre": "Autres contributions et taxes indirectes",
}

CHAPITRE_1BIS = {
    "chapitre_num": "1 bis",
    "chapitre_titre": "Taxe sur les dépôts et transferts d’argent",
}
CHAPITRE_1TER = {
    "chapitre_num": "1 ter",
    "chapitre_titre": "Taxe sur les paiements en numéraire",
}

# (suffixe, texte, page, section_num, section_titre, ssection_num, ssection_titre)
NOUVEAUX_ARTICLES = [
    ("quinquies",
     "Art.394 quinquies.- La taxe est assise sur le montant brut du dépôt ou du transfert, avant déduction des frais.\n",
     152, CHAPITRE_1BIS, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "1", "Assiette"),
    ("sexies",
     "Art.394 sexies.- Le taux de la taxe est de 0,5% du montant brut déposé ou transféré. Ce taux est porté à 5% pour les montants supérieurs à deux millions (2.000.000) de francs CFA.\n",
     152, CHAPITRE_1BIS, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "2", "Taux"),
    ("septies",
     "Art.394 septies.- Le fait générateur est constitué par le dépôt effectif ou l’ordre de transfert d’argent.\n",
     152, CHAPITRE_1BIS, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "3", "Fait générateur et exigibilité"),
    ("octies",
     "Art.394 octies.- L’exigibilité intervient à la suite de la validation de la transaction par l’opérateur.\n",
     152, CHAPITRE_1BIS, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "3", "Fait générateur et exigibilité"),
    ("nonies",
     ("Art. 394 nonies.- La taxe est perçue, au moment du dépôt ou du transfert sur un compte, par les personnes visées "
      "à l’Article 394 ter ci-dessus et reversée suivant un modèle de déclaration fourni à cet effet par l’Administration fiscale.\n"
      "Les contribuables assujettis à l’obligation de collecter la taxe sont tenus de paramétrer leur système d’information dans ce sens.\n"
      "Les modalités de recouvrement, de contrôle et de sanctions sont, mutatis mutandis, celles en matière de Taxe sur les Activités Financières.\n"
      "En tant que de besoin, un acte règlementaire sera pris à cet effet.\n"
      "(Modifié par Ordonnance N° 2025-44 du 31 décembre 2025 portant Loi de Finances pour l’année budgétaire 2026.)\n"),
     152, CHAPITRE_1BIS, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "4", "Déclaration et paiement"),
    ("decies",
     "Art. 394 decies.- Sont passibles de la taxe, les paiements en numéraire effectués, par les personnes physiques et morales.\n",
     152, CHAPITRE_1TER, "1", "Champ d’application", "1", "Opérations imposables"),
    ("undecies",
     "Art. 394 undecies.- Sont chargées de la collecte et du reversement de la taxe, les entreprises soumises à un régime réel d’imposition.\n",
     152, CHAPITRE_1TER, "1", "Champ d’application", "2", "Personnes imposables"),
    ("duodecies",
     ("Art. 394 duodecies.- Sont exonérés de la taxe :\n"
      "- les paiements de montant inférieur ou égal à cent mille (100.000) francs CFA ;\n"
      "- les paiements des impôts et taxes.\n"),
     152, CHAPITRE_1TER, "1", "Champ d’application", "3", "Exonérations"),
    ("terdecies",
     "Art. 394 terdecies.- La taxe est assise sur le montant hors taxe sur la valeur ajoutée du paiement effectué.\n",
     153, CHAPITRE_1TER, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "1", "Assiette"),
    ("quaterdecies",
     "Art. 394 quaterdecies.- Le taux de la taxe est de 1%.\n",
     153, CHAPITRE_1TER, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "2", "Taux"),
    ("quinquiesdecies",
     "Art. 394 quinquiesdecies.- Le fait générateur de la taxe est constitué par le paiement.\n",
     153, CHAPITRE_1TER, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "3", "Fait générateur et exigibilité"),
    ("sexiesdecies",
     "Art. 394 sexiesdecies.- La taxe est exigible au plus tard le quinze (15) du mois qui suit celui du fait générateur, sous les mêmes conditions que la taxe sur la valeur ajoutée.\n",
     153, CHAPITRE_1TER, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "3", "Fait générateur et exigibilité"),
    ("septiesdecies",
     "Art. 394 septiesdecies.- Les modalités de déclaration, de contrôle, de recouvrement et de traitement du contentieux de la taxe ainsi que les obligations et sanctions sont les mêmes qu’en matière de taxe sur la valeur ajoutée.\n",
     153, CHAPITRE_1TER, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "4", "Déclaration et paiement"),
    ("octiesdecies",
     "Art. 394 octiesdecies.- Les entreprises soumises à un régime réel d’imposition sont tenues de collecter de reverser la taxe à la recette des impôts de rattachement.\n",
     153, CHAPITRE_1TER, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "4", "Déclaration et paiement"),
    ("noniesdecies",
     ("Art. 394 noniesdecies.- En tant que de besoin, des mesures réglementaires sont prises pour l’application des présentes dispositions.\n"
      "(Modifié par Ordonnance N° 2025-44 du 31 décembre 2025 portant Loi de Finances pour l’année budgétaire 2026.)\n"),
     153, CHAPITRE_1TER, "2", "Assiette, taux, fait générateur, exigibilité et recouvrement", "4", "Déclaration et paiement"),
]

# Retirer l'ancienne entree 394quinquies contaminee, on va la recreer proprement
articles = [a for a in articles if a["article_id"] != "394quinquies"]

for suffixe, texte, page, chapitre, section_num, section_titre, ssection_num, ssection_titre in NOUVEAUX_ARTICLES:
    nouvelle_entree = {
        "article_id": f"394{suffixe}",
        "article_suffix": suffixe,
        "page": page,
        "section_num": section_num,
        "section_titre": section_titre,
        "ssection_num": ssection_num,
        "ssection_titre": ssection_titre,
        "text": texte,
        **BASE_METADATA,
        **chapitre,
    }
    articles.append(nouvelle_entree)
    print(f"Article 394{suffixe} créé ({len(texte)} caractères).")

with open(CHEMIN_FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n15 articles traités (1 corrigé + 14 créés). Total articles en base : {len(articles)}.")
print("IMPORTANT : les 14 nouveaux articles n'ont pas encore d'embedding — le prochain lancement de generer_embeddings.py les traitera automatiquement (nouveaux articles = jamais d'embedding = traites normalement).")
