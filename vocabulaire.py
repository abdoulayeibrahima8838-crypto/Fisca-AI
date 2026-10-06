# -*- coding: utf-8 -*-
"""
vocabulaire.py — Dictionnaire de synonymes et de vocabulaire naturel pour
Fisca AI (Phase 4 du plan RAG).

Objectif : quand une question utilise un terme familier, une abréviation ou
un mot du quotidien ("IS", "facture électronique", "travail au noir"), le
moteur de recherche doit aussi chercher avec l'équivalent officiel du CGI
("impôt sur les sociétés", "système électronique certifié de facturation",
"activité non déclarée") — sans quoi la recherche vectorielle et par
mots-clés peut manquer le bon article, faute de vocabulaire commun.

Ce fichier est volontairement separe de rag.py : l'enrichir (ajouter des
synonymes) ne demande jamais de toucher au code de recherche lui-meme.
"""

import os
import re
import unicodedata


# Chaque entree : terme central -> liste de termes equivalents ou familiers
# qui doivent tous elargir la recherche vers le meme terme central.
SYNONYMES = {
    # --- Sigles d'impots ---
    "impôt sur les sociétés": ["is", "impot societes"],
    "impôt sur les bénéfices d'affaires des personnes physiques": ["ibapp"],
    "impôt sur les traitements et salaires": ["its"],
    "impôt sur les revenus des capitaux mobiliers": [
        "irvm", "ircm", "impôt sur les revenus des valeurs mobilières",
        "impôt sur les revenus des capitaux mobilières",
    ],
    "taxe sur la valeur ajoutée": ["tva"],
    "impôt minimum forfaitaire": ["imf", "if", "impôt forfaitaire"],
    "impôt sur les revenus locatifs": ["irl"],
    "taxe d'apprentissage": ["tap"],
    "taxe sur certains frais généraux des entreprises": ["tcfge"],
    "taxe immobilière": ["ti"],
    "droits d'accises": ["da"],
    "taxe sur les activités financières": ["tafi"],
    "taxe unique sur les assurances": ["tua"],
    "droits de timbre": ["dt"],
    "droits d'enregistrement": ["de"],

    # --- Facturation / SECeF ---
    "système électronique certifié de facturation": [
        "secef", "facture électronique", "facture certifiée",
        "machine de facturation", "logiciel de facturation certifié",
    ],
    "module de contrôle de facturation": ["mcf"],
    "unité de facturation": ["uf"],

    # --- Administration / procédures ---
    "numéro d'identification fiscale": ["nif"],
    "régime réel normal d'imposition": ["nif r", "nif-r"],
    "régime réel simplifié d'imposition": ["nif s", "nif-s"],
    "régime du forfait": ["nif p", "nif-p", "régime de l'impôt forfaitaire", "régime forfaitaire"],
    "régimes particuliers d'imposition": ["nif a", "nif-a", "nif c", "nif-c"],
    "direction générale des impôts": ["dgi"],
    "avis de mise en recouvrement": ["amr"],
    "attestation de régularité fiscale": ["arf", "quitus fiscal", "certificat de régularité"],
    "contrôle sur pièces": ["csp"],
    "vérification de comptabilité": ["vg"],

    # --- Informel / non déclaré ---
    "activité non déclarée": [
        "travail au noir", "commerce non déclaré", "travail informel",
        "activité informelle", "commerce informel", "secteur informel",
    ],

    # --- Concepts métier du quotidien (le vocabulaire du contribuable,
    # pas celui du texte de loi) ---
    "facture": ["facturation", "reçu", "note"],
    "salaire": ["paie", "rémunération", "traitement"],
    "loyer": ["location", "bail"],
    "marché public": ["appel d'offres", "commande publique"],
    "importation": ["import", "marchandise importée"],
    "véhicule": ["voiture", "camion", "engin"],
    "immeuble": ["bâtiment", "maison", "propriété"],
    "prestation de services": ["service rendu", "prestation"],
    "espèces": ["cash", "argent liquide", "numéraire"],
    "entreprise nouvellement créée": ["nouvelle entreprise", "startup", "création d'entreprise"],
    "commerçant": ["vendeur", "opérateur économique"],

    # --- Sanctions / contrôle, vocabulaire courant ---
    "amende": ["pénalité", "sanction financière"],
    "redressement fiscal": ["contrôle fiscal", "vérification fiscale"],
}

