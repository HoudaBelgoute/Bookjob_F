# Rapport final — branche `audit-ameliorations`

## Résumé
L'identité visuelle est conservée (mêmes composants et classes CSS). Les modifications portent sur la
sécurité, la reproductibilité des données (collecte → nettoyage → export), la mesure de la qualité,
la connexion avec Google et les tests.

## ⚠️ Action obligatoire : secrets
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
| `tests/test_google_login.py` | création de compte, liaison à un compte existant, `state` falsifié, code refusé, clé d'invitation, absence de configuration | **non exécuté** |
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
