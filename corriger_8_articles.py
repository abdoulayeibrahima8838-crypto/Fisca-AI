#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_8_articles.py — A LANCER UNE SEULE FOIS depuis le Shell Render.

Corrige directement, en place, les 8 articles dont le texte etait contamine
(161, 162, 163, 166, 229, 333, 335, 336) dans cgi2026_articles_corrige.json.

Contourne completement GitHub - travaille directement sur le fichier tel
qu'il se trouve deja sur Render (celui utilise par generer_embeddings.py).

Usage :
    python corriger_8_articles.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_corrige.json"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

corrections = {
    "161": (
        "Art. 161.- L’impôt sur les revenus locatifs est applicable aux revenus de la\n"
        "location des immeubles bâtis ou non\n"
        "bâtis, ainsi que les revenus accessoires, quel que soit leur usage.\n"
    ),
    "162": (
        "Art. 162.- 1) L’impôt est dû par les per-\n"
        "sonnes bénéficiaires de revenus loca-\n"
        "tifs. Sont compris dans la catégorie\n"
        "des revenus locatifs :\n"
        "a) les revenus des propriétés bâties\n"
        "telles que les maisons et usines\n"
        "ainsi que ceux provenant de :\n"
        "i) l’outillage des établissements\n"
        "industriels attachés au fonds\n"
        "à perpétuelle demeure, ou\n"
        "reposant sur des fondations\n"
        "spéciales faisant corps avec\n"
        "l’ensemble ;\n"
        "ii) toutes installations commer-\n"
        "ciales ou industrielles assimi-\n"
        "lables à des constructions ;\n"
        "b) les revenus de la location\n"
        "du droit d’affichage, de la\n"
        "concession du droit d’exploi-\n"
        "tation des carrières, de rede-\n"
        "vances analogues ayant leur\n"
        "origine dans le droit de pro-\n"
        "priété ou d’usufruit ;\n"
        "c) les revenus des propriétés non\n"
        "bâties de toute nature y compris\n"
        "ceux des terrains occupés par\n"
        "des carrières et les mines ;\n"
        "d) les loyers des baux à construc-\n"
        "tion.\n"
        "2) Sont également soumis à l’impôt\n"
        "sur les revenus locatifs :\n"
        "a) les revenus résultant de la sous-\n"
        "location d’un bien visé au point 1\n"
        "ci-dessus ;\n"
        "b) les revenus en nature résultant\n"
        "de la mise à disposition à titre\n"
        "gratuit d’un bien visé au point 1\n"
        "ci-dessus ;\n"
        "c) les revenus en nature corres-\n"
        "pondant à la mise à disposition\n"
        "d’un ou de plusieurs logements\n"
        "secondaires dont le propriétaire\n"
        "se réserve la jouissance.\n"
    ),
    "163": (
        "Art. 163.- Ne sont pas soumis à l’impôt sur les revenus locatifs :\n"
        "1) Les loyers de toute nature d’immeubles appartenant à des personnes\n"
        "morales soumises à l’impôt sur les sociétés.\n"
        "2) Les loyers de toute nature d’immeubles appartenant à l’État, aux\n"
        "collectivités territoriales et à leurs éta-\n"
        "blissements publics n’ayant pas un caractère industriel et commercial.\n"
        "3) Les loyers des chambres d’hôtel et\n"
        "d’établissements assimilés.\n"
        "4) Les loyers dont le cumul par bailleur\n"
        "n’excède pas vingt mille (20 000) francs\n"
        "CFA par mois.\n"
    ),
    "166": (
        "Art. 166.- 1) Le taux de l'impôt sur les\n"
        "revenus locatifs est de 12%.\n"
        "2) Toutefois, le taux est de 6% pour :\n"
        "a) les revenus en nature résultant\n"
        "de la mise à disposition à titre\n"
        "gratuit d'un bien visé à l'article\n"
        "162 du présent Code ;\n"
        "b) les revenus en nature correspondant à la mise à disposition d'un\n"
        "ou plusieurs logements secondaires dont le propriétaire se réserve\n"
        "la jouissance.\n"
    ),
    "229": (
        "Art. 229.- 1) L’impôt sur les plus-values\n"
        "immobilières est perçu à l’occasion\n"
        "de l’établissement des certificats de\n"
        "ventes d’immeubles par les notaires,\n"
        "les agents d’affaires et autres officiers\n"
        "ministériels habilités à instrumenter.\n"
        "2) L’impôt est reversé auprès du Receveur des Impôts territorialement compétent dans le délai fixé à l’article 481\n"
        "du présent Code.\n"
        "4) Dans tous les cas, le montant de\n"
        "l’impôt ne saurait être inférieur\n"
        "aux tarifs ci-après :\n"
        "\n"
        "Pour les terrains nus : 75 000 FCFA à Niamey, 50 000 FCFA dans les "
        "autres chefs-lieux de régions, 25 000 FCFA dans les autres localités.\n"
        "Pour les immeubles bâtis : 500 000 FCFA à Niamey, 300 000 FCFA dans "
        "les autres chefs-lieux de régions, 100 000 FCFA dans les autres localités.\n"
    ),
    "333": (
        "Art. 333.- 1) L'exigibilité de la taxe sur\n"
        "la valeur ajoutée est constituée par le\n"
        "droit dont disposent les services des\n"
        "impôts pour exiger du redevable, à\n"
        "partir d'une date donnée, le paiement\n"
        "de la taxe.\n"
        "2) L'exigibilité de la taxe sur la valeur\n"
        "ajoutée intervient :\n"
        "a) pour les importations, au moment de l'enregistrement de\n"
        "la déclaration de mise à la\n"
        "consommation des biens ;\n"
        "b) pour les livraisons de biens : à la\n"
        "suite de la livraison des biens en\n"
        "question ;\n"
        "c) pour les prestations de services,\n"
        "à la suite de l'accomplissement\n"
        "du service ;\n"
        "d) pour les travaux immobiliers, à\n"
        "la suite de l'achèvement des travaux ou tranches de travaux ;\n"
        "e) pour les livraisons ou prestations\n"
        "de services à soi-même, au moment de leur première utilisation ;\n"
        "f) pour les opérations de crédit-bail,\n"
        "à la suite de l'encaissement du\n"
        "loyer par le crédit-bailleur ;\n"
        "g) S'il s'agit de livraisons ou de\n"
        "prestations de services à l'État,\n"
        "aux collectivités territoriales ou\n"
        "à leurs démembrements n'ayant\n"
        "pas un caractère industriel ou\n"
        "commercial, un différé de paiement de la taxe est accordé par\n"
        "le service des impôts jusqu'au\n"
        "moment du paiement par les\n"
        "services du Trésor Public.\n"
        "3) La constatation du fait générateur\n"
        "ne peut être postérieure à la facturation totale ou partielle.\n"
        "4) Le versement d'avances ou\n"
        "d'acomptes rend la taxe exigible sur le\n"
        "montant dudit versement, que l'opération en cause soit matériellement réalisée ou non.\n"
    ),
    "335": (
        "Art. 335.- Toute personne physique ou\n"
        "morale qui mentionne la TVA sur une\n"
        "facture ou un document en tenant lieu\n"
        "est redevable de la taxe du seul fait de\n"
        "sa facturation.\n"
    ),
    "336": (
        "Art. 336.- 1) Le taux normal de la taxe\n"
        "sur la valeur ajoutée est fixé à 19%.\n"
        "2) Toutefois, sont soumises à un taux\n"
        "réduit :\n"
        "a) de 10% :\n"
        "1° les activités de transport terrestre de personnes et de\n"
        "marchandises ;\n"
        "2° les activités de prestations\n"
        "d'hébergement et de restauration ;\n"
        "b) de 5%, les opérations d'importation ou de vente à l'intérieur des\n"
        "produits suivants :\n"
        "1° le sucre ;\n"
        "2° l'huile alimentaire ;\n"
        "3° les aliments destinés aux animaux d'élevage ;\n"
        "4° le lait manufacturé ;\n"
        "5° la farine de maïs, de mil, de\n"
        "millet, de sorgho, de riz, de\n"
        "blé et de fonio.\n"
    ),
}

nb_corriges = 0
for art in articles:
    if art["article_id"] in corrections:
        art["text"] = corrections[art["article_id"]]
        nb_corriges += 1
        print(f"Article {art['article_id']} corrigé ({len(art['text'])} caractères).")

with open(CHEMIN_FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"\n{nb_corriges}/8 articles corrigés et sauvegardés dans {CHEMIN_FICHIER}.")
print("Le fichier a été mis à jour directement sur Render, sans passer par GitHub.")
