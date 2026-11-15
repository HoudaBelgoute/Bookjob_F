# BookJob × Stages Marrakech

Le design BookJob (React) branché sur le backend de l'app Streamlit « Stages Marrakech » (FastAPI + pandas).
Les 374 entreprises du fichier Google Maps nettoyé remplacent les offres de démonstration.

## Lancer (Windows)
Copiez `backend/.env.example` en `backend/.env` et renseignez au minimum `DATABASE_URL` (Supabase), puis double-cliquez `start.bat` → http://localhost:8000
(Linux/Mac : `./start.sh`). Python 3.10+ et Node.js/npm requis. Les scripts installent les dépendances manquantes, compilent l'interface, puis lancent l'API.

## Base de données : Supabase
1. Crée un projet sur https://supabase.com, puis **Connect → Transaction pooler** et copie l'URI (port 6543) dans `DATABASE_URL`.
2. Les tables sont créées automatiquement au premier accès. Tu peux aussi exécuter `backend/supabase/schema.sql` dans le SQL Editor.
3. Données d'une ancienne installation (SQLite `backend/data/auth.sqlite3` + `backend/data/users/`) :
   ```
   cd backend
   python -m scripts.migrate_local_to_supabase           # simulation
   python -m scripts.migrate_local_to_supabase --apply   # copie vers Supabase
   ```
   Une fois la migration vérifiée, ces fichiers locaux peuvent être supprimés.

## Déploiement Vercel
Le fichier `vercel.json` déclare deux services Vercel : `frontend` (Vite, build statique) et `backend` (FastAPI, `backend/app/main.py`). La règle publique `/api/*` arrive d'abord au backend; les autres chemins vont au frontend, dont le fallback interne vers `index.html` permet de recharger directement une route React comme `/entreprises/MRK-001`. La route `/api/dash/` reste servie par le backend.
1. Pousse le dépôt sur GitHub et importe-le dans Vercel (racine du projet = dossier contenant `vercel.json`, sans framework preset).
2. Dans **Settings → Environment Variables**, ajoute : `DATABASE_URL`, `BOOKJOB_ENV=production`, `BOOKJOB_PUBLIC_URL=https://<ton-domaine>`, `CRON_SECRET` (chaîne aléatoire), et selon les besoins `GROQ_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI=https://<ton-domaine>/api/google/callback`.
3. Déploie. Le cron Vercel appelle `/api/cron/email-sync` une fois par jour (plan Hobby) pour synchroniser Gmail ; augmente la fréquence dans `vercel.json` sur un plan Pro.

`.vercelignore` exclut les secrets (`.env`), les tests et toutes les données personnelles locales.

## Développement
```
cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev        # http://localhost:5173 (proxy /api → :8000)
cd frontend && npm run build                     # recompile dist
cd backend && python -m pytest tests             # tests API, pipeline, connexion Google et IA
```
Les dépendances de test sont dans `backend/requirements-dev.txt` (`pip install -r requirements-dev.txt`).

## Pipeline de données (collecte → nettoyage → export)
Le code se trouve dans `backend/app/pipeline/` (`sources.py`, `cleaning.py`, `run.py`).

```
cd backend
python -m app.pipeline.run --source excel                  # rejoue le nettoyage sur data/donnees_brutes_places.xlsx
python -m app.pipeline.run --source places                 # nouvelle collecte Google Places API (New), requiert GOOGLE_API_KEY
python -m app.pipeline.run --source osm                    # entreprises, recruteurs et formations (gratuit, sans clé)
python -m app.pipeline.run --source jobs                   # annonces publiques encore ouvertes à Marrakech (sans clé)
python -m app.pipeline.run --source places --source excel  # combine plusieurs sources
python -m app.pipeline.run --source osm --source excel     # enrichit l'export existant avec OpenStreetMap
python -m app.pipeline.run --source jobs --source osm --source excel --out data/donnees_nettoyees.xlsx
```