# Sigles trop courts pour etre reconnus sans risque en minuscules (ex. "de"
# est aussi le mot francais le plus courant, "is"/"ti"/"da"/"dt"/"if"/"vg"
# etc. pourraient egalement apparaitre par hasard dans une phrase normale).
# Pour ces synonymes-la (5 caracteres ou moins, sans espace), on n'elargit
# la question QUE s'ils apparaissent ECRITS EN MAJUSCULES dans le texte
# original - un contribuable qui tape "DE" ou "TVA" le fait presque
# toujours en majuscules, jamais un "de" ou "tva" perdu au milieu d'une
# phrase en minuscules.
SEUIL_LONGUEUR_SIGLE_RISQUE = 5

# Exceptions : termes courts mais qui ne sont jamais des mots francais
# ordinaires (donc aucun risque de collision meme en minuscules) et qui,
# de plus, ne s'ecrivent pas conventionnellement tout en majuscules
# (ex. "SECeF" avec un e minuscule). Ceux-la restent reconnus quelle que
# soit la casse utilisee.
TERMES_SANS_RISQUE_MALGRE_LONGUEUR = {"secef"}



# =============================================================================
# VOCABULAIRE ENRICHI (octobre 2026)
# =============================================================================
# Active par la variable d'environnement VOCABULAIRE_ENRICHI=1 (Render).
# Desactive par defaut : tant qu'elle n'est pas a "1", le comportement est
# EXACTEMENT celui d'avant (memes synonymes, meme detection).
#
# Pour le tester sans toucher a l'application en ligne (Shell Render) :
#   VOCABULAIRE_ENRICHI=1 python fisca_ai_test_engine.py --refaire-tout
#
# Contenu : chaque terme central est un terme du CGI 2026 ; les synonymes
# sont le vocabulaire des contribuables (anciens noms d'impots encore en
# usage au Niger comme « patente », « impot synthetique », « contribution
# fonciere » ; sigles UEMOA courants ; expressions du quotidien ; un terme
# haoussa). Les synonymes ne sont JAMAIS montres a l'utilisateur : ils
# elargissent seulement la recherche.
#
# En mode enrichi, la detection devient aussi :
#   - insensible aux accents (« impot », « benefice », « societes ») ;
#   - tolerante au pluriel simple (« loyers », « acomptes ») ;
# et l'erreur historique « impot forfaitaire » -> impot minimum forfaitaire
# est corrigee (l'impot forfaitaire des articles 121 et 122 est celui du
# regime du forfait, distinct de l'IMF).

VOCABULAIRE_ENRICHI = os.environ.get("VOCABULAIRE_ENRICHI", "0") == "1"

