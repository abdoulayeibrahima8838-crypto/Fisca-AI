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

import re


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
    "régime de l'impôt forfaitaire": ["nif p", "nif-p"],
    "régimes particuliers d'imposition": ["nif a", "nif-a", "nif c", "nif-c"],
    "direction générale des impôts": ["dgi"],
    "avis de mise en recouvrement": ["amr"],
    "attestation de régularité fiscale": ["arf", "quitus fiscal", "certificat de régularité"],
    "contrôle sur pièces": ["csp"],
    "vérification générale de la comptabilité": ["vg"],

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


def construire_index_inverse():
    """Construit un dictionnaire terme_familier -> (terme_central, sensible_casse),
    pour une recherche rapide dans les deux sens. Un synonyme est marque
    'sensible a la casse' s'il est court (<= 5 caracteres) ET sans espace -
    typiquement un sigle (IS, TVA, DE, ARF...) qui pourrait sinon collisionner
    avec un mot francais ordinaire une fois mis en minuscules."""
    index = {}
    for terme_central, synonymes in SYNONYMES.items():
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

    if not termes_trouves:
        return question

    return question + " " + " ".join(sorted(termes_trouves))

