#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_804_805.py — A LANCER UNE SEULE FOIS depuis le Shell Render.

Corrige la contamination croisee entre les articles 804 (systeme electronique
certifie de facturation) et 805 (attestation de regularite fiscale) : la fin
de l'article 804 (points 5 a 8, sur la certification des logiciels) avait ete
melangee a tort dans le texte de l'article 805.

Usage :
    python corriger_804_805.py
"""
import json

CHEMIN_FICHIER = "cgi2026_articles_corrige.json"

with open(CHEMIN_FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

corrections = {
    "804": (
        "Art. 804.- 1) La facture certifiée est une\n"
        "facture émise via un système électronique certifié de facturation par la\n"
        "Direction Générale des Impôts. Le Directeur Général des Impôts définit par\n"
        "note circulaire, la notion de document\n"
        "tenant lieu de facture certifiée et y précise selon le cas, les mentions obligatoires minimales qu’il doit comporter.\n"
        "2) Un système électronique certifié de\n"
        "facturation est une unité de facturation\n"
        "ou un système de facturation d’entreprise homologué par la Direction Générale des Impôts relié à un module de\n"
        "contrôle de facturation.\n"
        "3) L’unité de facturation et le module\n"
        "de contrôle de facturation sont soumis\n"
        "à une procédure de certification de la\n"
        "Direction Générale des Impôts à l’issue de laquelle un certificat de conformité est délivré.\n"
        "4) Le système électronique certifié de\n"
        "facturation peut être également présenté sous une version dématérialisée.\n"
        "5) Les logiciels de facturation ou systèmes de facturation d’entreprise\n"
        "doivent satisfaire aux spécifications\n"
        "techniques émises par la Direction\n"
        "Générale des Impôts et respecter les\n"
        "critères d’inaltérabilité, de sécurisation, de conservation et d’archivage\n"
        "des données en vue du contrôle de\n"
        "l’Administration fiscale. Ils sont autorisés à être commercialisés quand ils\n"
        "obtiennent l’attestation de conformité\n"
        "délivrée par la Direction Générale des\n"
        "Impôts pour chaque logiciel ou système de facturation d’entreprise.\n"
        "6) L’assujetti qui utilise son propre système de facturation électronique doit\n"
        "satisfaire à la procédure d’auto-déclaration de son système de facturation et\n"
        "obtenir une attestation de conformité.\n"
        "7) Le défaut de présentation de l’attestation prévue aux points 3, 5 et 6 du présent article est sanctionné par l’amende\n"
        "prévue à l’article 828 du présent Code.\n"
        "8) En tant que de besoin, les modalités d’application des dispositions du\n"
        "présent article sont précisées par voie\n"
        "réglementaire.\n"
    ),
    "805": (
        "Art. 805.- 1) Les contribuables ou leurs\n"
        "représentants dûment mandatés sont\n"
        "autorisés à se faire délivrer par l’Administration fiscale une attestation de\n"
        "régularité fiscale, à la condition qu’elle\n"
        "soit relative à leur propre situation fiscale.\n"
        "2) L’attestation de régularité fiscale est\n"
        "un document qui certifie que le contribuable s’est conformé à ses obligations fiscales.\n"
        "3) L’attestation de régularité fiscale\n"
        "est valable pour une durée de quatre-vingt-dix (90) jours en son original ou\n"
        "en sa copie légalisée.\n"
        "4) L’attestation de régularité fiscale est\n"
        "obligatoire pour les commerçants, importateurs, industriels, producteurs,\n"
        "entrepreneurs de travaux publics et\n"
        "bâtiments, prestataires de services,\n"
        "pour tout dossier :\n"
        "a) d’agrément ;\n"
        "b) de soumission à un marché public ;\n"
        "c) d’attestation d’exonération fiscale ;\n"
        "d) de concours bancaire ;\n"
        "e) de commandes publiques ;\n"
        "f) de dispense de retenue à la\n"
        "source de la taxe sur la valeur\n"
        "ajoutée ;\n"
        "g) de remboursement de crédit de\n"
        "taxe sur la valeur ajoutée ;\n"
        "h) de remboursement d’impôt\n"
        "et taxes indûment perçus par\n"
        "l’État ;\n"
        "i) d’octroi, de renouvellement,\n"
        "de transfert de titres miniers\n"
        "et pétroliers, ainsi que les autorisations diverses délivrées\n"
        "par les services du Ministère\n"
        "chargé des mines, de l’Energie et du Ministère chargé du\n"
        "pétrole ;\n"
        "j) d’octroi d’agrément ou d’autorisation délivré par les services du Ministère chargé du\n"
        "Commerce et de l’Industrie,\n"
        "du Ministère chargé des finances ou toute autorité gouvernementale habilitée.\n"
        "5) L’attestation de régularité fiscale est\n"
        "également obligatoire pour :\n"
        "a) les personnes physiques ou\n"
        "morales, se livrant aux opérations d’exportation, de réexportation ou de transit ;\n"
        "b) les exportateurs de bétail pour\n"
        "leurs formalités en douane ;\n"
        "c) les transitaires, les commissionnaires et autres déclarants en douane réalisant des\n"
        "opérations pour le compte des\n"
        "tiers, pour leurs opérations en\n"
        "douanes ;\n"
        "d) tout candidat à un mandat\n"
        "électif ;\n"
        "e) les Organisations Non Gouvernementales et Associations de\n"
        "Développement à l’occasion\n"
        "des demandes d’exonération\n"
        "fiscale ;\n"
        "f) de toute personne ayant son\n"
        "domicile fiscal en République\n"
        "du Niger mais quittant définitivement ce pays.\n"
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

print(f"\n{nb_corriges}/2 articles corrigés et sauvegardés dans {CHEMIN_FICHIER}.")
print("N'oublie pas d'effacer et régénérer les embeddings de ces 2 articles ensuite.")