SYNONYMES_ENRICHIS = {
    # --- Anciens noms et appellations courantes des impots ---
    "taxe professionnelle": [
        "patente", "patentes", "impôt de patente", "droit de patente",
        "contribution des patentes",
    ],
    "régime du forfait": [
        "impôt synthétique", "patente synthétique", "impôt forfaitaire",
        "contribuable au forfait",
    ],
    "taxe immobilière": [
        "contribution foncière", "impôt foncier", "taxe foncière",
        "foncier bâti", "impôt sur les immeubles",
    ],
    "impôt sur les bénéfices d'affaires des personnes physiques": [
        "bic", "bnc", "bénéfices industriels et commerciaux",
        "bénéfices non commerciaux", "impôt sur le bénéfice",
        "impôt sur les bénéfices", "isb", "impôt de l'entreprise individuelle",
    ],
    "impôt sur les traitements et salaires": [
        "iuts", "impôt sur le salaire", "impôt sur salaire",
        "impôt sur les salaires", "retenue sur salaire", "impôt sur la paie",
    ],
    "impôt sur les revenus des capitaux mobiliers": [
        "impôt sur les dividendes", "retenue sur dividendes", "dividende",
        "dividendes", "bénéfices distribués",
    ],
    "impôt sur les revenus locatifs": [
        "impôt sur les loyers", "impôt sur le loyer", "impôt locatif",
        "taxe sur les loyers", "retenue sur loyer", "retenue sur les loyers",
        "revenus de location",
    ],
    "taxe sur la valeur ajoutée": ["taxe à la valeur ajoutée"],
    "taxe d'habitation": [
        "taxe sur l'électricité", "taxe sur la facture d'électricité",
        "taxe nigelec", "taxe sur le compteur",
    ],
    "vignette automobile": [
        "vignette auto", "taxe sur les véhicules", "taxe de roulage",
        "taxe sur la voiture",
    ],
    "droits d'accises": [
        "accise", "accises", "taxe sur le tabac", "taxe sur les cigarettes",
        "taxe sur les boissons", "taxe sur l'alcool",
    ],
    "taxe intérieure sur les produits pétroliers": [
        "tipp", "taxe sur le carburant", "taxe sur l'essence",
        "taxe sur le gasoil", "taxe sur le gas-oil",
    ],
    "taxe sur les activités financières": [
        "taxe sur les frais bancaires", "taxe sur les agios",
        "taxe sur les commissions bancaires",
    ],
    "taxe unique sur les assurances": [
        "taxe sur les assurances", "taxe sur les primes d'assurance",
    ],
    "taxe à l'embarquement sur le transport aérien": [
        "taxe sur les billets d'avion", "taxe aéroportuaire",
        "taxe d'embarquement",
    ],
    "taxe de protection de l'environnement": [
        "taxe sur les sachets", "taxe sur les plastiques", "écotaxe",
        "taxe verte", "taxe sur la pollution",
    ],
    "taxe sur les loteries et jeux de hasard": [
        "taxe sur les paris", "taxe sur les jeux", "pari mutuel",
        "loterie nationale",
    ],
    "taxe sur l'utilisation des réseaux de télécommunications": [
        "taxe télécom", "taxe sur les appels", "taxe sur la téléphonie",
        "taxe sur le crédit téléphonique",
    ],
    "impôt sur les plus-values immobilières": [
        "plus-value immobilière", "impôt sur la vente de maison",
        "impôt sur la vente d'immeuble", "impôt sur la vente de terrain",
    ],
    "taxe d'apprentissage": ["taxe sur la formation professionnelle"],
    "impôts, droits et taxes": ["haraji", "kudin haraji"],

    # --- Identification et obligations ---
    "déclaration d'existence": [
        "inscription aux impôts", "s'inscrire aux impôts",
        "s'enregistrer aux impôts", "immatriculation fiscale",
        "obtenir un nif", "créer un nif", "ouvrir un dossier fiscal",
    ],
    "déclaration statistique et fiscale": [
        "dsf", "liasse fiscale", "états financiers annuels",
        "bilan annuel", "déclaration de résultat", "déclaration des résultats",
    ],
    "télé-déclaration": [
        "déclaration en ligne", "déclarer en ligne", "télédéclaration",
        "e-déclaration",
    ],
    "télépaiement": [
        "paiement en ligne", "payer en ligne", "paiement électronique",
        "mobile money", "paiement par téléphone",
    ],
    "régime réel simplifié d'imposition": ["réel simplifié", "rsi"],
    "régime réel normal d'imposition": ["réel normal", "rni"],
    "centre de gestion agréé": ["cga"],
    "rescrit fiscal": [
        "demande de position", "prise de position de l'administration",
        "avis préalable de l'administration",
    ],

    # --- Controle, sanctions, recouvrement ---
    "vérification de comptabilité": [
        "vgc", "vérification générale de comptabilité",
        "vérification générale", "contrôle sur place",
    ],
    "procédure de rectification contradictoire": [
        "redressement", "redressements", "notification de redressement",
        "lettre de redressement", "rappel d'impôt",
    ],
    "procédure de taxation d'office": [
        "imposition d'office", "évaluation d'office", "taxé d'office",
        "taxée d'office",
    ],
    "manœuvres frauduleuses": [
        "fraude", "fraude fiscale", "fausse déclaration", "fausses factures",
        "fausse facture", "frauder",
    ],
    "avis à tiers détenteur": [
        "atd", "saisie sur compte", "saisie du compte bancaire",
        "saisie sur salaire", "blocage du compte",
    ],
    "avis de mise en recouvrement": ["avis d'imposition"],
    "mise en demeure": ["lettre de relance", "dernier avertissement"],
    "fermeture provisoire pour non-paiement d'impôts": [
        "fermeture de boutique", "fermeture du magasin",
        "fermeture de l'établissement", "fermeture du commerce",
        "fermer ma boutique", "fermer mon magasin", "fermer mon commerce",
        "mettre les scellés", "pose de scellés",
    ],
    "réclamation": [
        "contester un impôt", "contester l'impôt", "contestation de l'impôt",
        "contester une imposition", "contentieux fiscal",
    ],
    "sursis de paiement": [
        "suspendre le paiement", "suspension du paiement",
    ],
    "demandes en remise ou modération d'impôt": [
        "remise gracieuse", "annulation des pénalités",
        "réduction des pénalités", "effacement de la dette fiscale",
    ],
    "plan de règlement": [
        "échéancier", "paiement échelonné", "paiement en plusieurs fois",
        "étalement de la dette", "moratoire",
    ],
    "délais de reprise": [
        "prescription fiscale", "années prescrites", "années non prescrites",
    ],
    "pénalités de recouvrement": [
        "pénalité de retard", "pénalités de retard", "majoration de retard",
        "amende de retard",
    ],

    # --- Enregistrement, timbre, foncier ---
    "droits d'enregistrement": [
        "frais d'enregistrement", "frais de mutation", "droits de mutation",
        "frais d'acte",
    ],
    "mutations à titre onéreux d'immeubles": [
        "vente de maison", "vente de terrain", "vente de parcelle",
        "achat de maison", "achat de terrain", "achat de parcelle",
        "acheter une maison", "acheter un terrain", "acheter une parcelle",
        "vendre ma maison", "vendre mon terrain", "vendre ma parcelle",
    ],
    "mutations par décès": [
        "héritage", "hériter", "droits de succession", "droits d'héritage",
    ],
    "mutations à titre gratuit": [
        "donation entre vifs", "donner un bien", "donner une maison",
        "donner un terrain",
    ],
    "titre foncier": [
        "papier de la parcelle", "titre de propriété", "acte de propriété",
        "permis urbain d'habiter",
    ],
    "cession de fonds de commerce": [
        "vente de boutique", "vendre mon commerce", "vente du commerce",
        "vendre ma boutique", "reprise de commerce",
    ],
    "droits de timbre": [
        "timbres fiscaux", "timbre fiscal", "papier timbré", "timbrer",
    ],
    "contrat de bail": ["contrat de location"],

    # --- Benefices, charges, TVA ---
    "charges déductibles": [
        "dépenses déductibles", "frais déductibles", "charges admises",
        "déduire une dépense", "déduire une charge",
    ],
    "déficit": [
        "report déficitaire", "report de perte", "report des pertes",
        "reporter les pertes", "reporter mes pertes", "reporter une perte",
        "exercice déficitaire",
    ],
    "acompte provisionnel": [
        "acompte", "acomptes", "avance d'impôt", "paiement anticipé",
    ],
    "retenue à la source": ["prélèvement à la source"],
    "prix de transfert": [
        "transfert de bénéfices", "facturation intragroupe",
        "transactions intragroupe",
    ],
    "non-résident": [
        "prestataire étranger", "société étrangère", "entreprise étrangère",
        "non résident",
    ],
    "frais de siège et d'assistance technique": [
        "management fees", "frais de gestion du groupe",
    ],
    "régime des investissements": [
        "code des investissements", "entreprise agréée",
        "agrément au code des investissements",
    ],
    "remboursement des crédits de taxe sur la valeur ajoutée": [
        "crédit de tva", "remboursement de tva", "tva à rembourser",
        "remboursement de la tva",
    ],
    "droit à déduction": [
        "récupérer la tva", "récupération de la tva", "tva récupérable",
        "déduire la tva", "tva déductible",
    ],
    "retenue à la source de la taxe sur la valeur ajoutée": [
        "tva retenue", "retenue de tva", "retenue de la tva",
    ],
    "exonération": ["exemption", "exempté", "exemptée", "dispense d'impôt"],
}


