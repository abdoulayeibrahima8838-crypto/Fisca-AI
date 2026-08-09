# Security.md — Fisca AI

Ce document liste les règles de sécurité déjà appliquées au projet, pour
qu'elles soient systématiquement respectées dans tout nouveau code ajouté
par la suite — que ce soit par Claude ou lors d'une future retouche.

## 1. Secrets et clés API

- **Jamais** de clé, token ou mot de passe écrit en dur dans le code.
- Toujours via `os.environ.get("NOM_VARIABLE")`.
- Variables actuellement utilisées : `GEMINI_API_KEY`, `OPENAI_API_KEY`,
  `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`, `ADMIN_PASSWORD`,
  `FISCA_AI_SECRET`, `DATABASE_URL`, `COMPTES_ILLIMITES`.
- Si une variable obligatoire manque, le serveur doit soit refuser de
  démarrer avec un message clair, soit fonctionner en mode dégradé avec
  un avertissement explicite dans les logs (jamais d'échec silencieux).

## 2. Validation côté serveur

- Toute donnée reçue d'un formulaire ou d'une API externe doit être
  validée **côté serveur**, même si elle est déjà validée côté client
  (JavaScript) — le client peut toujours être contourné.
- Toujours vérifier : présence du champ, longueur minimale ET maximale,
  format attendu (email/téléphone, nombre, etc.).

## 3. Longueurs maximales

- Tout champ texte libre doit avoir une limite haute, même généreuse :
  - Question posée à l'IA : 500 caractères (`LONGUEUR_MAX_QUESTION`)
  - Nom d'utilisateur : 100 caractères (`LONGUEUR_MAX_NOM`)
- Objectif : éviter qu'un texte démesuré ne fasse exploser le coût d'un
  appel IA ou ne surcharge la base de données.

## 4. Rate limiting (limite de fréquence)

- Toute route qui déclenche une action coûteuse (appel IA, création de
  compte, envoi de message) doit être protégée par une limite de
  fréquence, **en plus** d'un éventuel quota métier journalier — un
  quota journalier limite le total, pas le rythme d'envoi.
- Limites actuelles :
  - `/api/question` : 10 requêtes/minute par adresse IP
  - `/api/inscription` : 5 créations de compte/heure par adresse IP
  - Connexion et réinitialisation de mot de passe : déjà protégées
    (voir section 6)

## 5. Messages d'erreur

- Ne jamais révéler d'information technique interne (stack trace,
  requête SQL, chemin de fichier) dans une réponse d'erreur visible par
  l'utilisateur.
- Pour tout ce qui touche à l'authentification, rester générique :
  - "Contact ou mot de passe incorrect" — jamais préciser lequel des
    deux est faux.
  - La réinitialisation de mot de passe répond toujours "ok", que le
    contact existe ou non — ne jamais révéler quels comptes existent.

## 6. Protection anti-brute-force

- Toute route d'authentification (connexion, réinitialisation) doit
  bloquer après un nombre défini de tentatives échouées, sur une
  fenêtre de temps donnée.
- Actuellement : 5 tentatives / 15 minutes, par contact concerné.

## 7. Affichage et anti-XSS

- Le contenu généré par un utilisateur (question, nom, réponse de l'IA)
  ne doit **jamais** être inséré dans une page HTML via `innerHTML` côté
  navigateur — toujours `textContent`.
- Toute page générée côté serveur qui affiche du contenu utilisateur
  (ex. `/admin`) doit systématiquement échapper `&`, `<`, `>`, `"`, `'`
  avant insertion dans le HTML.

## 8. Webhooks externes (Meta / WhatsApp)

- Toute requête reçue sur `/webhook/whatsapp` doit être vérifiée via la
  signature `X-Hub-Signature-256`, calculée avec `WHATSAPP_APP_SECRET`
  — jamais traiter une requête non signée comme fiable en production.
- La route de vérification (`GET`, utilisée une seule fois par Meta)
  reste séparée de la route de réception des messages (`POST`).

## 9. Cookies et sessions

- `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY` et
  `SESSION_COOKIE_SAMESITE` doivent rester activés — ne jamais les
  désactiver, même temporairement pour déboguer.

## 10. Avant tout déploiement

Checklist rapide à vérifier mentalement avant de livrer une nouvelle
route ou un nouveau formulaire :

- [ ] Les entrées sont validées côté serveur (présence, longueur, format)
- [ ] Une limite de fréquence est en place si l'action a un coût
- [ ] Les messages d'erreur restent génériques
- [ ] Aucune clé ou secret n'apparaît en clair dans le code
- [ ] L'affichage du contenu utilisateur passe par `textContent` ou un
      échappement HTML explicite
