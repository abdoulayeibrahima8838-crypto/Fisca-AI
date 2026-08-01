# -*- coding: utf-8 -*-
"""
Bibliotheque documentaire de Fisca AI.

Contenu verifie directement dans le Code General des Impots (CGI) 2026,
fourni par l'utilisateur. Chaque entree cite l'article exact.
"""

DOCUMENT_ACTIF = "Code General des Impots 2026 - Facture certifiee"

QA_LIBRARY = [
    {
        "id": "qui-concerne",
        "keywords": ["qui", "concerne", "concernee", "beneficiaire", "marche public", "tout le monde", "forfait", "forfaitaire"],
        "question_type": "Qui est concerne par la facture certifiee ?",
        "answer": (
            "Toute personne physique ou morale soumise a l'impot sur les societes, "
            "a l'impot sur les benefices d'affaires des personnes physiques, a "
            "l'impot forfaitaire, ou assujettie a la TVA, doit delivrer une facture "
            "certifiee. Le regime forfaitaire n'est pas automatiquement dispense : "
            "seule une derogation expresse du Directeur General des Impots peut "
            "exempter une personne, au cas par cas."
        ),
        "source": "Art. 802 du CGI 2026",
        "verified": True,
    },
    {
        "id": "choix-systeme",
        "keywords": ["quel systeme", "choisir", "systeme de certification", "secef choix", "homologue"],
        "question_type": "Quel systeme de certification choisir ?",
        "answer": (
            "Un systeme electronique certifie de facturation est une unite de "
            "facturation ou un logiciel de facturation d'entreprise homologue par "
            "la DGI, relie a un module de controle de facturation. Il doit obtenir "
            "un certificat de conformite avant d'etre commercialise ou utilise."
        ),
        "source": "Art. 804 du CGI 2026",
        "verified": True,
    },
    {
        "id": "systeme-interne",
        "keywords": ["systeme interne", "deja paye", "mon propre logiciel", "logiciel deja", "propre systeme"],
        "question_type": "J'ai deja un systeme de facturation interne, dois-je le changer ?",
        "answer": (
            "Si vous utilisez votre propre systeme de facturation electronique, "
            "vous devez suivre une procedure d'auto-declaration aupres de la DGI "
            "et obtenir une attestation de conformite. Sans cette attestation, "
            "vous vous exposez a une amende."
        ),
        "source": "Art. 804 (points 6-7) du CGI 2026",
        "verified": True,
    },
    {
        "id": "sanctions",
        "keywords": ["sanction", "amende", "penalite", "consequence non delivrance", "combien"],
        "question_type": "Quelles sont les sanctions en cas de non-respect ?",
        "answer": (
            "Deux cas bien distincts. 1) Vous n'avez PAS de systeme electronique "
            "certifie du tout (pas de machine, pas de logiciel homologue) et "
            "vous vendez quand meme : amende forfaitaire de 2 000 000 FCFA. "
            "2) Vous AVEZ un systeme mais vous ne l'utilisez pas pour delivrer "
            "la facture, ou vous delivrez une facture minoree : amende egale "
            "au montant de la TVA due, avec un minimum de 100 000 FCFA par "
            "facture (par exemple, pour une vente de 100 000 FCFA HT au taux "
            "normal de TVA, l'amende serait de 19 000 FCFA, mais comme c'est "
            "sous le minimum, c'est 100 000 FCFA qui s'applique). En cas de "
            "recidive : amende de 4 000 000 FCFA, fermeture administrative de "
            "l'entreprise, et poursuites penales possibles. Le paiement de "
            "l'amende ne dispense jamais du paiement de la TVA elle-meme."
        ),
        "source": "Art. 828 du CGI 2026 ; exemples pratiques : Comprendre la Facture Certifiee (M. Abdoulaye), chap. 7",
        "verified": True,
    },
    {
        "id": "impact-tva",
        "keywords": ["tva", "deduction tva", "consequence tva"],
        "question_type": "Quel est l'impact sur la TVA si la facture n'est pas certifiee ?",
        "answer": (
            "La TVA sur un achat n'est deductible que si elle est mentionnee "
            "distinctement sur une facture certifiee conforme aux mentions de "
            "l'article 802, ou un document en tenant lieu."
        ),
        "source": "Art. 346 du CGI 2026",
        "verified": True,
    },
    {
        "id": "impact-isb",
        "keywords": ["isb", "charge deductible", "impot sur les benefices", "impot sur les societes"],
        "question_type": "Quel est l'impact sur l'ISB si la facture n'est pas certifiee ?",
        "answer": (
            "Pour etre deductible, une charge doit etre appuyee d'une facture "
            "portant les mentions obligatoires de l'article 802 (sauf derogations "
            "prevues au meme article). Une charge sans facture certifiee conforme "
            "risque d'etre rejetee de la deduction."
        ),
        "source": "Art. 23 du CGI 2026",
        "verified": True,
    },
    {
        "id": "fournisseur-non-homologue",
        "keywords": ["fournisseur", "non homologue", "vendeur systeme", "editeur logiciel"],
        "question_type": "Que risque un fournisseur qui vend un systeme non homologue ?",
        "answer": (
            "Les fournisseurs de systemes de facturation et editeurs de logiciels "
            "qui ne respectent pas l'obligation d'homologation risquent une amende "
            "d'1 000 000 FCFA, portee a 10 000 000 FCFA en cas de recidive, sans "
            "prejudice des sanctions penales."
        ),
        "source": "Art. 828 (point 6) du CGI 2026",
        "verified": True,
    },
    {
        "id": "fournisseurs-etrangers",
        "keywords": ["etranger", "fournisseur etranger", "hors du niger", "importation service", "dispense etranger"],
        "question_type": "Les fournisseurs etrangers sont-ils dispenses de la facture certifiee ?",
        "answer": (
            "Non. Un fournisseur assujetti a la TVA etabli hors du Niger doit "
            "faire accrediter un representant domicilie au Niger, qui s'engage a "
            "remplir les formalites et a delivrer la facture certifiee en son "
            "nom. A defaut de representant, la TVA et les penalites deviennent "
            "dues par le client ou par la personne chargee de la facturation."
        ),
        "source": "Art. 364 du CGI 2026",
        "verified": True,
    },
    {
        "id": "mentions-obligatoires",
        "keywords": ["mentions obligatoires", "que doit contenir", "information sur la facture", "quoi figurer"],
        "question_type": "Quelles informations doivent figurer sur la facture certifiee ?",
        "answer": (
            "La date de facturation, un numero unique en sequence chronologique "
            "continue, la nature de l'operation, le prix hors taxe, le taux et le "
            "montant de la TVA, l'identification complete du vendeur (y compris "
            "son Numero d'Identification Fiscale) et celle du client (y compris "
            "son NIF)."
        ),
        "source": "Art. 366 du CGI 2026",
        "verified": True,
    },
    {
        "id": "facture-hors-systeme",
        "keywords": ["pas emise par le systeme", "hors systeme", "sans passer par la machine", "contourne"],
        "question_type": "Que se passe-t-il si ma facture n'est pas emise par le systeme alors que j'en ai un ?",
        "answer": (
            "Une facture qui n'est pas delivree par le systeme electronique "
            "certifie, alors que vous en disposez, n'ouvre droit ni a la "
            "deduction de la TVA, ni a la deduction de la charge correspondante "
            "en matiere d'impot sur les societes ou d'impot sur les benefices "
            "d'affaires."
        ),
        "source": "Art. 803 du CGI 2026",
        "verified": True,
    },
    {
        "id": "seuil-forfaitaire",
        "keywords": ["seuil forfaitaire", "chiffre d'affaires forfaitaire", "petit commercant", "regime forfait"],
        "question_type": "A partir de quel chiffre d'affaires est-on au regime forfaitaire ?",
        "answer": (
            "Le regime du forfait s'applique aux entreprises individuelles (hors "
            "professions liberales) dont le chiffre d'affaires est inferieur a "
            "50 000 000 FCFA. Ces entreprises restent en principe soumises a "
            "l'obligation de facture certifiee comme les autres regimes."
        ),
        "source": "Art. 120 du CGI 2026",
        "verified": True,
    },
    {
        "id": "derogations",
        "keywords": ["derogation", "dispense", "exempte", "qui est dispense", "exception"],
        "question_type": "Peut-on obtenir une dispense d'utiliser le SECeF ?",
        "answer": (
            "Oui, sous conditions strictes. Certaines professions ont beneficie "
            "de derogations temporaires par le passe (ex. pharmacies, "
            "cliniques, cabinets medicaux en 2021). En dehors de ces cas "
            "historiques, toute personne non dispensee peut demander une "
            "derogation individuelle : elle doit justifier pourquoi elle ne "
            "peut pas utiliser de SECeF, ne pas exercer dans la distribution "
            "ou une profession liberale, et sa demande est examinee en "
            "plusieurs etapes par les services fiscaux avant decision finale "
            "du Directeur Central ou Regional."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, sections 7.3-7.4 ; Art. 368 bis du CGI",
        "verified": True,
    },
    {
        "id": "documents-tenant-lieu",
        "keywords": ["document tenant lieu", "document de remplacement", "sans facture", "douane", "quittance", "menue depense", "petite depense"],
        "question_type": "Quels documents peuvent remplacer la facture certifiee ?",
        "answer": (
            "Plusieurs types de documents sont reconnus comme equivalents a "
            "une facture certifiee : les factures des personnes beneficiant "
            "d'une derogation en cours de validite, les documents douaniers "
            "(import/export), les titres de perception et avis d'imposition "
            "emis par l'administration, les quittances de paiement de "
            "services publics, les declarations de recettes du Tresor public, "
            "et les documents relatifs aux menues depenses limitees a "
            "100 000 FCFA par an et par beneficiaire."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section VIII (8.1 a 8.9)",
        "verified": True,
    },
    {
        "id": "pas-de-secef-vs-machine-inutilisee",
        "keywords": ["pas de machine", "sans secef", "pas equipe", "je n'ai pas la machine", "pas de systeme", "pas de secef", "aucun systeme", "du tout"],
        "question_type": "Que risque-t-on si on n'a pas du tout de systeme SECeF ?",
        "answer": (
            "Toute personne soumise a l'obligation qui vend des biens ou "
            "services sans disposer d'aucun systeme electronique certifie de "
            "facturation est passible d'une amende forfaitaire de 2 000 000 "
            "FCFA. C'est different du cas ou vous avez la machine mais ne "
            "l'utilisez pas pour delivrer la facture (amende egale au montant "
            "de la TVA, minimum 100 000 FCFA)."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 7, section 7.1 ; Art. 828 du CGI 2026",
        "verified": True,
    },
    {
        "id": "panne-secef",
        "keywords": ["panne", "en panne", "dysfonctionnement machine", "machine cassee", "ne marche plus"],
        "question_type": "Que faire en cas de panne du dispositif SECeF ?",
        "answer": (
            "Vous devez disposer a l'avance d'un SECeF de remplacement pour "
            "les cas ou la facturation ne peut pas etre decalee lors d'une "
            "panne bloquante - ce n'est pas facultatif, c'est une obligation "
            "prealable. En cas de panne bloquante, vous devez notifier "
            "immediatement l'administration fiscale ET le fournisseur, par "
            "ecrit ou par saisine electronique. Si le DGI autorise "
            "exceptionnellement une facturation non electronique le temps de "
            "la panne, vous devez ensuite reprendre de maniere exhaustive "
            "toutes les ventes dans le SECeF des que possible, et notifier a "
            "nouveau quand le probleme est resolu."
        ),
        "source": "Art. 4 (point b) et Art. 5 (point k) de l'Arrete 00474 du 20 novembre 2020 (modalites d'utilisation)",
        "verified": True,
    },
    {
        "id": "pas-de-connexion-internet",
        "keywords": ["pas internet", "connexion internet", "hors ligne", "pas de reseau", "internet coupe", "pas de connexion"],
        "question_type": "Que faire en l'absence de connexion internet pour le e-SECeF ?",
        "answer": (
            "Precision importante : le SECeF fonctionne via le reseau GSM "
            "(reseau mobile), pas une connexion internet classique de type "
            "wifi/fibre. Vous devez placer votre SECeF dans un endroit qui "
            "capte le reseau GSM et surveiller cette connectivite en "
            "permanence. En cas d'indisponibilite temporaire (probleme de "
            "connexion ou panne de la plateforme), un systeme physique de "
            "facturation certifie doit etre utilise en remplacement le temps "
            "que la connexion soit retablie, notamment pour les utilisateurs "
            "du e-SECeF (version dematerialisee)."
        ),
        "source": "Art. 5 (points l et m) de l'Arrete 00474 du 20 novembre 2020 ; Comprendre la Facture Certifiee (M. Abdoulaye), chap. 5, section V",
        "verified": True,
    },
    {
        "id": "nif-client-particulier",
        "keywords": ["pas de nif", "sans nif", "je n'ai pas de nif", "client particulier", "nif obligatoire"],
        "question_type": "Le NIF du client est-il toujours obligatoire sur la facture ?",
        "answer": (
            "Non. Le Numero d'Identification Fiscale (NIF) du client n'est "
            "exige que si le client est une entreprise. Pour un particulier "
            "(consommateur final sans activite professionnelle), cette "
            "mention n'est pas requise sur la facture certifiee."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section VI (mentions obligatoires - informations sur le client)",
        "verified": True,
    },
    {
        "id": "vendre-des-machines-secef",
        "keywords": ["vendre ma machine", "vendre des machines", "distribuer machine", "commercialiser secef", "devenir fournisseur", "revendre ma machine", "ceder ma machine"],
        "question_type": "Peut-on vendre, revendre ou ceder une machine SECeF ?",
        "answer": (
            "Deux situations differentes. En tant que FOURNISSEUR "
            "homologue par la DGI, vous pouvez commercialiser des machines "
            "(prix fixe librement), mais vendre des machines non certifiees "
            "entraine le retrait immediat de votre certificat, en plus de "
            "sanctions penales. En tant qu'ENTREPRISE UTILISATRICE qui "
            "voudrait revendre sa propre machine deja en service : le "
            "certificat de conformite ou l'attestation individuelle est "
            "propre a l'entreprise qui l'a obtenu et ne peut JAMAIS etre "
            "transmis a une autre entreprise, quelle que soit la maniere. "
            "L'acheteur eventuel devrait donc obtenir sa propre certification "
            "aupres de la DGI, independamment de la machine physique."
        ),
        "source": "Art. 11 et 18 de l'Arrete 00473 du 20 novembre 2020 (commercialisation SECeF)",
        "verified": True,
    },
]

SUGGESTIONS = [
    "Qui est concerne par la facture certifiee ?",
    "Quelles sont les sanctions en cas de non-respect ?",
    "Quel est l'impact sur la TVA si la facture n'est pas certifiee ?",
    "J'ai deja un systeme de facturation interne, dois-je le changer ?",
]
