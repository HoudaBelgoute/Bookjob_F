# État de livraison — BookJob

Ce point de situation complète l'audit historique ci-dessous et inclut les compléments fonctionnels de novembre 2026.

## Parcours et fonctionnalités livrés
- Inscription/connexion par compte, données privées par utilisateur dans Supabase/Postgres, synchronisation Gmail à autorisation séparée.
- Parcours entreprise : recherche ou recommandation du tableau de bord → fiche persistante `/entreprises/{id}` avec lien source Google Maps et fraîcheur explicitement inconnue → préparation/envoi → page « Mes candidatures ». Les recommandations ouvrent directement la fiche concernée, y compris après actualisation. Le fallback Vercel sert l'entrée React pour les routes profondes; les chemins `/api/*` sont réécrits vers FastAPI avant le catch-all frontend.
- Le tableau de bord et le suivi ne comptent comme candidatures envoyées que celles ayant un statut d'envoi/réponse et une date valide; brouillons, annulations, expirations et dates invalides sont exclus.
- L'indice profil/secteur mesure la part des compétences déclarées qui contiennent un mot-clé du secteur. Il n'analyse pas une annonce et ne prédit pas l'embauche. Le score de répertoire (/100) combine secteur, réputation lissée, visibilité et contactabilité; il n'est pas une mesure de recrutement.
- Les réponses Gmail distinguent maintenant refus, acceptation, entretien, demande de documents et demande de relance. Une mise à jour automatique exige un message daté et une association fiable; les extraits Gmail sont affichés dans l'espace privé et les autres cas restent à confirmer. Une absence de réponse ne devient pas un refus.
- Le pipeline existant sait importer Excel, Google Places et OpenStreetMap et interroger les annonces publiques autorisées décrites dans le README. Il ne valide pas périodiquement les faits de l'export Google Maps livré : sa date de collecte reste inconnue, et aucune activité de recrutement n'est inventée.
- Le tableau de bord permet de choisir un objectif hebdomadaire; sa progression ne compte que les candidatures envoyées datées de lundi à aujourd'hui. Les brouillons de relance J+7/J+14 ouvrent le logiciel de messagerie de l'utilisateur et ne sont jamais envoyés par ce bouton. L'envoi automatique J+7 existant reste désactivé par défaut et demande une activation explicite.
- Seul Groq est pris en charge pour l'IA distante. La clé personnelle est vérifiée puis chiffrée avec Fernet dans le stockage privé du compte; `BOOKJOB_AI_KEY_ENCRYPTION_KEY` est requise. Sans cette variable, l'enregistrement de clé est désactivé et BookJob peut utiliser la configuration serveur partagée.
- Le guide d'accueil décrit désormais tableau de bord, profil, entreprises, carte et candidatures; il peut être relancé depuis Paramètres.
- L'application n'a pas de compte partagé ni de mode démo prérempli : les comptes et données sont privés. Les documents d'audit existants servent de livrables d'examen; ils ne constituent pas une preuve de déploiement réel.

## Limites restantes
- **Enrichissement vérifié** : les connecteurs autorisés existants peuvent collecter des données fraîches sur demande, mais la base importée n'a ni horodatage par fiche ni mécanisme de revalidation; elle demeure présentée comme non vérifiée.
- Les intégrations Groq, Gmail/OAuth, Google Geocoding et le déploiement Vercel ne sont vérifiés que si les environnements de service correspondants sont configurés; aucune clé ni aucun compte privé n'a été inspecté.

## Vérification du complément (16 novembre 2026)
- Backend hors base : 53 tests réussis, dont chiffrement/priorité des clés Groq, objectifs hebdomadaires, stades J+7/J+14 et prudence de classification Gmail; compilation Python réussie.
- Frontend : `npm run test` (1 test), `npm run build` et `npm run lint` réussis.
- La suite complète a été tentée; les tests API/auth, Dash et synchronisation qui nécessitent Postgres échouent ou ne peuvent démarrer car `DATABASE_URL`/`TEST_DATABASE_URL` ne sont pas configurés dans cet environnement. Les nouvelles routes API n'ont donc pas été exercées contre Supabase. Gmail/OAuth, Groq et Vercel en production ne sont pas déclarés vérifiés.
- `npm run lint` signale deux avertissements préexistants dans `frontend/src/data/data.js` (regex préfixées à remplacer par `startsWith`).

## Commits de la reprise
- `0606f78` — clés IA personnelles chiffrées, objectif hebdomadaire, relances guidées J+7/J+14 et prudence Gmail renforcée.
- `3a9a961` — onboarding guidé et transparence sur les entreprises.
- `96f73ee` — matching explicable et provenance.
- `f722845` — parcours candidature/suivi, statistiques et fallback SPA.
- `f783183` — documentation IA alignée sur Groq uniquement et explications d'indice exactes.
- `3e79e07` — comptage fiable des candidatures, protection de l'export et accès direct aux fiches depuis le tableau de bord.

---

# Audit historique — branche `audit-ameliorations`

Le rapport ci-dessous décrit l'état au moment de l'audit initial. Les mentions « non exécuté » et l'ancien nom de branche sont historiques; voir l'état de livraison ci-dessus pour la validation la plus récente.

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
