# Redirection du backend cloud Artisan vers l'API MySpresso

**Date** : 2026-05-19
**Auteur** : Francis (MySpresso)
**Statut** : En attente de validation

## 1. Contexte & objectif

Artisan v4.0.3 (logiciel desktop PyQt6 de torréfaction de café) communique avec le service cloud propriétaire `artisan.plus` pour récupérer le stock (cafés, blends, magasins) et le planning de torréfactions, et pour pousser les profils de roast. Cette communication est concentrée dans `src/plus/` (~13 000 lignes, 19 modules) avec une couche HTTP unique dans `src/plus/connection.py`.

Le présent fork **MySpresso Artisan** vise à remplacer cette dépendance par une API MySpresso interne, **sans toucher aux fonctionnalités métier** d'Artisan (canvas, profils, capteurs, PID, machines, designer, comparator, analyzer, énergie).

Critères de réussite :
- Le fork ne contacte plus `artisan.plus` (vérifiable par capture réseau).
- Toutes les fonctions cloud existantes (login pseudo-désactivé, stock, blend picker, planning, push roast, sync delta, lock schedule, notifications) restent opérationnelles contre la nouvelle API.
- Endpoint configurable sans recompilation (env var + UI).
- Aucune régression sur le reste de l'application.

## 2. Approche retenue

**Option A — Substitution par configuration** (sans introduction d'interface d'abstraction).

L'API MySpresso étant conçue pour être compatible wire-à-wire avec `artisan.plus`, nous changeons uniquement **l'adresse** à laquelle parle la couche HTTP existante. Aucune nouvelle abstraction n'est introduite. Les modules `plus/stock.py`, `plus/sync.py`, `plus/queue.py`, `plus/schedule.py`, `plus/connection.py` (couche HTTP), ainsi que toutes les TypedDicts (`Coffee`, `Blend`, `StockItem`, `ScheduledItem`) restent inchangés.

Rationale : YAGNI. Une couche d'abstraction (Protocol `CloudBackend` avec implémentations multiples) n'apporte aucun bénéfice tant qu'il n'y a qu'un seul backend cible. Si une divergence apparaît sur un endpoint particulier, on introduira un mini-adaptateur local dans le module concerné.

## 3. Architecture cible

```
┌─────────────────────────────────────────────────────┐
│  artisanlib/* (UI, canvas, profils, capteurs, PID)  │  INCHANGÉ
├─────────────────────────────────────────────────────┤
│  plus/stock.py | sync.py | queue.py | schedule.py   │  INCHANGÉ
│  plus/roast_properties consumers, notifications     │
├─────────────────────────────────────────────────────┤
│  plus/connection.py  (sendData / getData)           │  QUASI-INCHANGÉ
│      └─ authentify()                                │  → court-circuité (cf. §5)
├─────────────────────────────────────────────────────┤
│  plus/config.py                                     │  MODIFIÉ
│      └─ api_base_url résolu dynamiquement           │
│      └─ auth_enabled flag (False en v1)             │
└─────────────────────────────────────────────────────┘
                            │
                            ▼
                api.myspresso.com/v1   ← cible (configurable)
```

Surface d'impact (fichiers modifiés) :
- `src/plus/config.py` — résolution dynamique des URLs + flag `auth_enabled`.
- `src/plus/connection.py` — court-circuit du flow d'authentification quand `auth_enabled=False`.
- `src/plus/login.py` — dialog de login bypass quand `auth_enabled=False` (ou auto-validation).
- Préférences UI — nouvel onglet "Cloud" pour éditer l'URL (fichier à déterminer, probablement `artisanlib/preferences.py` ou équivalent).
- Libellés cosmétiques — chaînes "artisan.plus" → "MySpresso" dans login, menu, statut, tooltips.

## 4. Couche de configuration

### 4.1 Résolution de la base URL

`plus/config.py` aujourd'hui (lignes 44-55) :
```python
api_base_url = 'https://artisan.plus/api/v1'
auth_url = api_base_url + '/accounts/users/authenticate'
stock_url = api_base_url + '/acoffees'
roast_url = api_base_url + '/aroast'
lock_schedule_url = api_base_url + '/aschedule/lock'
notifications_url = api_base_url + '/notifications'
web_base_url = 'https://artisan.plus'
```

Après modification :
```python
def _resolve_api_base_url() -> str:
    # 1. Env var (dev, CI, override ponctuel)
    if env := os.environ.get('MYSPRESSO_API_URL'):
        return env.rstrip('/')
    # 2. QSettings (modifiable via UI Préférences)
    settings = QSettings()
    stored = settings.value('cloud/api_base_url', '', type=str)
    if stored:
        return stored.rstrip('/')
    # 3. Défaut compilé
    return 'http://localhost:8000/v1'  # dev local; sera changé en prod

api_base_url = _resolve_api_base_url()
web_base_url = _resolve_web_base_url()  # même logique avec MYSPRESSO_WEB_URL
auth_url = api_base_url + '/accounts/users/authenticate'
stock_url = api_base_url + '/acoffees'
roast_url = api_base_url + '/aroast'
lock_schedule_url = api_base_url + '/aschedule/lock'
notifications_url = api_base_url + '/notifications'
```

