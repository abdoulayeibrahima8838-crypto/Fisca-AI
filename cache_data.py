# -*- coding: utf-8 -*-
"""
Bibliotheque documentaire de Fisca AI - PHASE TEST.

Ce fichier contient les questions/reponses actuellement connues par Fisca AI.
Chaque entree doit etre validee avec le CGI 2026, les arretes et circulaires
avant toute mise en production reelle. Le champ "verified" indique le statut.

Pour ajouter une question : copier un bloc, changer "keywords" (mots-cles
qui doivent apparaitre dans la question de l'utilisateur pour declencher
cette reponse), "answer" et "source".
"""

DOCUMENT_ACTIF = "Comprendre la Facture Certifiee"

QA_LIBRARY = [
    {
        "id": "qui-concerne",
        "keywords": ["qui", "concerne", "concernee", "beneficiaire", "marche public", "tout le monde"],
        "question_type": "Qui est concerne par la facture certifiee ?",
        "answer": (
            "Toutes les personnes assujetties a la TVA doivent emettre une facture "
            "certifiee pour l'ensemble de leurs transactions, pas seulement les "
            "beneficiaires de marches publics."
        ),
        "source": "Contenu test - a confirmer avec le CGI 2026 et les textes reglementaires",
        "verified": False,
    },
    {
        "id": "choix-systeme",
        "keywords": ["quel systeme", "choisir", "systeme de certification", "secef choix"],
        "question_type": "Quel systeme de certification choisir ?",
        "answer": (
            "Le contribuable choisit librement son SECeF parmi la liste des "
            "fournisseurs homologues, mise a jour regulierement sur le site de "
            "la DGI. Plusieurs types de dispositifs existent : solutions "
            "logicielles, modules de controle de facturation, unites de "
            "facturation."
        ),
        "source": "Contenu test - a confirmer avec le CGI 2026 et les textes reglementaires",
        "verified": False,
    },
    {
        "id": "systemes-identiques",
        "keywords": ["systemes", "identiques", "meme systeme", "differents dispositifs"],
        "question_type": "Les systemes de certification sont-ils tous identiques ?",
        "answer": (
            "Non. Plusieurs types de dispositifs homologues existent : solutions "
            "logicielles de facturation, modules de controle de facturation, "
            "unites de facturation."
        ),
        "source": "Contenu test - a confirmer avec le CGI 2026 et les textes reglementaires",
        "verified": False,
    },
    {
        "id": "sanctions",
        "keywords": ["sanction", "amende", "penalite", "consequence non delivrance"],
        "question_type": "Quelles sont les sanctions en cas de non-respect ?",
        "answer": (
            "Une amende peut s'appliquer en cas de non-delivrance ou de facture "
            "minoree. Le taux exact (calcule sur la TVA eludee sous l'ancien "
            "texte) doit etre reconfirme avec le nouveau CGI 2026."
        ),
        "source": "Contenu test - taux a reconfirmer, ne pas diffuser tel quel",
        "verified": False,
    },
    {
        "id": "impact-tva",
        "keywords": ["tva", "deduction tva", "consequence tva"],
        "question_type": "Quel est l'impact sur la TVA si la facture n'est pas certifiee ?",
        "answer": "La TVA n'est deductible que si elle figure sur une facture certifiee.",
        "source": "Contenu test - a confirmer avec le CGI 2026 et les textes reglementaires",
        "verified": False,
    },
    {
        "id": "impact-isb",
        "keywords": ["isb", "charge deductible", "impot sur les benefices"],
        "question_type": "Quel est l'impact sur l'ISB si la facture n'est pas certifiee ?",
        "answer": "Une charge n'est deductible a l'ISB que si elle est justifiee par une facture certifiee.",
        "source": "Contenu test - a confirmer avec le CGI 2026 et les textes reglementaires",
        "verified": False,
    },
    {
        "id": "pourquoi",
        "keywords": ["pourquoi", "objectif", "instauree", "raison"],
        "question_type": "Pourquoi la facture certifiee a-t-elle ete instauree ?",
        "answer": (
            "La facture certifiee vise a reduire la fraude sur la TVA, accroitre "
            "les ressources de l'Etat, et renforcer l'egalite de tous devant "
            "l'impot."
        ),
        "source": "Contenu test - a confirmer avec le CGI 2026 et les textes reglementaires",
        "verified": False,
    },
]

SUGGESTIONS = [
    "Qui est concerne par la facture certifiee ?",
    "Quel systeme de certification choisir ?",
    "Quelles sont les sanctions en cas de non-respect ?",
    "Pourquoi la facture certifiee a-t-elle ete instauree ?",
]
