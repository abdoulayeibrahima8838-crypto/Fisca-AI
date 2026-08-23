#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_lot4.py — A LANCER UNE SEULE FOIS depuis le Shell Render.

Lot 4 : articles 390, 394, 476.
(L'article 437 est mis de côté pour une session dédiée — il fait plus de
43 points et s'étend sur au moins 5-6 pages du PDF source.)

Usage :
    python corriger_lot4.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_corrige.json"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

corrections = {
    "390": (
        "Art. 390.- 1) L’assiette de la Taxe sur\n"
        "les Activités Financières est constituée par le montant brut des intérêts,\n"
        "des agios, des commissions et autres\n"
        "rémunérations, à l’exclusion de la taxe\n"
        "elle-même.\n"
        "2) Lorsqu’une rémunération est partagée entre des personnes visées à\n"
        "l’article 387 du présent Code, chacune est imposée sur la fraction de la\n"
        "rémunération qui lui est définitivement\n"
        "acquise.\n"
    ),
    "394": (
        "Art. 394.- Les modalités de déclaration, de contrôle, de recouvrement\n"
        "et de traitement du contentieux de la\n"
        "taxe ainsi que les obligations et sanctions sont les mêmes qu’en matière de\n"
        "taxe sur la valeur ajoutée.\n"
    ),
    "476": (
        "Art. 476.- 1) Sont enregistrés au droit\n"
        "fixe de six mille (6 000) francs CFA :\n"
        "a) les procès-verbaux de conciliation dressés par les juges,\n"
        "desquels il ne résulte aucune\n"
        "disposition donnant lieu au\n"
        "droit proportionnel ou dont le\n"
        "droit proportionnel ne s’élèverait pas au minimum de\n"
        "perception ;\n"
        "b) les jugements de simple police et des juges, les ordonnances de référé, lorsque ces\n"
        "jugements et ordonnances\n"
        "ne peuvent pas donner lieu\n"
        "au droit proportionnel, ou\n"
        "donnent lieu au paiement d’un\n"
        "droit inférieur à six mille (6\n"
        "000) francs CFA.\n"
        "c) les ordonnances portant injonction de payer, qu’il y ait\n"
        "titre ou non.\n"
        "2) Sont enregistrés au droit fixe de dix\n"
        "mille (10 000) francs CFA :\n"
        "a) les jugements en matière gracieuse, les jugements de la\n"
        "police correctionnelle et les\n"
        "jugements de première instance en premier et en dernier ressort contenant des\n"
        "dispositions définitives qui ne\n"
        "peuvent donner lieu au droit\n"
        "proportionnel ;\n"
        "b) les arrêts sur les jugements\n"
        "en matière gracieuse, ou\n"
        "les arrêts sur appels d’ordonnances, de toute nature\n"
        "lorsqu’ils ne peuvent donner\n"
        "lieu au droit proportionnel. Si\n"
        "toutefois le Trésor Public est\n"
        "condamné, il est dispensé du\n"
        "paiement des droits ;\n"
        "c) les jugements et arrêts rendus sur incidents en cours\n"
        "d’instance et sur les exceptions prévues au titre du Code\n"
        "de procédure civile ;\n"
        "2) Sont enregistrés au droit fixe de vingt\n"
        "mille (20 000) francs CFA, les jugements des tribunaux criminels, les\n"
        "arrêts des Cours de justice contenant\n"
        "les dispositions qui ne peuvent donner\n"
        "lieu au droit proportionnel, ou donnent\n"
        "lieu à moins de vingt mille (20 000)\n"
        "francs CFA de droit proportionnel.\n"
        "3) Sont enregistrés au droit fixe de vingt\n"
        "mille (20 000) francs CFA, les jugements de première instance prononçant un divorce.\n"
        "4) Sont enregistrés au droit fixe de\n"
        "trente-cinq mille (35 000) francs CFA,\n"
        "les arrêts des cours d’appel prononçant un divorce.\n"
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

print(f"\n{nb_corriges}/3 articles corrigés (Lot 4).")
