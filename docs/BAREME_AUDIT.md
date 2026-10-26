# Audit BookJob au regard du barème officiel

Ce document reprend **uniquement les colonnes du barème officiel** (BACKEND, FRONTEND, TEST, RÉSULTAT).
Le barème ne précise pas de pondération : aucune note n'est attribuée ici. La colonne « Avancement % »
reste à remplir par l'évaluateur.

> **Tests** : les tests décrits ci-dessous ont été écrits mais **non exécutés** pendant cet audit
> (Python et Node bloqués par une stratégie de groupe sur le poste utilisé). Voir
> `docs/BOOKJOB_FINAL_REPORT.md` pour les commandes à lancer.

Légende du statut : ✅ couvert · 🟡 partiel · ❌ absent.

## 1. BACKEND

| Critère | État avant audit | Fichiers | Corrections / ajouts | Comment vérifier | Statut |
|---|---|---|---|---|---|
| Data Collection (sources) | Un seul fichier Excel déjà nettoyé ; aucun code de collecte dans le dépôt ; Excel brut ignoré par Git | `backend/data/donnees_brutes_places.xlsx`, `backend/app/pipeline/sources.py` | Connecteurs `ExcelSource` (import d'un export brut) et `GooglePlacesSource` (Places API New, pagination, clé via `GOOGLE_API_KEY`) ; une source en échec n'arrête pas les autres ; journal par source ; Excel brut versionné | `python -m app.pipeline.run --source excel` puis `--source places` (clé requise) ; `tests/test_pipeline.py` | ✅ (LinkedIn non automatisable, ajout manuel documenté) |
| Data Cleaning – liste des problèmes | Feuille « Rapport nettoyage » (14 problèmes) dans l'Excel, non visible dans l'app | `donnees_nettoyees.xlsx`, `pipeline/cleaning.py` | Le pipeline produit son propre rapport (problème, lignes concernées, traitement) ; affiché dans Statistiques via `/api/data-quality` | Page Statistiques → « Qualité des données » ; feuille « Rapport nettoyage » de `donnees_nettoyees_pipeline.xlsx` | ✅ |
| Data Cleaning – solutions | Règles appliquées hors dépôt, non reproductibles | `pipeline/cleaning.py` | Règles codées et testées : lignes sans nom, notes/avis invalides, doublons (cid puis nom+adresse, cumul des requêtes), ville hors Marrakech, catégories non employeuses, normalisation téléphone (+212), domaine et type de site, quartier, code postal, note lissée bayésienne, score et priorité A/B/C, identifiants `MRK-###` stables | `tests/test_pipeline.py` | ✅ (règles documentées ; les comptes exacts du fichier d'origine ne sont pas garantis identiques) |
| Data Exploring (KPIs) | KPI de candidatures (tableau de bord, Statistiques, Dash) ; KPI « entretiens » ne comptait pas les nouveaux statuts | `dash_dashboard.py`, `pages/Statistics.jsx` | KPI entretiens corrigé ; KPI données : lignes brutes, nettoyées, exclues, doublons, coordonnées exactes | Statistiques + `/dash/` | ✅ |
| Data Quality | Non mesurée dans l'application | `main.py` (`GET /api/data-quality`), `Statistics.jsx` | Complétude par champ, doublons d'ID, motifs d'exclusion, répartition des priorités, historique des exécutions | `test_data_quality_exposes_cleaning_report_and_completeness` | ✅ |
| Data Visualization – nombre de graphiques | Dash : 3 graphiques Plotly (statuts, évolution mensuelle, secteurs) ; Statistiques : barres par statut, résultats, etc. | `dash_dashboard.py`, `Statistics.jsx` | Ajout de 2 graphiques de qualité (complétude, priorités) | Ouvrir `/dash/` et Statistiques | ✅ |
| Data Visualization – interprétation | Peu de texte d'interprétation | `Statistics.jsx` | Libellés explicatifs sur la section qualité ; l'interprétation rédigée reste à compléter dans le rapport de projet | Relecture | 🟡 |
| Langage du backend | Python 3 / FastAPI / pandas | `backend/` | — | — | ✅ |
| Structure du projet (dossier racine) | Archives `app.zip`, `src.zip`, `.venv`, `node_modules` livrés dans le zip | racine, `.gitignore` | `.gitignore` complété ; dossier `docs/` ; module `pipeline/` séparé | Arborescence du dépôt | ✅ |

## 2. FRONTEND

| Critère | État avant audit | Fichiers | Corrections / ajouts | Comment vérifier | Statut |
|---|---|---|---|---|---|
| Intégration backend/frontend | API REST + proxy Vite ; deux appels `fetch` bruts contournaient la gestion 401 | `api.js`, `store/useStore.js` | Passage par le client `api` (`favorites`, `home`, `dataQuality`) | Se déconnecter dans un autre onglet → retour à l'écran de connexion | ✅ |
| Organisation des pages | 11 pages ; « Entreprises » et « Rechercher » redondantes | `Sidebar.jsx`, `pages/` | Non fusionnées (risque sans build possible) | — | 🟡 |
| Fonctionnalités de la plateforme | Recherche, carte, suivi Kanban, CV Studio, Gmail, IA, favoris | — | Connexion « Continuer avec Google », qualité des données, badge de la barre latérale corrigé | Parcours manuel | ✅ |
| Liste des entreprises | 374 entreprises, filtres secteur/priorité/quartier/score/distance ; pagination côté client (limite 500) | `SearchPage.jsx`, `main.py` | Pas de pagination serveur ni de filtres type d'offre/date/source (pas d'entité « offre ») | — | 🟡 |
| Liste des erreurs | Messages d'erreur en français dans les formulaires | `AuthGate.jsx`, `api.js` | Erreurs Google affichées (`erreur_google`) ; validation du profil (422) | Tests `test_profile_rejects_invalid_values`, `test_google_login.py` | ✅ |
| Gestion des erreurs | Le gestionnaire global renvoyait le texte de l'exception au client | `main.py` | Message générique côté client, trace complète dans les journaux serveur | Provoquer une erreur → réponse 500 sans détail interne | ✅ |

## 3. TEST

| Critère | État | Corrections / ajouts | Statut |
|---|---|---|---|
| Dépôt sur GitHub | Dépôt Git local présent (historique existant) ; poussée vers GitHub à faire par l'étudiant | Branche `audit-ameliorations` ; secrets jamais commités (vérifié dans l'historique) | 🟡 |
| Déploiement | Scripts `start.bat` / `start.sh` ; variables de production documentées | README : HTTPS, `BOOKJOB_ENV=production`, volume privé | 🟡 (aucun déploiement vérifié) |
| Testing | Tests pytest existants (API, auth, Gmail, IA, Dash) | Ajout : `test_pipeline.py`, `test_google_login.py`, 3 tests API (santé publique, qualité, validation profil) | 🟡 écrits, **non exécutés** |

## RÉSULTAT

| Avancement % | Remarques |
|---|---|
| *(à remplir par l'évaluateur)* | Voir `docs/BOOKJOB_AUDIT.md` (problèmes par sévérité) et `docs/BOOKJOB_FINAL_REPORT.md` (modifications et limites). |