**Ordre de précédence** : env var > QSettings > défaut compilé.

### 4.2 Variables d'environnement supportées

| Variable | Rôle | Défaut |
|---|---|---|
| `MYSPRESSO_API_URL` | Base URL de l'API (sans trailing slash) | `http://localhost:8000/v1` |
| `MYSPRESSO_WEB_URL` | Base URL du dashboard web (pour liens UI) | `http://localhost:3000` |
| `MYSPRESSO_AUTH_ENABLED` | `"true"` / `"false"`. Active la vérification d'auth | `"false"` |

### 4.3 Clés QSettings

| Clé | Type | Description |
|---|---|---|
| `cloud/api_base_url` | str | Override de la base URL d'API |
| `cloud/web_base_url` | str | Override de l'URL web |
| `cloud/auth_enabled` | bool | Active le flow d'authentification |

### 4.4 Lecture au démarrage uniquement

`_resolve_api_base_url()` est appelée une fois à l'import de `config.py`. Le changement d'URL en runtime (via Préférences) **nécessite un redémarrage de l'application** — comportement documenté dans la UI. Pas de hot-reload : la complexité (invalider les caches sync/stock, fermer les connexions HTTP en cours) ne se justifie pas pour cet usage.

## 5. Authentification désactivée (v1)

L'API MySpresso v1 ne requiert pas d'authentification. Côté client, on court-circuite le flow existant **sans le supprimer** (réactivable par config quand l'auth sera implémentée côté backend).

### 5.1 Comportement quand `auth_enabled=False`

- `plus/connection.authentify()` : retourne immédiatement avec un token fictif (`token = "noauth"`) et un user fictif (`nickname = "local"`, `account_id = "noauth"`). Aucun appel HTTP n'est fait vers `auth_url`.
- `plus/login.Login` (dialog Qt) : **n'est pas affiché**. Le `controller.connect()` doit considérer l'utilisateur comme déjà loggé.
- Header `Authorization` : **omis** des requêtes sortantes (ou présent avec valeur `Bearer noauth` — peu importe, le backend l'ignore). On choisit "omis" pour propreté.
- Le statut UI affiche "Connected" sans étape de login.

### 5.2 Comportement quand `auth_enabled=True` (futur)

Flow existant inchangé : dialog login, POST auth, Bearer token, retry sur 401. Aucune modification de code requise pour ce mode.

### 5.3 Stockage de credentials

Le module `keyring` reste en place mais inutilisé tant que `auth_enabled=False`. Pas de purge des entrées keyring existantes (les utilisateurs n'auront pas migré depuis artisan.plus).

## 6. Modifications UI

### 6.1 Nouvel onglet "Cloud" dans Préférences

Champs :
- **API endpoint** (text, lecture/écriture `cloud/api_base_url`)
- **Web endpoint** (text, lecture/écriture `cloud/web_base_url`)
- **Reset to defaults** (bouton, efface les clés QSettings)
- Note d'aide : "Restart required after change."

### 6.2 Rebranding cosmétique

Recherche/remplacement contextuel des chaînes affichées :

| Avant | Après |
|---|---|
| "artisan.plus" | "MySpresso" |
| "Connect to artisan.plus" | "Connect to MySpresso" |
| Lien `register_url` | URL MySpresso (à fournir) |
| Lien `reset_passwd_url` | URL MySpresso (à fournir) |
| Icône statut plus | Icône MySpresso (à fournir, fallback : conserver l'existante) |

**Hors périmètre** : retraduire les 35 fichiers `.ts` de traduction. Les chaînes en français/anglais resteront mixtes "MySpresso" / "artisan.plus" jusqu'à la prochaine campagne de traduction. Les noms internes de variables (`plus_account`, `plus.connection`, etc.) restent inchangés.

## 7. Périmètre & non-objectifs

### Inclus
- Configuration de `api_base_url` et `web_base_url` (env + QSettings + défaut).
- Bypass de l'authentification quand `auth_enabled=False`.
- Onglet Préférences "Cloud".
- Rebranding cosmétique des chaînes UI principales (login, menu, statut).
- Tests d'intégration pointant vers l'API MySpresso locale.

### Exclus explicitement
- Aucune modification de `canvas.py`, `main.py` (sauf libellés), profils, capteurs, PID, machines, designer, comparator, analyzer, énergie.
- Pas de nouveau format de fichier, pas de migration `.alog`.
- Pas de réécriture de la queue persistante (`queue.py`), du cache shelve (`sync.py`), du worker thread, du PID, ni des modules hardware.
- Pas d'introduction d'interface `CloudBackend` ou similaire (YAGNI tant qu'un seul backend cible).
- Pas de retrait des modules `src/plus/*` — on garde la totalité, on change juste l'adresse.
- Pas de mise à jour des traductions `.ts/.qm`.
- Pas de packaging/distribution (PyInstaller, AppVeyor) — sera fait dans un work item séparé.

## 8. Plan de migration (étapes prévues)

1. Modifier `src/plus/config.py` : ajout `_resolve_api_base_url()`, `_resolve_web_base_url()`, flag `auth_enabled`. Commit isolé.
2. Modifier `src/plus/connection.py` : court-circuit `authentify()` quand `auth_enabled=False`. Omettre header Authorization. Commit isolé.
3. Modifier `src/plus/login.py` (ou son point d'invocation dans `controller.py`) : bypass du dialog quand `auth_enabled=False`. Commit isolé.
4. Ajouter l'onglet Préférences "Cloud" (fichier à identifier au moment de l'implémentation). Commit isolé.
5. Rebranding des chaînes UI principales. Commit isolé.
6. Tests d'intégration : un script qui lance Artisan en pointant vers `http://localhost:8000/v1` (l'API MySpresso devra tourner en parallèle) et exerce stock fetch, push roast, lock schedule, notifications. Commit isolé.

Chaque étape commitée séparément pour faciliter bisect en cas de régression.

## 9. Stratégie de test

### 9.1 Tests unitaires
- `test/unitary/test_config_resolution.py` (nouveau) : vérifie l'ordre env > QSettings > défaut, et le `auth_enabled` flag.
- `test/unitary/test_connection_noauth.py` (nouveau) : vérifie que `authentify()` retourne un token fictif sans appel HTTP quand `auth_enabled=False`, et que le header Authorization est omis.

### 9.2 Tests d'intégration (essentiellement manuels)
Artisan est une application GUI PyQt6, peu testable en headless sans Xvfb/pytest-qt avec offscreen — la suite existante ne couvre pratiquement pas la GUI (cf. analyse upstream). Les vérifications d'intégration seront donc majoritairement manuelles dans cette itération :
- Lancer un serveur HTTP mock minimal (Python `http.server` ou pytest-httpserver) répondant aux 5 endpoints attendus, OU pointer vers l'API MySpresso locale quand disponible.
- Lancer Artisan avec `MYSPRESSO_API_URL=http://localhost:<port>/v1` (et `MYSPRESSO_AUTH_ENABLED=false`).
- Vérifier manuellement : ouverture sans dialog de login, état "connected" affiché, fetch stock fonctionnel (liste cafés/blends visible), push roast après une session (vérifier requête côté serveur mock), schedule lock, notifications.
- Optionnel : un test pytest qui n'instancie pas la GUI mais appelle directement `plus.stock.fetch()`, `plus.queue.addRoast()`, etc. contre un `pytest-httpserver` (faisable sans QApplication via mocking ciblé).

### 9.3 Tests de non-régression
- Le test suite existant doit continuer à passer (`pytest src/test/`) — en particulier `test/sanity/` et `test/smoke/`. Aucune modification de leurs assertions.
- Linting et typage strict (`ruff check src/`, `mypy src/`, `pylint`) doivent rester verts — config dans `src/pyproject.toml`. Toute nouvelle fonction ajoutée doit être entièrement typée (`disallow_untyped_defs = true`).
- Lancer l'app en mode "no cloud" (Artisan supporte de tourner sans cloud activé, `controller.connect()` non déclenché) : vérifier qu'il n'y a aucune tentative d'accès réseau à `artisan.plus` ni à MySpresso.

## 10. Risques & limites connues

| Risque | Mitigation |
|---|---|
| Le backend MySpresso n'est pas encore prêt → impossible de tester en local | Démarrer l'implémentation en parallèle ; utiliser un serveur mock pour valider le client |
| Des chaînes "artisan.plus" oubliées subsistent dans des dialogs peu visibles | Grep exhaustif final + revue ; les chaînes traduites resteront un suivi séparé |
| `auth_enabled=False` masque une régression du flow d'auth qui réapparaîtra plus tard | Conserver les tests unitaires existants du flow d'auth ; les exécuter périodiquement même si le mode par défaut est désactivé |
| Le format `.alog` évolue côté upstream Artisan → mise à jour future complexe | Hors périmètre ; documenter dans un prochain RFC |
| L'icône statut "plus connected" reste l'icône artisan.plus historique | Acceptable pour v1 ; remplacement icône en backlog |
| Caches persistants (shelve `stock_cache`, `sync_cache`) peuvent contenir des données serveur artisan.plus historiques d'un utilisateur ayant migré | Documenter la procédure de purge des caches utilisateur ; non bloquant pour un fork from-scratch |

## 11. Décisions ouvertes (non bloquantes)

- URL par défaut compilée : `http://localhost:8000/v1` choisi pour le dev. À changer avant tout déploiement public/release.
- Liens `register_url` et `reset_passwd_url` : URLs MySpresso à fournir avant rebrand final.
- Onglet Préférences "Cloud" : emplacement précis dans le dialog Préférences existant — à arbitrer au moment de l'implémentation.
- Icône statut MySpresso : à fournir ou conserver l'existante.