- Données brutes (avant nettoyage) : `backend/data/donnees_brutes_places.xlsx` ; chaque nouvelle collecte Places est enregistrée dans `donnees_brutes_collecte_AAAAMMJJ_HHMM.xlsx`.
- OpenStreetMap ajoute les entreprises, agences de recrutement et établissements d'enseignement/formation cartographiés à Marrakech. Cette source gratuite ne nécessite aucune clé API.
- La source `jobs` interroge le portail officiel Emploi Public, filtre les annonces avec date limite encore valide, et ajoute les offres retenues dans la feuille « Offres publiques actives ». Le nombre d'offres et d'établissements de formation est indiqué dans le résumé d'exécution.
- La source Google Places comprend davantage de secteurs et de recherches de centres de formation, mais reste facultative et peut nécessiter un compte Google Cloud avec facturation activée.
- Sortie par défaut : `backend/data/donnees_nettoyees_pipeline.xlsx`. Pour mettre à jour le classeur de l'application, passe `--out data/donnees_nettoyees.xlsx` depuis `backend`; les autres feuilles utilisateur (ex. « Suivi ») sont préservées et les identifiants `MRK-###` existants sont conservés.
- Une source en échec n'arrête pas les autres : le journal indique succès, partiel ou échec par source, et l'historique des exécutions est conservé dans `data/pipeline_runs.json`.
- Les annonces récoltées sont les concours publics actifs de Marrakech; les offres privées et les stages ne sont disponibles que si un fournisseur autorise leur collecte ou propose une API/flux public.
- Rekrute n'est pas récupéré automatiquement car son `robots.txt` interdit l'accès automatisé à ses pages d'offres; Emploi.ma bloque les requêtes de collecte directe. Le pipeline ne contourne ni ces restrictions ni leurs protections.
- La page Statistiques affiche la qualité des données (complétude, doublons, lignes exclues, problèmes et traitements, exécutions du pipeline) via `GET /api/data-quality`.
- LinkedIn n'est pas collecté automatiquement (conditions d'utilisation) : les offres trouvées sur LinkedIn s'ajoutent manuellement au suivi avec la source « LinkedIn ».

## Fonctions (Streamlit → BookJob)
| Streamlit | BookJob |
|---|---|
| Profil (13 champs, profil.json) | Page Profil (sections modifiables, complétion % masquée une fois à 100 %, compétences, photo de profil importée par l'utilisateur) |
| Opportunités (filtres secteur/priorité/quartier/score, recherche, « Ajouter au suivi ») | Rechercher : filtres, tri (score, matching, distance, note, avis), fiche détaillée, ajout au suivi |
| Carte & distance (Nominatim, GPS manuel, Haversine, distance max) | Carte & distance (Leaflet), adresse/GPS/ma position, filtre et tri par distance |
| Suivi des candidatures | Mes candidatures : Kanban + liste, filtres (statut, entreprise, source, période), détails, historique des changements, preuve détaillée des e-mails Gmail envoyés, réponses associées et export CSV |
| Postuler (import CV, dossier cv_envoyes) | « Postuler » : CV importé (aussi enregistré dans la bibliothèque) ou choisi dans la bibliothèque, relance J+7 automatique, téléchargement |
| Candidature & CV (IA ou modèle, mailto) | CV Studio : CV + e-mail (IA ou modèle), lettre de motivation, 3 mises en page, impression PDF |
| Tableau de bord | Résumé personnel avec accès à la page Statistiques centralisée (activité, statuts, réponses, entreprises et qualité des données) |
| — (BookJob) | Favoris, petit chatbot IA flottant (contextuel), recherches enregistrées, notifications de relance, Paramètres |

Les fichiers de données restent compatibles : `backend/data/suivi.csv` et `profil.json` sont ceux de l'app Streamlit. Au premier compte créé, les données locales historiques sont copiées dans son espace privé. Les comptes suivants partent avec leur propre profil et leur propre suivi.

## IA (optionnelle)
Sans clé, BookJob utilise des modèles locaux de génération et un assistant fondé sur les données disponibles. Le seul fournisseur IA distant actuellement intégré est Groq : configurez `GROQ_API_KEY` et, facultativement, `GROQ_MODEL` dans `backend/.env` en local ou dans les variables privées du serveur. La clé est partagée par l'application et reste côté serveur ; BookJob ne propose pas de stockage de clé IA personnelle par compte. Ne publiez jamais cette clé dans GitHub. `GOOGLE_API_KEY` est un réglage distinct, facultatif, pour affiner les coordonnées depuis Paramètres.

## Comptes, sessions et données personnelles
L'application affiche la connexion au démarrage. L'inscription demande le nom complet, l'adresse e-mail et un mot de passe ; le nom et l'e-mail sont préremplis dans le profil. Le mot de passe est haché et les données sont stockées dans un espace privé par utilisateur. Les cookies de session sont `HttpOnly`, invalidés côté serveur à la déconnexion et expirent après 8 heures. Seule la session du site est fermée lors de la déconnexion : les données du compte et l'autorisation Gmail sont conservées. Les routes API et Dash vérifient la session côté serveur.

Configurez `BOOKJOB_ENV=production` derrière HTTPS. Toutes les données (comptes, sessions, profil, suivi, favoris, CV, avatar, jetons Gmail, confirmations et historique des messages envoyés) sont stockées dans **Supabase (Postgres)** via `DATABASE_URL` ; aucun fichier n'est écrit sur le disque du serveur. Les fichiers privés sont dans la table `user_files` (RLS activée : inaccessibles par l'API publique Supabase). La première inscription importe les données historiques locales dans le compte initial. Chaque utilisateur connecte son propre Gmail. Les inscriptions publiques sont activées par défaut ; définissez `BOOKJOB_REGISTRATION_KEY` pour exiger une clé aux inscriptions suivantes.

