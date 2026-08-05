# -*- coding: utf-8 -*-
"""
calendrier_fiscal_data.py
Données du calendrier fiscal nigérien, sourcées du Code Général des Impôts 2026.

Structure pensée pour s'intégrer au même modèle que cache_data.py de Fisca AI :
chaque échéance référence son article exact du CGI 2026, pour garder la même
rigueur de citation que le reste de l'application.

Deux catégories :
  1. ECHEANCES_MENSUELLES  -> obligations qui reviennent chaque mois (jour fixe)
  2. ECHEANCES_PONCTUELLES -> obligations à date fixe dans l'année (un seul mois)
  3. DELAIS_EVENEMENTS     -> obligations déclenchées par un événement
                              (pas une date de calendrier, mais un nombre de
                              jours/mois à partir d'un fait générateur)

MISE À JOUR : toute modification du CGI (loi de finances annuelle) doit se
répercuter ici. Prévoir une revue de ce fichier chaque décembre/janvier.
"""

# ---------------------------------------------------------------------------
# 1) ÉCHÉANCES MENSUELLES RÉCURRENTES
#    (jour_du_mois : jour limite dans le mois SUIVANT celui concerné, sauf
#     mention contraire explicite dans le libellé)
# ---------------------------------------------------------------------------
ECHEANCES_MENSUELLES = [
    {
        "id": "tva-normal",
        "jour_limite": 15,
        "libelle": "TVA — Régime réel normal (déclaration du mois précédent)",
        "impot": "Taxe sur la Valeur Ajoutée",
        "article": "Art. 354.1",
        "public": "Assujettis au régime réel normal (Art. 118)",
    },
    {
        "id": "its-declaration",
        "jour_limite": 15,
        "libelle": "Impôt sur les Traitements et Salaires — déclaration mensuelle",
        "impot": "IUTS",
        "article": "Art. 152",
        "public": "Tout employeur, même sans salarié payé dans le mois (sauf régime du forfait)",
    },
    {
        "id": "its-versement",
        "jour_limite": 15,
        "libelle": "Impôt sur les Traitements et Salaires — versement de la retenue",
        "impot": "IUTS",
        "article": "Art. 153",
        "public": "Tout employeur domicilié ou établi au Niger",
    },
    {
        "id": "taf",
        "jour_limite": 15,
        "libelle": "Taxe sur les Activités Financières",
        "impot": "TAF",
        "article": "Art. 393",
        "public": "Établissements financiers et assimilés",
    },
    {
        "id": "taxe-numeraire",
        "jour_limite": 15,
        "libelle": "Taxe sur les paiements en numéraire",
        "impot": "Taxe sur les paiements en numéraire",
        "article": "Art. 394 sexiesdecies",
        "public": "Entreprises au régime réel, pour paiements > 100 000 FCFA",
    },
    {
        "id": "retenue-source-prestataires",
        "jour_limite": 15,
        "libelle": "Retenue à la source de 20% (prestataires visés à l'Art. 108)",
        "impot": "Retenue de conformité fiscale",
        "article": "Art. 107",
        "public": "Débiteurs effectuant des paiements à des prestataires non en règle",
    },
    {
        "id": "irl-retenue",
        "jour_limite": 15,
        "libelle": "Impôt sur les Revenus Locatifs — reversement de la retenue",
        "impot": "IRL",
        "article": "Art. 171",
        "public": "Locataires soumis au régime réel, État, collectivités, ONG, projets",
    },
    {
        "id": "taxe-habitation-facturee",
        "jour_limite": 15,
        "libelle": "Taxe d'Habitation — reversement (redevables facturés via électricité)",
        "impot": "Taxe d'Habitation",
        "article": "Art. 273",
        "public": "Redevables dont la taxe est prélevée sur la facture d'électricité",
    },
]

