# BookJob × Stages Marrakech

Le design BookJob (React) branché sur le backend de l'app Streamlit « Stages Marrakech » (FastAPI + pandas).
Les 374 entreprises du fichier Google Maps nettoyé remplacent les offres de démonstration.

## Lancer (Windows)
Double-cliquez `start.bat` → http://localhost:8000
(Linux/Mac : `./start.sh`). Python 3.10+ et Node.js/npm requis. Les scripts installent les dépendances manquantes, compilent l'interface, puis lancent l'API.

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
python -m app.pipeline.run --source places --source excel  # combine plusieurs sources
```

- Données brutes (avant nettoyage) : `backend/data/donnees_brutes_places.xlsx` ; chaque nouvelle collecte Places est enregistrée dans `donnees_brutes_collecte_AAAAMMJJ_HHMM.xlsx`.
- Sortie : `backend/data/donnees_nettoyees_pipeline.xlsx` (feuilles « Données nettoyées », « Lignes exclues », « Rapport nettoyage », « Dictionnaire », « Journal collecte »). Le fichier de référence `donnees_nettoyees.xlsx` utilisé par l'application n'est jamais écrasé ; les identifiants `MRK-###` existants sont conservés.
- Une source en échec n'arrête pas les autres : le journal indique succès, partiel ou échec par source, et l'historique des exécutions est conservé dans `data/pipeline_runs.json`.
- La page Statistiques affiche la qualité des données (complétude, doublons, lignes exclues, problèmes et traitements, exécutions du pipeline) via `GET /api/data-quality`.
- LinkedIn n'est pas collecté automatiquement (conditions d'utilisation) : les offres trouvées sur LinkedIn s'ajoutent manuellement au suivi avec la source « LinkedIn ».