Pour lancer les tests backend (ils écrivent dans la base : utilise un projet Supabase de test) : `cd backend && TEST_DATABASE_URL=... python -m pytest tests`.

### Connexion avec Google
Si `GOOGLE_OAUTH_CLIENT_ID` et `GOOGLE_OAUTH_CLIENT_SECRET` sont configurés, l'écran de connexion affiche « Continuer avec Google ». Ce flux demande seulement `openid email profile`, vérifie le paramètre `state` (cookie `HttpOnly`) et n'accepte que les adresses e-mail vérifiées par Google. Un compte BookJob existant avec la même adresse est réutilisé ; sinon un compte est créé (soumis à `BOOKJOB_REGISTRATION_KEY` si elle est définie et qu'un compte existe déjà). L'accès Gmail reste une autorisation distincte. Ajoute les scopes `openid`, `email` et `profile` à l'écran de consentement.

### Sécurité des secrets
`backend/.env` ne doit jamais être commité ni partagé (il est ignoré par `.gitignore`). Si ce fichier a été transmis dans une archive, régénère immédiatement les clés qu'il contient (secret client OAuth Google, clés IA, mot de passe d'application SMTP).

### Configuration OAuth Google (une fois par déploiement)
Dans Google Cloud Console, active l'API Gmail, crée un client OAuth de type « Application Web », configure l'écran de consentement et autorise les scopes `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.readonly` et `https://www.googleapis.com/auth/gmail.compose`. L'envoi utilise `gmail.send`; l'accès lecture est utilisé pour rechercher les réponses de recrutement. Après le clic explicite sur « Envoyer ma candidature », BookJob envoie le message et ses pièces jointes au recruteur via Gmail. L'application ne marque la candidature comme envoyée qu'après la réussite de l'appel Gmail. Ajoute l'URI de redirection exacte, par exemple `http://localhost:8000/api/google/callback` en local ou `https://ton-domaine/api/google/callback` en production. Configure `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` et `GOOGLE_OAUTH_REDIRECT_URI` dans l'environnement privé du backend. En mode « Testing », ajoute les comptes qui utiliseront l'application comme utilisateurs test.

L'utilisateur connecte ensuite son compte depuis la page Candidatures ou la fenêtre Postuler et autorise les scopes Google affichés. BookJob ne demande ni ne stocke son mot de passe Gmail ni un mot de passe d'application. Les jetons OAuth sont enregistrés dans l'espace privé Supabase de chaque compte.

La page Candidatures affiche l'état de connexion et de lecture, permet de déclencher une synchronisation, et présente les e-mails ambigus pour association manuelle. Le worker vérifie périodiquement les nouveaux messages (toutes les 15 minutes). Les messages reconnus sans association fiable ne changent pas de statut automatiquement. La synchronisation nécessite la configuration OAuth et l'autorisation Gmail de lecture. L'envoi d'une candidature nécessite l'autorisation Gmail `gmail.send`.

Les relances automatiques sont désactivées par défaut et doivent être activées dans la page Candidatures. Après activation, BookJob vérifie d'abord les nouveaux messages, puis envoie au plus une relance depuis le Gmail connecté après sept jours sans réponse, uniquement pour une candidature marquée « Candidature envoyée » et ayant une adresse de recruteur valide. Une réponse associée ou un autre statut empêche la relance. Les relances n'incluent pas de CV ni de pièce jointe. En cas d'échec d'envoi, BookJob ne réessaie pas automatiquement afin d'éviter les doublons; l'échec est indiqué dans la page Candidatures. L'envoi nécessite l'autorisation Gmail `gmail.send`; si Gmail était déjà connecté sans ce scope, reconnecte le compte pour renouveler l'autorisation. Un client OAuth en mode « Testing » peut nécessiter une nouvelle autorisation après sept jours. Pour un usage durable, configure le consentement Google en mode production et complète les étapes de vérification Google requises pour les scopes Gmail.