def _plier(texte):
    """Minuscules sans accents, apostrophes unifiees (mode enrichi)."""
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    return t.replace("’", "'")


def _synonymes_de_base():
    """Synonymes historiques, detectes EXACTEMENT comme avant. En mode
    enrichi, seule correction : « impot forfaitaire » ne renvoie plus vers
    l'impot minimum forfaitaire (il releve du regime du forfait)."""
    if not VOCABULAIRE_ENRICHI:
        return SYNONYMES
    base = {k: list(v) for k, v in SYNONYMES.items()}
    base["impôt minimum forfaitaire"] = [
        s for s in base.get("impôt minimum forfaitaire", []) if s != "impôt forfaitaire"
    ]
    return base


def construire_index_enrichi():
    """terme_familier (sans accents) -> (terme_central, sensible_casse), pour
    les SEULS synonymes ajoutes en octobre 2026. Vide si le mode enrichi est
    desactive."""
    index = {}
    if not VOCABULAIRE_ENRICHI:
        return index
    for central, synonymes in SYNONYMES_ENRICHIS.items():
        for s in synonymes:
            sigle = (len(s) <= SEUIL_LONGUEUR_SIGLE_RISQUE and " " not in s
                     and s.lower() not in TERMES_SANS_RISQUE_MALGRE_LONGUEUR)
            index[s] = (central, sigle)
    return index


