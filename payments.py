# -*- coding: utf-8 -*-
"""
Module de paiement de Fisca AI.

Architecture identique au filet de securite OpenAI (engine.py) : chaque
fournisseur de paiement (MyNITA, iMoney) est represente par une fonction
qui verifie d'abord si elle est configuree (cle API presente), tente le
paiement si oui, et retourne un statut clair sinon. Tant qu'aucune cle
n'est configuree, le systeme retombe automatiquement sur le circuit
manuel existant (commande via WhatsApp), sans jamais bloquer
l'utilisateur ni faire planter le site.

Pour activer un fournisseur plus tard : ajouter la variable
d'environnement correspondante sur Render (ex. MYNITA_API_KEY) et
completer la fonction d'appel avec la vraie documentation technique
fournie par le prestataire au moment de l'ouverture du compte marchand.
"""
import os

MYNITA_API_KEY = os.environ.get("MYNITA_API_KEY")
MYNITA_MARCHAND_ID = os.environ.get("MYNITA_MARCHAND_ID")

IMONEY_API_KEY = os.environ.get("IMONEY_API_KEY")
IMONEY_MARCHAND_ID = os.environ.get("IMONEY_MARCHAND_ID")


def mynita_configure():
    return bool(MYNITA_API_KEY and MYNITA_MARCHAND_ID)


def imoney_configure():
    return bool(IMONEY_API_KEY and IMONEY_MARCHAND_ID)


def initier_paiement_mynita(montant_fcfa, description, reference_interne):
    """Initie un paiement via l'API MyNITA. Retourne un dict avec au
    moins {"ok": bool, "lien_paiement": str|None, "erreur": str|None}.

    NON IMPLEMENTE : ceci est un emplacement reserve. Quand le compte
    marchand MyNITA sera ouvert, remplacer le corps de cette fonction
    par le veritable appel a leur API (endpoint, authentification et
    format exacts fournis par NITA au moment de l'inscription).
    """
    if not mynita_configure():
        return {"ok": False, "lien_paiement": None, "erreur": "mynita_non_configure"}

    # --- EMPLACEMENT RESERVE POUR L'APPEL REEL A L'API MYNITA ---
    # Exemple de structure attendue (a adapter selon leur documentation) :
    #
    # import requests
    # reponse = requests.post(
    #     "https://api.mynita.ne/v1/paiements",  # URL fictive, a remplacer
    #     headers={"Authorization": f"Bearer {MYNITA_API_KEY}"},
    #     json={
    #         "marchand_id": MYNITA_MARCHAND_ID,
    #         "montant": montant_fcfa,
    #         "devise": "XOF",
    #         "description": description,
    #         "reference": reference_interne,
    #     },
    #     timeout=15,
    # )
    # data = reponse.json()
    # return {"ok": True, "lien_paiement": data["lien_paiement"], "erreur": None}

    return {"ok": False, "lien_paiement": None, "erreur": "integration_non_terminee"}


def initier_paiement_imoney(montant_fcfa, description, reference_interne):
    """Meme principe que MyNITA, pour le fournisseur iMoney (iFUTUR).
    NON IMPLEMENTE : emplacement reserve, a completer avec la vraie
    documentation technique d'iMoney."""
    if not imoney_configure():
        return {"ok": False, "lien_paiement": None, "erreur": "imoney_non_configure"}

    # --- EMPLACEMENT RESERVE POUR L'APPEL REEL A L'API IMONEY ---
    return {"ok": False, "lien_paiement": None, "erreur": "integration_non_terminee"}


def initier_paiement(montant_fcfa, description, reference_interne, fournisseur_prefere="mynita"):
    """Point d'entree unique. Essaie le fournisseur prefere, puis
    l'autre si le premier n'est pas configure. Si aucun n'est
    configure, retourne un statut clair indiquant de basculer sur le
    circuit manuel (WhatsApp) - jamais d'erreur bloquante."""
    fournisseurs = {
        "mynita": initier_paiement_mynita,
        "imoney": initier_paiement_imoney,
    }
    ordre = [fournisseur_prefere] + [f for f in fournisseurs if f != fournisseur_prefere]

    for nom in ordre:
        resultat = fournisseurs[nom](montant_fcfa, description, reference_interne)
        if resultat["ok"]:
            resultat["fournisseur"] = nom
            return resultat

    return {
        "ok": False,
        "lien_paiement": None,
        "fournisseur": None,
        "erreur": "aucun_fournisseur_configure",
    }