Avant l'envoi, vérifie le destinataire et le contenu du message dans la fenêtre Postuler. Après clic sur « Envoyer ma candidature », le message part directement du Gmail connecté avec le CV et la lettre sélectionnés. BookJob conserve dans l'historique de la candidature l'expéditeur, le destinataire, l'objet, le contenu, les noms des pièces jointes, la date et l'identifiant Gmail, avec un lien direct vers le message dans « Envoyés ». Le suivi détaillé est accessible depuis « Voir les détails et l'historique ». La confirmation atteste que Gmail a créé le message dans « Envoyés » ; elle ne garantit pas sa remise ou sa lecture par le destinataire. En cas d'échec ou d'autorisation manquante, une erreur est affichée et la candidature n'est pas marquée comme envoyée. L'envoi automatique des relances reste désactivé tant que tu ne l'actives pas dans la page Candidatures.

## Honnêteté des données
- Au premier accès, un guide présente le parcours profil → recherche d’entreprise → candidature et suivi. Son état est enregistré dans les réglages privés du compte et peut être ignoré.
- Les entreprises viennent d'un fichier de données Google Maps ; BookJob ne lance pas de scraping global en arrière-plan et les fiches n'ont souvent pas d'adresse e-mail.
- Le répertoire est un export fourni avec le projet ; aucune date de mise à jour par entreprise n'est disponible. Les coordonnées et évaluations reflètent cet export et ne sont pas garanties comme actuelles.
- Quand une fiche contient un e-mail, BookJob le propose. Sinon, à l'ouverture de « Postuler », il cherche les adresses publiquement affichées sur le site officiel enregistré et indique la page source. La recherche priorise les pages de contact indiquées par le site ; si aucune adresse n'est publiée (ou si l'entreprise n'a pas de site enregistré), l'adresse doit être vérifiée et saisie manuellement. BookJob ne devine jamais une adresse.
- BookJob envoie des candidatures par e-mail à l'adresse vérifiée. Le succès confirme que Gmail a créé le message dans « Envoyés », mais ne garantit pas que le serveur du destinataire l'a remis dans sa boîte ou qu'il l'a lu. Il ne soumet pas automatiquement de formulaires sur les sites d'emploi, LinkedIn ou les portails de recrutement, et une adresse publique ne garantit pas qu'elle soit celle du recruteur.
- L'indice des fiches entreprise est la part des compétences déclarées qui partagent un mot-clé du secteur; les détails montrent les compétences rapprochées et non rapprochées. Il ne tient pas compte d'une offre et ne représente pas une probabilité d'embauche. Pour une offre dont le texte est fourni, BookJob compare séparément les compétences déclarées aux termes explicitement présents. Sans description d'offre, aucun score d'offre n'est inventé.
- Le score du répertoire (/100) combine le secteur, une note Google lissée, la visibilité (nombre d'avis plafonné) et la contactabilité. C'est un classement interne des fiches, pas une mesure de recrutement ni une promesse de réponse.
- Positions sur la carte : niveau quartier (pas de GPS dans l'export), sauf géocodage Google activé.

## Statistiques
La page React « Statistiques » regroupe les indicateurs personnels de candidatures et le panorama de la base entreprises, dont les informations de qualité et de fraîcheur des données. Le tableau de bord d'accueil reste volontairement synthétique. L'ancien tableau Plotly Dash est conservé à `/api/dash/` pour compatibilité, mais ne constitue plus un parcours de navigation principal.

## Limites connues
La synchronisation des réponses est disponible uniquement avec Gmail ; Outlook n'est pas intégré. La synchronisation automatique nécessite une configuration OAuth valide et un accès Gmail autorisé ; sur Vercel elle passe par le cron `/api/cron/email-sync` (en local, un worker tourne toutes les 15 minutes). Les fichiers importés sont limités à 5 Mo (stockés dans Postgres). Les statistiques reflètent les candidatures et les messages effectivement enregistrés ; l'absence de réponse n'est jamais considérée comme un refus.
