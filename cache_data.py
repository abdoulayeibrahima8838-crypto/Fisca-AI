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
        "keywords": ["qui", "concerne", "concernee", "beneficiaire", "marche public", "tout le monde", "forfait", "forfaitaire", "applique a moi", "oblige d'avoir", "obligatoire pour moi"],
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
        "keywords": ["quel systeme", "choisir", "systeme de certification", "secef choix", "homologue", "quel type", "type prendre"],
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
        "keywords": ["sanction", "amende", "penalite", "consequence non delivrance"],
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
        "keywords": ["tva", "deduction tva", "consequence tva", "recuperer taxe", "recuperer tva"],
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
        "keywords": ["mentions obligatoires", "que doit contenir", "information sur la facture", "quoi figurer", "quoi ecrit", "ecrit sur la facture", "doit contenir"],
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
        "keywords": ["seuil forfaitaire", "chiffre d'affaires forfaitaire", "petit commercant", "regime forfait", "50 millions"],
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
            "Oui, deux voies possibles. D'abord, une liste de categories "
            "sont dispensees de plein droit : l'Etat et les collectivites "
            "publiques (hors activite commerciale), les agriculteurs/"
            "eleveurs/jardiniers vendant sans transformation (mais pas les "
            "intermediaires qui revendent), les bailleurs d'immeubles nus a "
            "titre personnel, les societes publiques d'eau et d'electricite, "
            "les banques et etablissements financiers, les compagnies "
            "d'assurance, les compagnies aeriennes etrangeres (pour leurs "
            "propres produits), et les distributeurs agrees de "
            "telecommunications (cartes prepayees). Le regime de l'impot "
            "synthetique a beneficie d'une exemption temporaire du 30 "
            "septembre 2021 au 1er fevrier 2023 (sauf importateurs/"
            "exportateurs, exclus de cette dispense - attention, une "
            "entreprise immatriculee sous 'IMPORT EXPORT' sans reellement "
            "importer/exporter est automatiquement exclue). Ensuite, toute "
            "autre personne non dispensee peut demander une derogation "
            "individuelle en justifiant pourquoi elle ne peut pas utiliser "
            "de SECeF (hors distribution et professions liberales), "
            "examinee par les services fiscaux avant decision finale."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, sections 7.2-7.4 ; Art. 368 bis du CGI",
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
        "keywords": ["pas de machine", "sans secef", "pas equipe", "je n'ai pas la machine", "pas de systeme", "pas de secef", "aucun systeme", "du tout", "zero equipement", "aucun equipement"],
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
    {
        "id": "systemes-identiques",
        "keywords": ["systemes identiques", "meme systeme", "differents dispositifs", "tous pareils"],
        "question_type": "Les systemes de certification sont-ils tous identiques ?",
        "answer": (
            "Non. Plusieurs types de dispositifs homologues existent : "
            "unites de facturation (UF), modules de controle de facturation "
            "(MCF), et systemes de facturation d'entreprise (logiciels) "
            "homologues separement."
        ),
        "source": "Art. 804 du CGI 2026 ; Arrete 00473 (definitions)",
        "verified": True,
    },
    {
        "id": "pourquoi",
        "keywords": ["pourquoi", "objectif", "instauree", "raison", "but de la loi", "cette loi existe"],
        "question_type": "Pourquoi la facture certifiee a-t-elle ete instauree ?",
        "answer": (
            "La facture certifiee vise a reduire la fraude sur la TVA, "
            "accroitre les ressources de l'Etat, et renforcer l'egalite de "
            "tous devant l'impot."
        ),
        "source": "Ministere des Finances / DGI (communication officielle sur la reforme)",
        "verified": True,
    },
    {
        "id": "prix-machines-secef",
        "keywords": ["prix", "coute", "combien coute", "cher", "tarif", "montant machine", "gratuit", "gratuite", "e-secef gratuit"],
        "question_type": "Combien coute une machine ou un systeme SECeF ?",
        "answer": (
            "Ca depend du type de systeme choisi. Pour les machines "
            "physiques (unites de facturation UF, modules de controle "
            "MCF), l'arrete 00473 precise que les fournisseurs homologues "
            "sont LIBRES de fixer leur prix eux-memes - il n'y a pas de "
            "tarif legal impose. A titre purement indicatif (pas un prix "
            "officiel), un responsable de la DGI a evoque plus de 300 000 "
            "FCFA comme ordre de grandeur couramment pratique par les "
            "fournisseurs lors d'une intervention televisee - le prix "
            "reel varie donc d'un fournisseur a l'autre, et il vaut mieux "
            "comparer plusieurs devis. Sinon, l'Etat a aussi introduit le "
            "e-SECeF (version dematerialisee, accessible par smartphone, "
            "tablette ou ordinateur connecte a internet) : celui-ci est "
            "GRATUIT, specialement pense pour alleger les charges des "
            "PME/TPE qui n'ont pas les moyens du materiel physique."
        ),
        "source": "Art. 21 et 23 de l'Arrete 00473 du 20 novembre 2020 (prix libre) ; Comprendre la Facture Certifiee (M. Abdoulaye), chap. 5 (avantages du e-SECeF, prix indicatif cite par la DGI)",
        "verified": True,
    },
    {
        "id": "definition-facture",
        "keywords": ["c'est quoi une facture", "definition facture", "qu'est ce qu'une facture", "signification facture"],
        "question_type": "Qu'est-ce qu'une facture, au sens juridique ?",
        "answer": (
            "Une facture est un document commercial qui atteste d'une "
            "transaction entre un vendeur et un acheteur, precisant les "
            "biens ou services fournis ainsi que les conditions de "
            "paiement. Pour la facture certifiee specifiquement, le CGI la "
            "definit comme une facture emise et transmise via un systeme "
            "electronique certifie de facturation par la DGI."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 1, sections I-II ; Art. 368 bis du CGI",
        "verified": True,
    },
    {
        "id": "fonctions-facture",
        "keywords": ["fonctions de la facture", "role de la facture", "a quoi sert une facture"],
        "question_type": "Quelles sont les fonctions d'une facture ?",
        "answer": (
            "La facture remplit 4 fonctions principales : juridique "
            "(preuve d'un contrat, utile en cas de litige), comptable "
            "(enregistrement des recettes/depenses, justificatif "
            "d'audit), fiscale (calcul et controle des taxes), et "
            "douaniere (determination des droits a l'import/export, lutte "
            "contre la fraude)."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 1, section II",
        "verified": True,
    },
    {
        "id": "archivage-factures",
        "keywords": ["archiver les factures", "conservation facture", "garder les factures", "obligation archivage"],
        "question_type": "Quelle est l'obligation d'archivage des factures ?",
        "answer": (
            "L'archivage des factures est une obligation legale. Il "
            "permet de repondre aux demandes des autorites, de se "
            "proteger en cas de litige, et d'eviter des sanctions. Les "
            "factures doivent etre bien organisees, accessibles, et "
            "conservees dans un format securise (papier ou electronique)."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 1, section III",
        "verified": True,
    },
    {
        "id": "limites-factures-traditionnelles",
        "keywords": ["facture word", "facture excel", "facture papier", "inconvenients facture traditionnelle"],
        "question_type": "Quels sont les inconvenients des factures traditionnelles (Word/Excel/papier) ?",
        "answer": (
            "Les factures traditionnelles presentent plusieurs "
            "inconvenients : erreurs humaines de saisie/calcul, "
            "tracabilite limitee lors des controles, archivage physique "
            "contraignant, et risque de fraude/falsification plus eleve. "
            "Elles sont d'ailleurs considerees comme obsoletes et non "
            "conformes depuis la reforme, sauf cas specifiques dispenses."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 1, section IV",
        "verified": True,
    },
    {
        "id": "phases-deploiement",
        "keywords": ["depuis quand facture certifiee", "phases deploiement", "historique reforme", "quand a commence"],
        "question_type": "Depuis quand la facture certifiee existe, et quelles ont ete ses phases de deploiement ?",
        "answer": (
            "La facture certifiee a ete instauree par la loi de decembre "
            "2019, avec une entree en vigueur effective en septembre "
            "2021. Le deploiement s'est fait en 3 phases : 1) 2020 - "
            "instauration du SECeF, 2) 2021 - grandes/moyennes "
            "entreprises et regime reel d'imposition, 3) 2023 - inclusion "
            "des petites et micro-entreprises, avec un systeme devenu "
            "totalement gratuit (e-SECeF)."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 2, section III",
        "verified": True,
    },
    {
        "id": "resultats-reforme",
        "keywords": ["resultats de la reforme", "impact recettes fiscales", "ca a rapporte quoi"],
        "question_type": "Quels resultats concrets la reforme a-t-elle produits ?",
        "answer": (
            "La reforme a permis une amelioration notable des recettes "
            "fiscales : pour la premiere fois en 2022, la DGI a depasse "
            "le seuil de 600 milliards de FCFA en recettes cash. Elle a "
            "aussi apporte une meilleure transparence des transactions et "
            "une reduction des fraudes commerciales et fiscales."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 2, section IV",
        "verified": True,
    },
    {
        "id": "refus-vendeur",
        "keywords": ["vendeur refuse", "il ne veut pas me donner la facture", "refus de facture"],
        "question_type": "Que faire si le vendeur refuse de delivrer une facture certifiee ?",
        "answer": (
            "En tant que client, vous devez d'abord exiger la facture "
            "certifiee, meme si le vendeur ne la propose pas "
            "spontanement. Si le fournisseur persiste dans son refus, "
            "vous devez en informer la DGI. Exiger sa facture, c'est "
            "s'assurer que la TVA payee est bien reversee a l'Etat."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section III",
        "verified": True,
    },
    {
        "id": "verification-facture",
        "keywords": ["verifier une facture", "authenticite facture", "comment verifier", "sygma"],
        "question_type": "Comment verifier l'authenticite d'une facture certifiee ?",
        "answer": (
            "Le client peut verifier une facture certifiee via le site "
            "ou l'application mobile de la DGI (sygma.impots.gouv.ne), "
            "grace aux references ou au QR code figurant sur la facture. "
            "En cas de doute, contactez immediatement la DGI ou demandez "
            "au fournisseur de corriger les erreurs ou incoherences."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section IV",
        "verified": True,
    },
    {
        "id": "types-facture",
        "keywords": ["types de facture", "facture exportation", "facture des ventes"],
        "question_type": "Quels sont les differents types de facture certifiee ?",
        "answer": (
            "Il existe 3 types de facture certifiee : la facture des "
            "ventes (transactions domestiques a l'interieur du pays), la "
            "facture d'exportation (ventes a l'etranger, avec mentions "
            "specifiques), et la facture d'avoir (annulation ou "
            "rectification d'une facture anterieure)."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section V",
        "verified": True,
    },
    {
        "id": "facture-avoir",
        "keywords": ["facture d'avoir", "annuler une facture", "corriger une facture", "retour marchandise"],
        "question_type": "Qu'est-ce qu'une facture d'avoir, et quand l'utiliser ?",
        "answer": (
            "Une facture d'avoir sert a annuler ou rectifier une facture "
            "anterieure. Elle intervient notamment en cas de retour de "
            "marchandises, d'erreur dans le montant facture, "
            "d'ajustement suite a des conditions speciales, ou de "
            "regularisation d'une avance."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section 5.3",
        "verified": True,
    },
    {
        "id": "regime-synthetique-dates",
        "keywords": ["regime synthetique", "date exemption", "import export dispense"],
        "question_type": "Quelles sont les dates precises d'exemption pour le regime de l'impot synthetique ?",
        "answer": (
            "Les contribuables au regime de l'impot synthetique ont "
            "beneficie d'une exemption temporaire du 30 septembre 2021 "
            "au 1er fevrier 2023 - apres cette date, ils doivent delivrer "
            "la facture certifiee. Les importateurs/exportateurs sous ce "
            "regime sont exclus de cette dispense des le debut. "
            "Attention : une entreprise immatriculee sous la profession "
            "'IMPORT EXPORT' sans reellement importer ni exporter sera "
            "automatiquement exclue de la derogation - le bon choix "
            "d'activite est donc essentiel."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section 7.2 ; Circulaire 00024 du 22 fevrier 2023",
        "verified": True,
    },
    {
        "id": "elements-securite-facture",
        "keywords": ["qr code facture", "code secef", "elements de securite"],
        "question_type": "Quels elements de securite figurent sur une facture certifiee ?",
        "answer": (
            "Une facture certifiee comporte un code SECeF (identifiant "
            "unique attribue a chaque facture) et un QR code contenant "
            "des donnees essentielles : le NIF, la signature "
            "electronique, la date, et le numero de la machine ou du "
            "systeme ayant genere la facture."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 3, section 6.4",
        "verified": True,
    },
    {
        "id": "difference-sfe-mcf-uf",
        "keywords": ["difference sfe mcf uf", "c'est quoi sfe", "c'est quoi mcf", "c'est quoi uf"],
        "question_type": "Quelle est la difference entre SFE, MCF et UF ?",
        "answer": (
            "Le SFE (Systeme de Facturation Electronique) est le "
            "logiciel qui genere les factures. Le MCF (Module de "
            "Controle de Facturation) est la machine qui securise et "
            "transmet les donnees a la DGI. Quand les deux sont reunis "
            "dans une seule machine, on parle d'Unite de Facturation "
            "(UF)."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 4, section I",
        "verified": True,
    },
    {
        "id": "materialise-vs-dematerialise",
        "keywords": ["materialise ou dematerialise", "difference secef version", "quelle version choisir"],
        "question_type": "Quelle est la difference entre SECeF materialise et dematerialise ?",
        "answer": (
            "Le SECeF materialise repose sur des equipements physiques "
            "(MCF/SFE), fonctionne via le reseau GSM, et est accessible "
            "sans connexion internet classique. Le SECeF dematerialise "
            "(e-SECeF) est base sur une plateforme numerique en ligne et "
            "necessite une connexion internet active."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 4, section II",
        "verified": True,
    },
    {
        "id": "modes-deploiement",
        "keywords": ["mode de deploiement", "connexion directe reseau cloud", "quel mode choisir"],
        "question_type": "Quels modes de deploiement choisir selon la taille de l'entreprise ?",
        "answer": (
            "3 modes existent. La connexion directe (poste individuel "
            "relie au MCF, sans reseau) convient aux petites entreprises "
            "a faible volume, cout reduit. Le reseau local (plusieurs "
            "postes connectes a un serveur) convient aux entreprises "
            "moyennes avec plusieurs points de vente. Le cloud "
            "(hebergement distant via internet) convient aux grandes "
            "entreprises avec plusieurs succursales, plus flexible mais "
            "necessite une connexion stable."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 4, section VIII.4",
        "verified": True,
    },
    {
        "id": "arf",
        "keywords": ["arf", "attestation de regularite fiscale", "c'est quoi l'arf"],
        "question_type": "Qu'est-ce que l'ARF, et pourquoi le SECeF est-il necessaire pour l'obtenir ?",
        "answer": (
            "L'ARF (Attestation de Regularite Fiscale) est un document "
            "obligatoire pour de nombreuses demarches : marche public, "
            "agrement, concours bancaire, operations avec le Tresor "
            "public, transaction douaniere, titres miniers, ou meme une "
            "candidature elective. Son obtention repose sur la "
            "conformite fiscale du contribuable, notamment l'utilisation "
            "du SECeF."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 6, section 3.3 ; Art. 45 et 356 du CGI",
        "verified": True,
    },
    {
        "id": "exemption-precompte-isb",
        "keywords": ["precompte isb", "exemption acheteur", "precompte impot benefices"],
        "question_type": "L'acheteur est-il exempte du precompte ISB avec un SECeF ?",
        "answer": (
            "Oui. L'acheteur disposant d'un certificat de conformite au "
            "SECeF est exempte du paiement du precompte de l'Impot sur "
            "les Benefices (ISB). En attendant la definition complete "
            "des conditions de delivrance de ce certificat, il doit "
            "fournir une copie des documents prouvant l'acquisition et "
            "l'activation de son SECeF au grossiste ou industriel."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 6, section 3.1 ; Art. 38 bis du CGI",
        "verified": True,
    },
    {
        "id": "facture-non-certifiee-tribunal",
        "keywords": ["facture non certifiee tribunal", "preuve devant la justice", "valeur juridique facture"],
        "question_type": "Une facture non certifiee tient-elle devant un tribunal ?",
        "answer": (
            "Non, ou en tout cas difficilement. Les tribunaux "
            "reconnaissent la facture certifiee comme une preuve solide "
            "et incontestable dans les litiges commerciaux et fiscaux. "
            "Un jugement de 2024 du tribunal de commerce du Niger a "
            "refuse de reconnaitre des creances basees sur des factures "
            "non certifiees."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 6, section 2",
        "verified": True,
    },
    {
        "id": "cessation-activite",
        "keywords": ["cessation activite", "fermer mon entreprise", "desactiver secef", "arret entreprise"],
        "question_type": "Que faire du SECeF en cas de cessation d'activite ?",
        "answer": (
            "En cas de fermeture ou de cessation d'entreprise, de mise "
            "hors d'usage du SECeF ou d'arret pour toute autre raison, "
            "vous devez engager une procedure de desactivation dans un "
            "delai de sept (7) jours ouvrables. Le SECeF desactive doit "
            "ensuite etre conserve pendant quatre (4) ans."
        ),
        "source": "Art. 5 (point p) de l'Arrete 00474 du 20 novembre 2020",
        "verified": True,
    },
    {
        "id": "dossier-certification-machine",
        "keywords": ["dossier de certification", "documents pour certifier", "demande de certification machine"],
        "question_type": "Quels documents fournir pour faire certifier sa propre machine ?",
        "answer": (
            "Le dossier de demande de certification, adresse au "
            "Directeur General des Impots, doit comprendre : un "
            "formulaire de demande dument rempli, une copie de l'extrait "
            "du Registre de Commerce et du Credit Mobilier, une copie de "
            "la carte d'importateur ou d'une carte professionnelle en "
            "cours de validite, une attestation de regularite fiscale en "
            "cours de validite, et tout autre document specifie par note "
            "circulaire de la DGI."
        ),
        "source": "Art. 8 de l'Arrete 00473 du 20 novembre 2020",
        "verified": True,
    },
    {
        "id": "definition-e-secef",
        "keywords": ["c'est quoi le e-secef", "definition e-secef", "e-sfe e-mcf"],
        "question_type": "Qu'est-ce que le e-SECeF, et quels sont ses composants ?",
        "answer": (
            "Le e-SECeF est une application dematerialisee permettant "
            "d'emettre et de certifier des factures en ligne. Il est "
            "compose de deux elements : le e-SFE (application de "
            "facturation en ligne fournie par la DGI) et le e-MCF "
            "(module de controle virtuel). Contrairement au SECeF "
            "materialise qui utilise le reseau GSM, le e-SECeF "
            "fonctionne via internet. Il a ete lance en fevrier 2023."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 5, section II",
        "verified": True,
    },
    {
        "id": "calendrier-e-secef",
        "keywords": ["calendrier e-secef", "dates deploiement e-secef", "quand e-secef obligatoire"],
        "question_type": "Quel est le calendrier de deploiement progressif du e-SECeF ?",
        "answer": (
            "Le e-SECeF a ete deploye progressivement en 2023 : 1er "
            "fevrier - contribuables au regime de l'impot synthetique et "
            "PME sans SFE homologue, 1er avril - contribuables disposant "
            "d'un SFE homologue ou auto-declare, 1er juin - prestataires "
            "de services, 1er septembre - tous les contribuables sans "
            "distinction."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 5, section III",
        "verified": True,
    },
    {
        "id": "conditions-inscription-e-secef",
        "keywords": ["conditions e-secef", "s'inscrire au e-secef", "comment adherer e-secef"],
        "question_type": "Quelles sont les conditions et la procedure d'inscription au e-SECeF ?",
        "answer": (
            "Pour utiliser le e-SECeF, il faut disposer d'un Numero "
            "d'Identification Fiscale (NIF), d'une adresse email valide "
            "et d'une connexion internet active, ainsi que d'un "
            "smartphone, d'une tablette ou d'un ordinateur. L'inscription "
            "peut se faire en ligne ou directement dans un service "
            "operationnel de la DGI."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 5, sections III-IV",
        "verified": True,
    },
    {
        "id": "conservation-e-secef",
        "keywords": ["conservation e-secef", "combien de temps garder facture e-secef", "format facture e-secef", "pdf a4"],
        "question_type": "Combien de temps conserver les factures e-SECeF, et sous quel format ?",
        "answer": (
            "Les factures emises via le e-SECeF doivent etre conservees "
            "pendant au moins dix (10) ans, fournies en format PDF avec "
            "des dimensions A4 ou A8. C'est different du SECeF physique, "
            "dont les factures papier thermique doivent rester lisibles "
            "pendant au moins 4 ans - verifiez donc bien quelle version "
            "vous utilisez."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 5, section V",
        "verified": True,
    },
    {
        "id": "reclassement-entreprises",
        "keywords": ["reclassement entreprise", "changer de categorie entreprise", "micro petite moyenne grande"],
        "question_type": "Comment le e-SECeF aide-t-il au reclassement des entreprises ?",
        "answer": (
            "Grace a la collecte de donnees fiscales fiables, le "
            "e-SECeF permet de suivre l'evolution du chiffre d'affaires "
            "d'une entreprise et de la reclasser automatiquement : de "
            "micro a petite entreprise, de petite a moyenne, et de "
            "moyenne a grande entreprise."
        ),
        "source": "Comprendre la Facture Certifiee (M. Abdoulaye), chap. 5, section VII",
        "verified": True,
    },
]

SUGGESTIONS = [
    "Qui est concerne par la facture certifiee ?",
    "Quelles sont les sanctions en cas de non-respect ?",
    "Quel est l'impact sur la TVA si la facture n'est pas certifiee ?",
    "J'ai deja un systeme de facturation interne, dois-je le changer ?",
]
