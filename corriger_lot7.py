#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_lot7.py — A LANCER UNE SEULE FOIS depuis le Shell Render.

Lot 7 : articles 705, 718, 754, 785.

Usage :
    python corriger_lot7.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_corrige.json"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

corrections = {
    "705": (
        "Art. 705.- 1) L’avis de mise en recouvrement est nominatif et comporte, à\n"
        "peine de nullité :\n"
        "a) l’identité complète et l’adresse\n"
        "du contribuable ;\n"
        "b) les indications nécessaires à\n"
        "la connaissance des impôts,\n"
        "droits, taxes et redevances ou\n"
        "autres sommes faisant l’objet\n"
        "du recouvrement ;\n"
        "c) la période à laquelle se rapporte\n"
        "l’imposition ;\n"
        "d) l’année au cours de laquelle\n"
        "l’imposition est établie ;\n"
        "e) le numéro d’ordre de l’avis de\n"
        "mise en recouvrement ;\n"
        "f) le montant des droits et pénalités ;\n"
        "g) le Numéro d’Identification Fiscale pour les contribuables\n"
        "immatriculés ;\n"
        "h) la date de mise en recouvrement ;\n"
        "i) la date d’exigibilité ;\n"
        "j) la date de majoration ;\n"
        "k) les signatures des personnes\n"
        "habilitées.\n"
        "2) L’avis de mise en recouvrement est\n"
        "notifié par le Receveur des Impôts au\n"
        "contribuable, à ses ayants-droits ou à\n"
        "son représentant. En cas de refus de\n"
        "décharge, l’agent de poursuite dresse\n"
        "un procès-verbal de constat de refus.\n"
        "Nonobstant ce refus, la procédure de\n"
        "recouvrement suit son cours normal.\n"
    ),
    "718": (
        "Art. 718.- 1) Tout acte de poursuites\n"
        "est établi en original et en autant de\n"
        "copies qu’il y a de destinataires.\n"
        "2) Les notifications sont faites à la personne du contribuable qui en accuse\n"
        "réception. Dans le cas où la notification à personne s’avère impossible,\n"
        "l’acte est remis sous pli fermé, au domicile du contribuable, entre les mains\n"
        "des parents, serviteurs, employés ou\n"
        "de toute autre personne habitant à\n"
        "même demeure.\n"
        "3) La personne qui reçoit l’acte en accuse réception. Si le contribuable ou\n"
        "la personne rencontrée refuse de recevoir l’acte, mention en est faite sur\n"
        "l’original et l’agent de poursuites délaisse néanmoins l’acte sous pli fermé\n"
        "en faisant mention sur l’original et la\n"
        "copie du refus à lui opposé.\n"
        "4) Si la remise de l’acte n’a pu être effectuée parce que le redevable n’a pas\n"
        "été rencontré ni personne pour lui à\n"
        "son domicile ou sa résidence, l’acte\n"
        "est considéré comme ayant été valablement notifié le dixième jour qui\n"
        "suit la date de son affichage au dernier\n"
        "domicile figurant sur l’avis de mise en\n"
        "recouvrement du redevable. Copie de\n"
        "l’acte est déposée au secrétariat de la\n"
        "mairie du lieu de situation du dernier\n"
        "domicile connu.\n"
        "5) La voie postale peut être utilisée\n"
        "pour la notification des actes de poursuites lorsque le redevable est domicilié en dehors des limites territoriales\n"
        "du poste comptable. L’acte de poursuites est placé sous enveloppe fermée portant au recto le numéro d’ordre\n"
        "de l’acte à notifier ainsi que l’adresse\n"
        "du redevable et au verso le timbre du\n"
        "comptable qui exerce les poursuites.\n"
        "Le cachet de la poste fait foi.\n"
    ),
    "754": (
        "Art. 754.- Hormis le cas où il fait l’objet\n"
        "d’une convention d’assistance administrative réciproque, le recouvrement\n"
        "à l’étranger des créances fiscales s’effectue par voie de contrainte extérieure,\n"
        "par le biais des chancelleries auprès\n"
        "des ambassades du Niger à l’étranger.\n"
    ),
    "785": (
        "Art. 785.- 1) Une déclaration annuelle\n"
        "doit être souscrite, auprès de l’Administration fiscale dont elle relève, par\n"
        "toute personne qui paye à des tiers ne\n"
        "faisant pas partie de son personnel salarié, des sommes qui entrent dans les\n"
        "catégories suivantes :\n"
        "a) commissions, courtages, ristournes commerciales ou\n"
        "autres, honoraires occasionnels ou non, gratifications et\n"
        "autres rémunérations assimilées ;\n"
        "b) droits d’auteur ou d’inventeur.\n"
        "2) Les sommes versées aux tiers sont à\n"
        "déclarer si elles répondent aux conditions suivantes :\n"
        "a) ne pas représenter une diminution de prix consentie par\n"
        "les entreprises à leurs clients\n"
        "en fonction du chiffre d’affaires\n"
        "réalisé avec ces derniers ;\n"
        "b) ne pas revêtir le caractère\n"
        "d’acte de commerce ;\n"
        "c) dépasser cinquante mille\n"
        "(50 000) francs CFA toutes\n"
        "taxes comprises par an pour\n"
        "un même bénéficiaire.\n"
        "3) Pour satisfaire à l’obligation de déclaration, la partie versante doit souscrire, selon les modèles conçus à cet\n"
        "effet par l’Administration fiscale :\n"
        "a) une déclaration récapitulative;\n"
        "b) un bulletin individuel par bénéficiaire.\n"
        "4) Ces déclarations doivent être souscrites, auprès du service des impôts\n"
        "territorialement compétent, avant le\n"
        "1er février de chaque année, pour les\n"
        "sommes versées au cours de l’année\n"
        "précédente. Lorsqu’une entreprise\n"
        "dispose de plusieurs établissements\n"
        "distincts, une seule déclaration regroupant l’ensemble des tiers bénéficiaires doit être souscrite.\n"
        "5) Tout manquement à l’obligation de\n"
        "déclaration visée au présent article est\n"
        "sanctionné dans les conditions prévues à l’article 810 du présent Code.\n"
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

print(f"\n{nb_corriges}/4 articles corrigés (Lot 7).")
