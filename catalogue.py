# -*- coding: utf-8 -*-
"""
Catalogue commercial de Fisca AI : livres/formations a vendre, documents
officiels a telecharger gratuitement, et abonnements Fisca AI (inactifs
pendant la phase test, prets a activer plus tard en changeant juste
"disponible" a True).
"""

WHATSAPP_NUMERO = "22791870434"  # sans le +, format attendu par wa.me


def lien_whatsapp_commande(nom_produit, nom_client=""):
    """Construit un lien wa.me avec un message pre-rempli pour la commande."""
    texte = f"Bonjour, je souhaite commander : {nom_produit}"
    if nom_client:
        texte += f" (Mon nom : {nom_client})"
    texte_encode = texte.replace(" ", "%20").replace(":", "%3A").replace(",", "%2C").replace("(", "%28").replace(")", "%29")
    return f"https://wa.me/{WHATSAPP_NUMERO}?text={texte_encode}"


# ---------------------------------------------------------------------------
# Livres et formations a vendre
# ---------------------------------------------------------------------------
CATALOGUE = [
    {
        "id": "livre-facture-certifiee",
        "titre": "Comprendre la Facture Certifiee",
        "auteur": "Moutari Abdoulaye",
        "type": "Livre",
        "description": "Le guide de reference sur la facture certifiee au Niger : cadre juridique, technique, sanctions et cas pratiques.",
        "prix_fcfa": 10000,
        "prix_original_fcfa": 15000,
        "couverture_emoji": "📘",
        "couverture_couleur": "#E07A3F",
        "couverture_image": "/images/couverture_livre_3d.png",
        "disponible_a_la_vente": True,
    },
    {
        "id": "ebook-cgi-2026",
        "titre": "Comprendre le Nouveau CGI 2026",
        "auteur": "Fisca Times",
        "type": "E-book",
        "description": "Les principaux changements du Code General des Impots 2026 expliques simplement.",
        "prix_fcfa": None,
        "couverture_emoji": "📗",
        "couverture_couleur": "#3E7D5A",
        "disponible_a_la_vente": False,  # Bientot disponible
    },
    {
        "id": "formation-fiscalite",
        "titre": "Formation : Bases de la Fiscalite Nigerienne",
        "auteur": "Fisca Times",
        "type": "Formation",
        "description": "Formation pratique pour comprendre et appliquer les obligations fiscales courantes.",
        "prix_fcfa": None,
        "couverture_emoji": "🎓",
        "couverture_couleur": "#C9A24B",
        "disponible_a_la_vente": False,  # Bientot disponible
    },
]


# ---------------------------------------------------------------------------
# Documents officiels telechargeables gratuitement
# ---------------------------------------------------------------------------
DOCUMENTS_TELECHARGEABLES = [
    {
        "id": "cgi-2026-pdf",
        "titre": "Code General des Impots 2026",
        "auteur": "Republique du Niger",
        "description": "Texte integral officiel du CGI 2026.",
        "couverture_emoji": "⚖️",
        "couverture_couleur": "#0E2A3A",
        "fichier": "cgi_2026.pdf",
    },
    {
        "id": "arrete-473-pdf",
        "titre": "Arrete N°00473 (20 nov. 2020)",
        "auteur": "Ministere des Finances - DGI",
        "description": "Conditions de commercialisation et de distribution des SECeF au Niger.",
        "couverture_emoji": "📄",
        "couverture_couleur": "#3E7D5A",
        "fichier": "arrete_473.pdf",
    },
    {
        "id": "arrete-474-pdf",
        "titre": "Arrete N°00474 (20 nov. 2020)",
        "auteur": "Ministere des Finances - DGI",
        "description": "Modalites d'utilisation des systemes electroniques de facturation.",
        "couverture_emoji": "📄",
        "couverture_couleur": "#3E7D5A",
        "fichier": "arrete_474.pdf",
    },
]


# ---------------------------------------------------------------------------
# Abonnements Fisca AI (3 paniers) - INACTIFS pendant la phase test.
# Pour activer plus tard : passer "disponible" a True sur le(s) plan(s)
# voulu(s). L'affichage et les boutons se debloquent automatiquement.
# ---------------------------------------------------------------------------
ABONNEMENTS = [
    {
        "id": "gratuit",
        "nom": "Gratuit",
        "prix_fcfa": 0,
        "periode": "toujours",
        "avantages": [
            "5 questions par jour",
            "Acces a la bibliotheque de base",
        ],
        "disponible": True,  # C'est le plan actuel par defaut
        "recommande": False,
    },
    {
        "id": "standard",
        "nom": "Standard",
        "prix_fcfa": None,  # A DEFINIR avant activation
        "periode": "par mois",
        "avantages": [
            "50 questions par jour",
            "Reponses via l'IA (recherche complete dans les documents)",
            "Historique illimite",
        ],
        "disponible": False,  # Bientot disponible
        "recommande": True,
    },
    {
        "id": "expert",
        "nom": "Expert Fiscal",
        "prix_fcfa": None,  # A DEFINIR avant activation
        "periode": "par mois",
        "avantages": [
            "Questions illimitees",
            "Acces prioritaire a l'IA",
            "Tous les documents et livres inclus",
            "Support direct par WhatsApp",
        ],
        "disponible": False,  # Bientot disponible
        "recommande": False,
    },
]
