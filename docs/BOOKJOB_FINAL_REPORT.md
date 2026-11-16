# État actuel du projet — BookJob

Ce document décrit les fonctionnalités et validations présentes dans la branche actuelle. Les constats de l'audit initial sont conservés dans la section historique ci-dessous.

## Fonctionnalités
- Les utilisateurs peuvent créer un compte avec nom, adresse e-mail et mot de passe, sans clé d'inscription. La connexion Google est optionnelle; l'autorisation Gmail est distincte.
- Les données de compte et les candidatures sont privées par utilisateur et stockées dans Supabase/Postgres.
- Le répertoire local d'entreprises et les sources à la demande sont distincts : Google Places recherche des lieux et entreprises, Jooble fournit des offres d'emploi, et le pipeline documenté prend aussi en charge OpenStreetMap et les sources publiques autorisées.
- Les offres Jooble peuvent être consultées puis importées au suivi par sélection. Google Places est présenté comme une source d'entreprises, et son import persistant utilise uniquement le Place ID.
- Groq et Anthropic/Claude sont pris en charge pour les fonctions IA existantes. Les clés personnelles sont validées auprès du fournisseur, chiffrées avec Fernet et isolées par compte; elles ne sont pas renvoyées dans les réponses API. `BOOKJOB_API_KEY_ENCRYPTION_KEY` est requise pour enregistrer les clés personnelles. En son absence, leur enregistrement est désactivé; les clés serveur configurées ou les modèles locaux restent les solutions de repli prévues.
- Le frontend React/Vite et l'API FastAPI sont déclarés dans `vercel.json` comme services distincts. Les routes `/api/*` sont dirigées vers l'API et les autres chemins vers le frontend. Le cron défini appelle la route de synchronisation Gmail une fois par jour.
- Les indicateurs et scores sont des outils de classement internes, pas des prédictions d'embauche. La fraîcheur des données du répertoire local n'est pas connue par fiche.

## Configuration et limites
- La configuration serveur est décrite dans `backend/.env.example`. Les clés personnelles ne doivent pas être placées dans `.env` ou dans le dépôt.
- Gmail, Google OAuth, les fournisseurs IA, Google Places, Jooble et les tâches cron nécessitent les clés ou autorisations correspondantes. Le présent dépôt ne prouve pas qu'un déploiement tiers est configuré ou fonctionnel.
- Les tests qui nécessitent PostgreSQL doivent être exécutés avec une base de test dédiée via `TEST_DATABASE_URL`. Aucun test de cette branche n'utilise la base de production fournie ailleurs.
- L'API Vercel et ses deux services sont validés ici par inspection de la configuration et de son schéma; aucun déploiement Vercel n'est effectué ni revendiqué.
- Si `BOOKJOB_REGISTRATION_KEY` existe encore dans le projet Vercel, le code ne la lit plus; elle peut être retirée manuellement depuis les paramètres de l'environnement.

## Vérifications récentes
- Backend sans base : 65 tests réussis, 1 ignoré. Les tests nécessitant PostgreSQL ne sont pas validés dans cet environnement.
- Frontend : test ciblé, lint et build réussis. Le lint signale deux avertissements préexistants dans `frontend/src/data/data.js`.
- Les appels réels aux fournisseurs et le déploiement Vercel ne sont pas déclarés testés par cette validation locale.

---

# Audit historique — branche `audit-ameliorations`

Le rapport ci-dessous décrit l'état au moment de l'audit initial. Les mentions « non exécuté » et l'ancien nom de branche sont historiques; voir l'état de livraison ci-dessus pour la validation la plus récente.

## Résumé
L'identité visuelle est conservée (mêmes composants et classes CSS). Les modifications portent sur la
sécurité, la reproductibilité des données (collecte → nettoyage → export), la mesure de la qualité,
la connexion avec Google et les tests.

## Action requise concernant les secrets
Le zip reçu contenait `backend/.env` avec des clés réelles. Elles doivent être **régénérées** :
secret client OAuth (Google Cloud Console), clé Groq et toute autre clé ou mot de passe d'application
présent dans ce fichier. Le fichier n'a jamais été commité et reste ignoré par Git ; le zip livré ne le contient pas.

## Modifications

### Sécurité
- `main.py` : erreurs 500 génériques (détail uniquement dans les journaux) ; `postMessage` limité à l'origine du site ;
  validation stricte de `PUT /api/profile` ; `/api/health` public.

### Données
- `app/pipeline/sources.py` : connecteurs Excel et Google Places API (New), isolation des échecs par source.
- `app/pipeline/cleaning.py` : règles de nettoyage, déduplication, score, priorité, identifiants stables, rapport et dictionnaire.
- `app/pipeline/run.py` : CLI, export Excel multi-feuilles (`donnees_nettoyees_pipeline.xlsx`), historique `pipeline_runs.json`.
  Le fichier `donnees_nettoyees.xlsx` utilisé par l'application n'est jamais écrasé.
- `GET /api/data-quality` et section « Qualité des données » dans Statistiques.
- `backend/data/donnees_brutes_places.xlsx` (avant nettoyage) désormais versionné.

### Connexion avec Google
- `app/google_login.py`, `accounts.login_with_google`, routes `GET /api/auth/google` et branche « login » du callback.
- Bouton « Continuer avec Google » dans `AuthGate.jsx` (affiché seulement si OAuth est configuré) et affichage des erreurs.
- L'accès Gmail reste une autorisation séparée.

### Corrections fonctionnelles
- KPI entretiens (Dash), badge de la barre latérale, appels API centralisés dans le store.

### Documentation
- `README.md` (pipeline, connexion Google, sécurité des secrets, dépendances de test), `backend/.env.example`,
  `docs/BAREME_AUDIT.md`, `docs/BOOKJOB_AUDIT.md`.

## Tests
| Fichier | Contenu | Résultat |
|---|---|---|
| `tests/test_pipeline.py` | règles unitaires, nettoyage complet sur données synthétiques, isolation des échecs, connecteur Places simulé, export et historique, fichier brut réel | **non exécuté** |
| `tests/test_google_login.py` | création de compte sans clé d'inscription, liaison à un compte existant, `state` falsifié, code refusé, absence de configuration | **non exécuté** |
| `tests/test_api.py` (3 ajouts) | santé publique, qualité des données, validation du profil | **non exécuté** |
| Build frontend (`npm run build`) | — | **non exécuté** |

Raison : Python et Node sont bloqués par une stratégie de groupe sur le poste utilisé pour l'audit.
Aucun résultat de test n'est donc revendiqué. Pour les lancer :

```
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
cd ../frontend
npm install
npm run build
```

Si un test échoue, corriger avant fusion de la branche.

## Limites connues
- Le pipeline reproduit les règles documentées du nettoyage, pas nécessairement les comptes et scores exacts du fichier d'origine.
- LinkedIn n'est pas collecté automatiquement (conditions d'utilisation) : ajout manuel dans le suivi avec la source « LinkedIn ».
- Pas d'entité « offre d'emploi » : la recherche porte sur des entreprises ; pas de filtres type d'offre / date de publication.
- Pagination de la recherche côté client ; pages « Entreprises » et « Rechercher » non fusionnées ; pas de rôle administrateur.
- Limitation des tentatives de connexion en mémoire.
- Aucun déploiement n'a été vérifié.
