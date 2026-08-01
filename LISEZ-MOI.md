# Fisca AI — Guide de mise en ligne (depuis un téléphone, sans ordinateur)

Ce projet peut être mis en ligne gratuitement, entièrement depuis le
navigateur de ton téléphone, en deux étapes : GitHub (pour héberger le
code) puis Render (pour le faire tourner et te donner un vrai lien web).

## Étape 1 — Créer un compte GitHub

1. Va sur **github.com** dans ton navigateur mobile
2. Crée un compte gratuit (email + mot de passe)
3. Une fois connecté, appuie sur le **+** en haut, puis **New repository**
4. Nomme-le `fisca-ai` (ou ce que tu veux), laisse-le **Public** ou
   **Private** selon ta préférence, puis **Create repository**

## Étape 2 — Envoyer les fichiers sur GitHub

1. Dans ton nouveau dépôt, appuie sur **Add file** → **Upload files**
2. Depuis ton gestionnaire de fichiers téléphone, sélectionne TOUS les
   fichiers de ce dossier `fisca-ai-backend` (app.py, engine.py,
   cache_data.py, requirements.txt, .gitignore, LISEZ-MOI.md)
3. Fais la même chose pour le contenu du dossier `static` : crée un
   fichier nommé `static/index.html` (GitHub accepte que tu tapes le
   chemin complet dans le nom du fichier au moment de l'upload) et
   colle-y le contenu si l'upload direct du sous-dossier ne fonctionne pas
4. Valide avec **Commit changes**

Astuce : si l'upload de dossier ne marche pas bien sur mobile, tu peux
utiliser l'appli officielle **GitHub Mobile** (disponible sur Play
Store), qui gère un peu mieux les dossiers que le site web.

## Étape 3 — Créer un compte Render et connecter GitHub

1. Va sur **render.com**, crée un compte gratuit (tu peux te connecter
   directement avec ton compte GitHub, c'est le plus simple)
2. Une fois connecté, appuie sur **New** → **Web Service**
3. Choisis ton dépôt `fisca-ai` dans la liste (Render te demandera
   d'autoriser l'accès à GitHub la première fois)

## Étape 4 — Configurer le service

Render va te proposer des champs à remplir :

- **Name** : `fisca-ai` (ou ce que tu veux — ça fera partie de ton lien)
- **Runtime** : Python 3
- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `python app.py`
- **Instance Type** : Free

Avant de lancer, va dans **Environment** (ou **Advanced**) et ajoute une
variable d'environnement :
- **Key** : `FISCA_AI_SECRET`
- **Value** : n'importe quelle longue suite de caractères aléatoires
  (tape ce que tu veux, ex. `niamey2026fiscatimessecretkey`)

Cette clé garde tes utilisateurs connectés même si le serveur redémarre.
Sans elle, tout le monde serait déconnecté à chaque redémarrage.

Appuie sur **Create Web Service**. Render installe et lance le projet
automatiquement (2-3 minutes la première fois).

## Étape 5 — Ton lien est prêt

Une fois le déploiement terminé, Render t'affiche une adresse du type :
`https://fisca-ai.onrender.com`

C'est ce lien que tu peux ouvrir depuis n'importe quel téléphone,
partager à des testeurs, etc.

## Limites à connaître pour cette phase test

- **Plan gratuit Render** : le service "s'endort" après 15 minutes sans
  visite, et met 30-60 secondes à se réveiller à la prochaine visite.
  Normal pour un test, gênant pour un vrai lancement — on passera à un
  plan payant (quelques dollars/mois) le jour où tu es prêt à annoncer
  publiquement.
- **Base de données** : sur le plan gratuit, les comptes et l'historique
  peuvent être effacés à chaque redéploiement du code. Pour une vraie
  mise en production, il faudra une base de données externe persistante
  (Render en propose une, payante après un certain quota).
- **Pas encore connecté à l'API OpenAI** — le moteur reste celui de
  `cache_data.py`, à compléter au fur et à mesure.

## Comment mettre à jour le contenu (questions/réponses) après coup

1. Depuis le site GitHub sur ton téléphone, ouvre `cache_data.py` dans
   ton dépôt
2. Appuie sur l'icône crayon (modifier)
3. Change le contenu, puis **Commit changes**
4. Render redéploie automatiquement le site avec le nouveau contenu en
   quelques minutes — rien d'autre à faire

## Rappel : lancer en local (si un jour tu as accès à un ordinateur)

```
pip install -r requirements.txt
python app.py
```
Puis ouvrir http://127.0.0.1:5000


## Comment ajouter une nouvelle question/réponse

Ouvre `cache_data.py`. Chaque question est un bloc comme celui-ci :

```python
{
    "id": "qui-concerne",
    "keywords": ["qui", "concerne", "beneficiaire"],
    "question_type": "Qui est concerne par la facture certifiee ?",
    "answer": "Ta reponse ici...",
    "source": "D'ou vient cette information",
    "verified": False,   # mets True quand tu as confirme avec le vrai texte
},
```

Copie un bloc, change le contenu, sauvegarde, relance `python app.py`.
Les `keywords` sont les mots qui doivent apparaître dans la question pour
que Fisca AI reconnaisse de quoi on parle — mets plusieurs variantes.

## Ce qui est déjà fonctionnel

- Création de compte et connexion (nom, contact, mot de passe)
- Quota de 10 questions par jour et par utilisateur (bloque au-delà)
- Le moteur comprend les fautes de frappe et les mots proches
- Historique de chaque question enregistré en base de données
- Boutons "utile" / "signaler une erreur" enregistrés aussi
- Étiquette "Contenu non vérifié" affichée automatiquement sur les
  réponses marquées `verified: False` — pour ne jamais présenter une
  info à confirmer comme une certitude

## Ce qui n'est PAS encore fait (volontairement, pour rester simple)

- Pas encore connecté à l'API OpenAI (le "vrai" moteur intelligent) —
  ce moteur local sert à tester le concept avant d'engager les frais
- Pas de mise en ligne sur internet — ça reste sur ton ordinateur
- Pas d'upload de PDF par l'utilisateur (comme prévu, désactivé en V1)
- Pas de paiement/abonnement réel

## Prochaine étape suggérée

Une fois que tu as testé et que le contenu de `cache_data.py` te
convient, l'étape suivante est soit :
1. Compléter les questions/réponses avec ton vrai livre, soit
2. Passer à la mise en ligne (hébergement + nom de domaine), soit
3. Brancher le vrai moteur OpenAI à la place du moteur local