# ---------------------------------------------------------------------------
# 2) ÉCHÉANCES PONCTUELLES (une seule fois par an, mois précis)
#    mois : 1=janvier ... 12=décembre
# ---------------------------------------------------------------------------
ECHEANCES_PONCTUELLES = [
    {
        "id": "taxe-immobiliere-declaration",
        "mois": 1, "jour": 31,
        "libelle": "Déclaration de la taxe immobilière (foncière)",
        "impot": "Taxe immobilière",
        "article": "Art. 261",
        "public": "Contribuables au régime réel",
    },
    {
        "id": "taxe-habitation-declaration",
        "mois": 1, "jour": 31,
        "libelle": "Déclaration de la Taxe d'Habitation (hors facturation électricité)",
        "impot": "Taxe d'Habitation",
        "article": "Art. 271",
        "public": "Redevables disposant d'un système autonome d'énergie",
    },
    {
        "id": "etat-loyers-bailleurs",
        "mois": 1, "jour": 31,
        "libelle": "État annuel des loyers perçus et retenues pratiquées (bailleurs)",
        "impot": "IRL",
        "article": "Art. 168",
        "public": "Tout redevable de l'impôt sur les revenus locatifs",
    },
    {
        "id": "tva-simplifie-t4",
        "mois": 1, "jour": 15,
        "libelle": "TVA — Régime réel simplifié (déclaration du 4e trimestre précédent)",
        "impot": "TVA",
        "article": "Art. 354.2",
        "public": "Assujettis au régime réel simplifié (Art. 119)",
    },
    {
        "id": "patente-declaration",
        "mois": 2, "jour": 28,
        "libelle": "Déclaration de la Taxe professionnelle (patente)",
        "impot": "Taxe professionnelle",
        "article": "Art. 290",
        "public": "Contribuables au régime réel",
    },
    {
        "id": "patente-1er-versement",
        "mois": 2, "jour": 28,
        "libelle": "Taxe professionnelle — 1er versement (au moins 50%)",
        "impot": "Taxe professionnelle",
        "article": "Art. 291",
        "public": "Contribuables au régime réel",
    },
    {
        "id": "vignette-machines-sous",
        "mois": 3, "jour": 1,
        "libelle": "Vignette sur les machines à sous",
        "impot": "Vignette machines à sous",
        "article": "Art. 317",
        "public": "Exploitants de machines à sous",
    },
    {
        "id": "vignette-vehicules",
        "mois": 4, "jour": 1,
        "libelle": "Vignette véhicules — paiement total de l'exercice",
        "impot": "Vignette",
        "article": "Art. 312",
        "public": "Possesseurs de véhicules à moteur",
    },
    {
        "id": "tva-simplifie-t1",
        "mois": 4, "jour": 15,
        "libelle": "TVA — Régime réel simplifié (déclaration du 1er trimestre)",
        "impot": "TVA",
        "article": "Art. 354.2",
        "public": "Assujettis au régime réel simplifié",
    },
    {
        "id": "tva-prorata-definitif",
        "mois": 4, "jour": 15,
        "libelle": "Déclaration du prorata de déduction TVA définitif (année précédente)",
        "impot": "TVA",
        "article": "Art. 354.2",
        "public": "Redevables ne réalisant pas exclusivement des opérations ouvrant droit à déduction",
    },
    {
        "id": "is-declaration",
        "mois": 4, "jour": 30,
        "libelle": "Déclaration statistique et fiscale (bénéfices imposables)",
        "impot": "Impôt sur les Sociétés / IBA",
        "article": "Art. 68",
        "public": "Sociétés et entreprises soumises à l'IS ou à l'IBA",
    },
    {
        "id": "is-solde",
        "mois": 4, "jour": 30,
        "libelle": "Solde de l'Impôt sur les Sociétés (régularisation de l'exercice précédent)",
        "impot": "Impôt sur les Sociétés",
        "article": "Art. 67 (lié au dépôt de la déclaration, Art. 68)",
        "public": "Sociétés soumises à l'IS",
    },
    {
        "id": "patente-solde",
        "mois": 6, "jour": 30,
        "libelle": "Taxe professionnelle — solde",
        "impot": "Taxe professionnelle",
        "article": "Art. 291",
        "public": "Contribuables au régime réel",
    },
    {
        "id": "taxe-immobiliere-solde",
        "mois": 6, "jour": 30,
        "libelle": "Taxe immobilière — solde",
        "impot": "Taxe immobilière",
        "article": "Art. 262",
        "public": "Contribuables au régime réel",
    },
    {
        "id": "taxe-habitation-solde",
        "mois": 6, "jour": 30,
        "libelle": "Taxe d'Habitation — solde (hors facturation électricité)",
        "impot": "Taxe d'Habitation",
        "article": "Art. 274",
        "public": "Redevables disposant d'un système autonome d'énergie",
    },
    {
        "id": "patente-transport",
        "mois": 6, "jour": 30,
        "libelle": "Taxe professionnelle du secteur des transports terrestres",
        "impot": "Taxe professionnelle (transports)",
        "article": "Art. 293",
        "public": "Entreprises de transport terrestre",
    },
    {
        "id": "is-acompte-1",
        "mois": 7, "jour": 1,
        "libelle": "Impôt sur les Sociétés — 1er acompte provisionnel",
        "impot": "Impôt sur les Sociétés",
        "article": "Art. 67",
        "public": "Sociétés soumises à l'IS (hors 1ère année d'activité)",
    },
    {
        "id": "tva-simplifie-t2",
        "mois": 7, "jour": 15,
        "libelle": "TVA — Régime réel simplifié (déclaration du 2e trimestre)",
        "impot": "TVA",
        "article": "Art. 354.2",
        "public": "Assujettis au régime réel simplifié",
    },
    {
        "id": "is-acompte-2",
        "mois": 9, "jour": 1,
        "libelle": "Impôt sur les Sociétés — 2e acompte provisionnel",
        "impot": "Impôt sur les Sociétés",
        "article": "Art. 67",
        "public": "Sociétés soumises à l'IS",
    },
    {
        "id": "tva-simplifie-t3",
        "mois": 10, "jour": 15,
        "libelle": "TVA — Régime réel simplifié (déclaration du 3e trimestre)",
        "impot": "TVA",
        "article": "Art. 354.2",
        "public": "Assujettis au régime réel simplifié",
    },
    {
        "id": "is-acompte-3",
        "mois": 11, "jour": 1,
        "libelle": "Impôt sur les Sociétés — 3e acompte provisionnel",
        "impot": "Impôt sur les Sociétés",
        "article": "Art. 67",
        "public": "Sociétés soumises à l'IS",
    },
]