## Fonctions (Streamlit → BookJob)
| Streamlit | BookJob |
|---|---|
| Profil (13 champs, profil.json) | Page Profil (sections modifiables, complétion % masquée une fois à 100 %, compétences, photo de profil importée par l'utilisateur) |
| Opportunités (filtres secteur/priorité/quartier/score, recherche, « Ajouter au suivi ») | Rechercher : filtres, tri (score, matching, distance, note, avis), fiche détaillée, ajout au suivi |
| Carte & distance (Nominatim, GPS manuel, Haversine, distance max) | Carte & distance (Leaflet), adresse/GPS/ma position, filtre et tri par distance |
| Suivi des candidatures | Mes candidatures : Kanban + liste, filtres (statut, entreprise, source, période), détails, historique des changements, réponses e-mail associées et export CSV |
| Postuler (import CV, dossier cv_envoyes) | « Postuler » : CV importé (aussi enregistré dans la bibliothèque) ou choisi dans la bibliothèque, relance J+7 automatique, téléchargement |
| Candidature & CV (IA ou modèle, mailto) | CV Studio : CV + e-mail (IA ou modèle), lettre de motivation, 3 mises en page, impression PDF |
| Tableau de bord | Tableau de bord personnel et page Statistiques (périodes hebdomadaires, statuts, réponses et entreprises) |
| — (BookJob) | Favoris, petit chatbot IA flottant (contextuel), recherches enregistrées, notifications de relance, Paramètres |

Les fichiers de données restent compatibles : `backend/data/suivi.csv` et `profil.json` sont ceux de l'app Streamlit. Au premier compte créé, les données locales historiques sont copiées dans son espace privé. Les comptes suivants partent avec leur propre profil et leur propre suivi.

## IA (optionnelle)
Aucune clé n'est nécessaire (mode modèle). Pour activer l'IA, copiez `backend/.env.example` en `backend/.env` :
Groq (`GROQ_API_KEY`, modèle `openai/gpt-oss-120b`), Grok (`XAI_API_KEY`, modèle `grok-4.7`), Ollama en local (aucune clé), OmniRoute (`OMNIROUTE_BASE_URL` + `OMNIROUTE_API_KEY`) ou Anthropic (`ANTHROPIC_API_KEY`).
Pour Ollama, installez-le puis téléchargez un modèle dans un terminal :

```bash
ollama pull qwen2.5:3b
```

Copiez `backend/.env.example` en `backend/.env`. Gardez `OLLAMA_BASE_URL=http://localhost:11434` et choisissez dans `OLLAMA_MODEL` un modèle installé. Le serveur Ollama doit rester lancé pendant l'utilisation de BookJob. Les clés des fournisseurs cloud restent côté serveur. `GOOGLE_API_KEY` (optionnel) permet d'affiner les coordonnées des entreprises depuis Paramètres.

Pour utiliser Groq en local, créez une clé API dans [la console Groq](https://console.groq.com/keys), puis renseignez `GROQ_API_KEY` dans `backend/.env`. Groq utilise le modèle configuré par `GROQ_MODEL` (par défaut `openai/gpt-oss-120b`) et sera prioritaire sur les autres fournisseurs. Redémarrez le backend après modification. Ne partagez jamais la clé et ne la publiez pas sur GitHub ; l'API peut être soumise à des limites ou conditions d'usage Groq.

Pour utiliser Grok en local, créez une clé API dans [la console xAI](https://console.x.ai/), puis renseignez `XAI_API_KEY` dans `backend/.env`. Gardez `XAI_MODEL=grok-4.7`. Redémarrez le backend après modification ; Grok sera prioritaire sur OmniRoute, Ollama et Anthropic quand aucune clé Groq n'est configurée. Ne partagez pas cette clé et ne la publiez jamais sur GitHub. L'API xAI est payante selon l'usage et peut nécessiter des crédits sur le compte.

Pour le site hébergé, configurez `XAI_API_KEY` et `XAI_MODEL` dans les variables d'environnement privées du serveur. À défaut de clé Grok, BookJob peut utiliser OmniRoute (`OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`, `OMNIROUTE_MODEL`), Ollama local ou Anthropic. Ne publiez jamais vos clés API dans GitHub.

## Comptes, sessions et données personnelles
L'application affiche la connexion au démarrage. L'inscription demande le nom complet, l'adresse e-mail et un mot de passe ; le nom et l'e-mail sont préremplis dans le profil. Le mot de passe est haché et les données sont stockées dans un espace privé par utilisateur. Les cookies de session sont `HttpOnly`, invalidés côté serveur à la déconnexion et expirent après 8 heures. Seule la session du site est fermée lors de la déconnexion : les données du compte et l'autorisation Gmail sont conservées. Les routes API et Dash vérifient la session côté serveur.

Configurez `BOOKJOB_ENV=production` derrière HTTPS. L'authentification utilise `backend/data/auth.sqlite3` par défaut (ou le chemin `BOOKJOB_AUTH_DB`) et nécessite un volume privé persistant. La première inscription importe les données historiques locales dans le compte initial ; aucun jeton Gmail historique n'est copié. Chaque utilisateur connecte son propre Gmail. Les inscriptions publiques sont activées par défaut ; définissez `BOOKJOB_REGISTRATION_KEY` pour exiger une clé aux inscriptions suivantes. Ne placez pas la base d'authentification, les données utilisateur ou les CV dans un stockage public.

Pour lancer les tests backend : `cd backend && python -m pytest tests`.

### Connexion avec Google
Si `GOOGLE_OAUTH_CLIENT_ID` et `GOOGLE_OAUTH_CLIENT_SECRET` sont configurés, l'écran de connexion affiche « Continuer avec Google ». Ce flux demande seulement `openid email profile`, vérifie le paramètre `state` (cookie `HttpOnly`) et n'accepte que les adresses e-mail vérifiées par Google. Un compte BookJob existant avec la même adresse est réutilisé ; sinon un compte est créé (soumis à `BOOKJOB_REGISTRATION_KEY` si elle est définie et qu'un compte existe déjà). L'accès Gmail reste une autorisation distincte. Ajoute les scopes `openid`, `email` et `profile` à l'écran de consentement.

### Sécurité des secrets
`backend/.env` ne doit jamais être commité ni partagé (il est ignoré par `.gitignore`). Si ce fichier a été transmis dans une archive, régénère immédiatement les clés qu'il contient (secret client OAuth Google, clés IA, mot de passe d'application SMTP).

### Configuration OAuth Google (une fois par déploiement)
Dans Google Cloud Console, active l'API Gmail, crée un client OAuth de type « Application Web », configure l'écran de consentement et autorise les scopes `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.readonly` et `https://www.googleapis.com/auth/gmail.compose`. L'accès lecture est utilisé uniquement pour rechercher et lire les réponses de recrutement. BookJob crée un brouillon adressé à l'entreprise et ne l'envoie qu'après l'action de confirmation dans l'application ; il n'envoie pas les candidatures automatiquement. Ajoute l'URI de redirection exacte, par exemple `http://localhost:8000/api/google/callback` en local ou `https://ton-domaine/api/google/callback` en production. Configure `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` et `GOOGLE_OAUTH_REDIRECT_URI` dans l'environnement privé du backend. En mode « Testing », ajoute les comptes qui utiliseront l'application comme utilisateurs test.

L'utilisateur connecte ensuite son compte depuis la page Candidatures et autorise les scopes Google affichés. BookJob ne demande ni ne stocke son mot de passe Gmail ni un mot de passe d'application. Les jetons OAuth sont enregistrés dans le répertoire privé de chaque compte ; sur un hébergeur, le répertoire de données doit donc être un volume persistant et privé. Définis aussi `BOOKJOB_PUBLIC_URL` sur l'URL HTTPS publique du backend pour générer les liens de confirmation, et conserve `EMAIL_CONFIRMATIONS_FILE` sur un volume privé et persistant.

La page Candidatures affiche l'état de connexion et de lecture, permet de déclencher une synchronisation, et présente les e-mails ambigus pour association manuelle. Le worker vérifie périodiquement les nouveaux messages (toutes les 15 minutes). Les messages reconnus sans association fiable ne changent pas de statut automatiquement. La synchronisation et l'envoi nécessitent la configuration OAuth et l'autorisation Gmail de l'utilisateur sur les trois scopes. Si Gmail était déjà connecté avant l'ajout du scope de brouillon, reconnecte le compte pour renouveler l'autorisation. Un client OAuth en mode « Testing » peut nécessiter une nouvelle autorisation après sept jours. Pour un usage durable, configure le consentement Google en mode production et complète les étapes de vérification Google requises pour les scopes Gmail.

« Préparer ma candidature » n'envoie rien à l'entreprise. Renseigne le lien et colle le texte de l'offre pour obtenir un matching, puis relis le message et la lettre générés. Tu peux aussi importer la lettre finale en PDF/Word ; sinon, elle est jointe comme fichier texte. Après connexion Google, BookJob t'envoie une prévisualisation à ton Gmail avec le CV, la lettre, le destinataire, les informations d'entreprise disponibles, le contenu de l'offre et un matching explicable. Le CV n'est envoyé à l'entreprise qu'après clic volontaire sur le lien de confirmation dans cet e-mail. Le lien expire après 20 minutes et ne peut servir qu'une fois. Après succès Gmail, BookJob marque la candidature « CV envoyé » et planifie la relance.

## Honnêteté des données
- Les entreprises viennent d'un fichier de données Google Maps ; BookJob ne lance pas de scraping global en arrière-plan et les fiches n'ont souvent pas d'adresse e-mail.
- Quand une fiche contient un e-mail, BookJob le propose. Sinon, à l'ouverture de « Postuler », il cherche les adresses publiquement affichées sur le site officiel enregistré et indique la page source. Si le site ne fournit pas d'adresse, elle doit être saisie manuellement. Vérifie toujours l'adresse trouvée avant d'envoyer le CV.
- BookJob envoie des candidatures par e-mail à l'adresse vérifiée. Il ne soumet pas automatiquement de formulaires sur les sites d'emploi, LinkedIn ou les portails de recrutement, et une adresse publique ne garantit pas qu'elle soit celle du recruteur.
- Le matching est une correspondance textuelle indicative : il compte les compétences déclarées dans le profil qui sont explicitement citées dans l'offre fournie. Il ne mesure ni l'expérience réelle ni une probabilité d'embauche. Sans description d'offre, BookJob n'invente pas de score et signale la candidature spontanée.
- Positions sur la carte : niveau quartier (pas de GPS dans l'export), sauf géocodage Google activé.

## Tableau analytique Plotly Dash
Le tableau de bord React habituel reste disponible à l'accueil. Pour les graphiques interactifs Dash, ouvre « Ouvrir le tableau analytique interactif » ou va sur `/dash/`. Il affiche les candidatures suivies, les envois et entretiens, un graphique filtrable par statut, leur évolution mensuelle et les entreprises par secteur. Dash est servi par le backend FastAPI et utilise les mêmes données BookJob ; il est également protégé par la connexion BookJob si celle-ci est activée.

## Limites connues
La synchronisation des réponses est disponible uniquement avec Gmail ; Outlook n'est pas intégré. La synchronisation automatique nécessite une configuration OAuth valide, un accès Gmail autorisé et un serveur qui reste en fonctionnement. Les statistiques reflètent les candidatures et les messages effectivement enregistrés ; l'absence de réponse n'est jamais considérée comme un refus.
