# Audit technique BookJob

Périmètre : backend FastAPI (`backend/app`), frontend React (`frontend/src`), données (`backend/data`),
configuration et livrable zip. Chaque point indique son état après la branche `audit-ameliorations`.

## Critique

| # | Problème | Impact | État |
|---|---|---|---|
| C1 | `backend/.env` livré dans le zip avec de **vraies clés** (secret client OAuth Google, clé Groq, identifiants SMTP…) | Toute personne ayant le zip peut utiliser ces comptes | Fichier jamais commité (vérifié) et ignoré par Git. **Action requise : régénérer toutes les clés** et ne plus inclure `.env` dans les archives |
| C2 | Le gestionnaire d'exceptions global renvoyait `Erreur serveur : {ex}` | Fuite de détails internes (chemins, requêtes) | Corrigé : message générique, journalisation serveur |

## Élevée

| # | Problème | Impact | État |
|---|---|---|---|
| E1 | Page de résultat OAuth : `postMessage(..., "*")` | Un autre site ouvrant la fenêtre pouvait recevoir le message | Corrigé : origine `window.location.origin` |
| E2 | `PUT /api/profile` acceptait n'importe quel JSON | Données arbitraires/volumineuses stockées | Corrigé : clés autorisées, types simples, 5 000 caractères max (422 sinon) |
| E3 | Aucun code de collecte ni de nettoyage dans le dépôt ; Excel brut ignoré | Critères « Data Collection / Cleaning » non démontrables | Corrigé : `app/pipeline/` + Excel brut versionné |
| E4 | Pas de connexion Google pour le compte (seulement l'accès Gmail) | Fonction demandée absente | Ajoutée : OIDC `openid email profile`, `state` vérifié, e-mail vérifié requis, liaison au compte existant, respect de la clé d'invitation |

## Moyenne

| # | Problème | État |
|---|---|---|
| M1 | Initialisation du store : `fetch` bruts pour favoris/accueil (pas de gestion 401) | Corrigé |
| M2 | KPI « entretiens » du tableau Dash ignorait « Entretien programmé » / « Acceptée » | Corrigé |
| M3 | Badge de la barre latérale comptait toutes les candidatures (ancien statut « À contacter ») | Corrigé : statuts actifs uniquement |
| M4 | Limitation des tentatives de connexion en mémoire (perdue au redémarrage, non partagée entre processus) | Non modifié — documenté |
| M5 | Recherche : chargement de 500 entreprises et pagination côté client ; pas de filtres type d'offre / date / source | Non modifié — pas d'entité « offre » dans les données |
| M6 | Pages « Entreprises » et « Rechercher » redondantes | Non modifié (fusion sans build vérifiable jugée risquée) |
| M7 | Pas de rôle administrateur | Non modifié |
| M8 | Aucune mesure de la qualité des données dans l'application | Corrigé : `GET /api/data-quality` + section Statistiques |

## Faible

| # | Problème | État |
|---|---|---|
| F1 | Archives `backend/app.zip`, `frontend/src.zip`, `.venv`, `node_modules` dans le livrable | `.gitignore` complété ; zip de livraison nettoyé |
| F2 | `/api/health` exigeait une session | Rendu public (aucune donnée exposée) |
| F3 | `/api/reset/tracking` est destructif sans double confirmation côté serveur | Non modifié — à confirmer dans l'interface |
| F4 | Pas de mentions sur les données partagées par Google | Ajout d'un texte sous le bouton Google ; pages CGU / confidentialité à rédiger |

## Points vérifiés sans problème
- Mots de passe hachés PBKDF2-SHA256 (310 000 itérations, sel aléatoire), jetons de session stockés hachés, cookies `HttpOnly`/`SameSite=Lax`, `Secure` en production.
- Isolation par utilisateur : fichiers dans `data/users/<id>/` sélectionnés par le middleware à partir de la session.
- Envoi Gmail uniquement après confirmation explicite (lien unique, 20 minutes).