# ---------------------------------------------------------------------------
# 3) DÉLAIS LIÉS À UN ÉVÉNEMENT (pas une date calendaire fixe)
# ---------------------------------------------------------------------------
DELAIS_EVENEMENTS = [
    {
        "id": "declaration-existence",
        "evenement": "Début d'activité",
        "delai": "30 jours",
        "libelle": "Déclaration d'existence auprès du service des impôts",
        "article": "Art. 774",
    },
    {
        "id": "declaration-existence-forfait",
        "evenement": "Début d'activité (régime du forfait)",
        "delai": "30 jours",
        "libelle": "Déclaration d'existence",
        "article": "Art. 131",
    },
    {
        "id": "modification-existence",
        "evenement": "Modification des informations déclarées à l'immatriculation",
        "delai": "15 jours",
        "libelle": "Notification de la modification à l'Administration fiscale",
        "article": "Art. 774",
    },
    {
        "id": "cession-cessation",
        "evenement": "Cession ou cessation d'entreprise",
        "delai": "10 jours",
        "libelle": "Aviser le service des impôts et transmettre la déclaration du bénéfice réel",
        "article": "Art. 113",
    },
    {
        "id": "enregistrement-acte-general",
        "evenement": "Signature d'un acte soumis à l'enregistrement",
        "delai": "1 mois",
        "libelle": "Enregistrement de l'acte",
        "article": "Art. 481.1",
    },
    {
        "id": "enregistrement-acte-etranger",
        "evenement": "Acte soumis à l'enregistrement, passé hors du territoire national",
        "delai": "2 mois",
        "libelle": "Enregistrement de l'acte",
        "article": "Art. 481.2.a",
    },
    {
        "id": "enregistrement-testament",
        "evenement": "Décès du testateur (testament déposé/reçu chez notaire)",
        "delai": "3 mois",
        "libelle": "Enregistrement du testament",
        "article": "Art. 481.2.b",
    },
    {
        "id": "mutation-deces-niger",
        "evenement": "Décès (mutation à titre gratuit), décès survenu au Niger",
        "delai": "6 mois",
        "libelle": "Déclaration de succession",
        "article": "Art. 481.2.c",
    },
    {
        "id": "mutation-deces-etranger",
        "evenement": "Décès (mutation à titre gratuit), décès survenu hors du Niger",
        "delai": "1 an",
        "libelle": "Déclaration de succession",
        "article": "Art. 481.2.c",
    },
    {
        "id": "mutation-sans-acte",
        "evenement": "Entrée en possession (mutation à titre onéreux ou bail, à défaut d'acte)",
        "delai": "1 mois",
        "libelle": "Déclaration détaillée et estimative",
        "article": "Art. 482",
    },
]

MOIS_LABELS = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}


def get_calendrier_par_mois():
    """
    Construit le calendrier complet organisé par mois (1-12).
    Chaque mois contient : les échéances mensuelles récurrentes (avec le
    jour_limite du mois en cours) + les échéances ponctuelles propres à ce mois.
    Retourne un dict { numero_mois: {"label": str, "echeances": [...]} }
    """
    calendrier = {m: {"label": MOIS_LABELS[m], "echeances": []} for m in range(1, 13)}

    for e in ECHEANCES_MENSUELLES:
        for m in range(1, 13):
            calendrier[m]["echeances"].append({
                "jour": e["jour_limite"],
                "libelle": e["libelle"],
                "impot": e["impot"],
                "article": e["article"],
                "public": e.get("public", ""),
                "type": "mensuelle",
            })

    for e in ECHEANCES_PONCTUELLES:
        calendrier[e["mois"]]["echeances"].append({
            "jour": e["jour"],
            "libelle": e["libelle"],
            "impot": e["impot"],
            "article": e["article"],
            "public": e.get("public", ""),
            "type": "ponctuelle",
        })

    # Tri de chaque mois par jour croissant
    for m in calendrier:
        calendrier[m]["echeances"].sort(key=lambda x: x["jour"])

    return calendrier