def construire_index_inverse():
    """Construit un dictionnaire terme_familier -> (terme_central, sensible_casse),
    pour une recherche rapide dans les deux sens. Un synonyme est marque
    'sensible a la casse' s'il est court (<= 5 caracteres) ET sans espace -
    typiquement un sigle (IS, TVA, DE, ARF...) qui pourrait sinon collisionner
    avec un mot francais ordinaire une fois mis en minuscules."""
    index = {}
    for terme_central, synonymes in _synonymes_de_base().items():
        index[terme_central.lower()] = (terme_central, False)
        for s in synonymes:
            est_sigle_risque = (
                len(s) <= SEUIL_LONGUEUR_SIGLE_RISQUE
                and " " not in s
                and s.lower() not in TERMES_SANS_RISQUE_MALGRE_LONGUEUR
            )
            index[s.lower()] = (terme_central, est_sigle_risque)
    return index


_INDEX_INVERSE = construire_index_inverse()
_INDEX_ENRICHI = construire_index_enrichi()


def elargir_question(question):
    """Detecte les termes familiers/abreges presents dans la question et
    retourne une version elargie qui ajoute leurs equivalents officiels du
    CGI - utilisee pour la recherche (vectorielle + mots-cles), jamais
    montree telle quelle a l'utilisateur.

    Les sigles courts et risques de collision (IS, DE, TI, ARF...) ne sont
    reconnus que s'ils apparaissent ECRITS EN MAJUSCULES dans la question
    originale - un contribuable qui parle de la "TVA" l'ecrit en majuscules,
    jamais un "tva" perdu au milieu d'une phrase en minuscules.

    Exemple :
        elargir_question("C'est quoi le taux de l'IS ?")
        -> "C'est quoi le taux de l'IS ? impôt sur les sociétés"
        elargir_question("je dois payer de la tva")
        -> "je dois payer de la tva" (le mot commun "de" n'est jamais elargi)
    """
    question_lower = question.lower()
    question_pliee = _plier(question) if VOCABULAIRE_ENRICHI else question_lower
    termes_trouves = set()

    for terme_familier, (terme_central, sensible_casse) in _INDEX_INVERSE.items():
        if sensible_casse:
            # Recherche la version MAJUSCULE du sigle dans le texte ORIGINAL
            # (pas en minuscules, pas de flag IGNORECASE) : un contribuable
            # qui parle de "DE" ou "ARF" l'ecrit en majuscules ; le mot
            # ordinaire "de" en minuscules ne doit jamais matcher.
            motif = r"\b" + re.escape(terme_familier.upper()) + r"\b"
            if re.search(motif, question):
                termes_trouves.add(terme_central)
        else:
            motif = r"\b" + re.escape(terme_familier) + r"\b"
            if re.search(motif, question_lower):
                termes_trouves.add(terme_central)

    # Correction importante : "NIF R/S/P/A/C" declenchent TOUJOURS aussi le
    # sigle generique "NIF" seul (puisque "NIF" apparait litteralement dans
    # le texte de "NIF P"), ajoutant a tort "numero d'identification
    # fiscale" en plus du terme specifique. Resultat observe en production :
    # l'article 775 (qui DEFINIT le NIF generique) dominait systematiquement
    # la recherche, empechant l'article specifique au bon regime (ex. 120
    # pour le regime du forfait) de remonter. Le terme specifique, plus
    # informatif, doit toujours l'emporter seul.
    TERMES_REGIMES_NIF_SPECIFIQUES = {
        "régime réel normal d'imposition", "régime réel simplifié d'imposition",
        "régime du forfait", "régimes particuliers d'imposition",
    }
    if termes_trouves & TERMES_REGIMES_NIF_SPECIFIQUES:
        termes_trouves.discard("numéro d'identification fiscale")

    # Mode enrichi : synonymes ajoutes en octobre 2026, detectes sans tenir
    # compte des accents et avec pluriel simple (s/x) tolere. Un terme
    # officiel deja ecrit dans la question n'est pas rajoute.
    for terme_familier, (terme_central, sensible_casse) in _INDEX_ENRICHI.items():
        if sensible_casse:
            trouve = re.search(r"\b" + re.escape(terme_familier.upper()) + r"\b", question)
        else:
            trouve = re.search(r"\b" + re.escape(_plier(terme_familier)) + r"[sx]?\b", question_pliee)
        if trouve and terme_central not in termes_trouves and _plier(terme_central) not in question_pliee:
            termes_trouves.add(terme_central)

    if not termes_trouves:
        return question

    return question + " " + " ".join(sorted(termes_trouves))


