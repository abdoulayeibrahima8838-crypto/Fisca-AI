#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_lot5.py — A LANCER UNE SEULE FOIS depuis le Shell Render.

Lot 5 : articles 534, 549, 556, 584, 618.

Usage :
    python corriger_lot5.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_corrige.json"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

corrections = {
    "534": (
        "Art. 534.- 1) Au cas où il n’y aurait pas\n"
        "partage immédiat de succession, il est\n"
        "déposé à la Recette des Impôts, une\n"
        "provision de 15% sur l’actif net recueilli.\n"
        "2) La régularisation est effectuée au\n"
        "moment du partage qui doit intervenir\n"
        "dans une période d’un (1) an, à compter de la date de perception de la provision.\n"
        "3) En cas d’indivision et à défaut de\n"
        "partage dans les conditions sus-indiquées, les droits de mutation sont\n"
        "liquidés au taux de 25% sur l’actif net\n"
        "recueilli.\n"
    ),
    "549": (
        "Art. 549.- Sont également soumis au\n"
        "droit de timbre de dimension :\n"
        "a) les demandes adressées\n"
        "aux administrations publiques de l’Etat et ses démembrements ainsi qu’aux\n"
        "établissements publics et\n"
        "offices, sociétés d’Etat et\n"
        "sociétés d’économie mixte,\n"
        "sous peine de rejet ;\n"
        "b) toute légalisation de document ou de signature quel\n"
        "que soit le fonctionnaire ou\n"
        "l’officier ministériel qui a procédé à la légalisation.\n"
    ),
    "556": (
        "Art. 556.- 1) Les lettres de change tirées\n"
        "par seconde, troisième ou quatrième\n"
        "peuvent, quoi qu’étant écrites sur papier non timbré être présentées à la Recette des Impôts dans le cas de protêt,\n"
        "sans qu’il y ait lieu au droit de timbre\n"
        "et à l’amende, pourvu que la première\n"
        "écrite sur papier au timbre proportionnel, soit représentée conjointement à\n"
        "la Recette des impôts.\n"
        "2) Toutefois, si la première timbrée ou\n"
        "visée pour timbre, n’est pas jointe à\n"
        "celle mise en circulation et destinée à\n"
        "recevoir les endossements, le timbre\n"
        "ou visa pour timbre doit toujours être\n"
        "apposé sur cette dernière, sous les\n"
        "peines prescrites par le présent Code.\n"
    ),
    "584": (
        "Art. 584.- Il est apposé un timbre fiscal de vingt-cinq mille (25 000) francs\n"
        "CFA sur les originaux ou exemplaires\n"
        "uniques :\n"
        "a) de tous les actes administratifs conférant agrément, autorisation, permis, certificat à\n"
        "caractère professionnel, délivrés par les administrations\n"
        "publiques de l’Etat et de ses\n"
        "démembrements, les établissements publics, les sociétés\n"
        "d’Etat, les sociétés d’économie mixte et les sociétés privées concessionnaires de\n"
        "service public. Toutefois, les droits de\n"
        "timbres relatifs à l’inscription\n"
        "au registre du commerce et\n"
        "du crédit mobilier sont plafonnés à onze mille cinq cents\n"
        "(11 500) francs CFA en application du point 30° de l’article\n"
        "548 du présent Code et du\n"
        "point 1° du f) du paragraphe\n"
        "1 de l’article 585 ci-dessous ;\n"
        "b) des carnets de transit routier, relatifs aux véhicules de\n"
        "toutes catégories destinées\n"
        "au marché nigérien lors de\n"
        "leur établissement dans les\n"
        "unités douanières ;\n"
        "c) des plans de bâtiments, d’ouvrages, documents d’urbanisme opérationnel, et autres\n"
        "dessins et schémas destinés\n"
        "aux appels d’offres, d’autorisation de construire ;\n"
        "d) des permis et autorisation de\n"
        "chasse, de capture d’animaux\n"
        "et oiseaux sauvages ;\n"
        "e) des actes et formalités relatifs aux marchés publics de\n"
        "toute nature, à savoir l’original\n"
        "du marché et l’original des\n"
        "procès-verbaux de réception\n"
        "définitive.\n"
    ),
    "618": (
        "Art. 618.- Sauf les exonérations prévues à l’article 543 et au point 28° de\n"
        "l’article 437 du présent Code sont soumises aux droits de timbre, mais enregistrées en débet, toutes décisions\n"
        "rendues par les juridictions statuant\n"
        "en matière administrative.\n"
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

print(f"\n{nb_corriges}/5 articles corrigés (Lot 5).")
