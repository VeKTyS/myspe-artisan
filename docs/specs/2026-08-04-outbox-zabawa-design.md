# Outbox — envoi fiable des torréfactions vers ZABAWA.plus — Design

Date : 2026-08-04
Statut : validé en brainstorming
Dépôts : `myspe-artisan` (Zabawa Roast, desktop, branche `feat/artisan-4.2.0`) et
`myspe-artisan-analyser` (ZABAWA.plus, web + Edge Functions Supabase).
Concerne les deux sociétés (MySpresso et Esperanza) : le problème n'est pas
propre à l'une d'elles, il est dans le transport.

## Problème

Le desktop possède **deux voies d'envoi concurrentes** vers ZABAWA.plus :

| | Voie A — automatique | Voie B — manuelle |
|---|---|---|
| Déclencheur | DROP ([canvas.py:15585](../../src/artisanlib/canvas.py)) | action de menu « Envoyer » |
| Transport | `plus/queue.py` → `POST /v1/aroast` | `POST upload-roast` direct |
| Contenu | record de synthèse | `.alog` intégral |
| Écriture serveur | merge par clé présente | `strategy=overwrite`, ligne entière |

### Défauts de la voie A

1. **Perte définitive après trois tentatives.** `queue_retries = 2`
   ([config.py:182](../../src/plus/config.py)) et, à l'épuisement de `iters`,
   `queue.task_done()` est appelé **inconditionnellement**
   ([queue.py:257](../../src/plus/queue.py)) : l'item quitte la file même s'il
   n'est jamais parti. Aucun message à l'opérateur.
2. **Enfilement conditionné à une connexion active.**
   `if firstDROP and self.autoDROPenabled and self.aw.plus_account is not None` :
   connexion échouée au démarrage → `addRoast()` n'est jamais appelé, rien
   n'est même mis en file.
3. **La file s'arrête d'elle-même.** Sur erreur réseau,
   `controller.disconnect(stop_queue=True)` coupe le worker jusqu'à
   reconnexion.
4. **Mises à jour partielles jetées.** Un SAVE après DROP produit un record
   partiel : s'il n'est pas « full » et pas encore dans le cache de sync, il est
   consommé sans être envoyé ([queue.py:126-129](../../src/plus/queue.py)). La
   base garde la version du DROP → **données fausses**, pas seulement absentes.
5. **Purge silencieuse à trois jours** (`queue_discard_after`).

### Défauts communs aux deux voies

6. **Société jamais transmise.** Ni `entrepriseId` ni `createMissingBean` :
   `upload-roast` ne requalifie pas le code magasin en `CODE@slug` et n'appelle
   pas `resolveOrCreateBean()`. Le trigger retombe sur `FALLBACK_BEAN_ID`
   (« Grain inconnu ») et `FALLBACK_STORE_ID` (aucun décrément de stock).
7. **Les deux voies s'écrasent mutuellement.** `/v1/aroast` merge les clés
   présentes, `upload-roast?strategy=overwrite` réécrit toute la ligne avec des
   `null`. Selon l'ordre d'arrivée, l'une efface le travail de l'autre.
8. **Batch number optionnel.** `roastbatchnr` n'est attribué que si
   `batchcounter > -1` ET si la torréfaction passe par DROP
   ([canvas.py:15837](../../src/artisanlib/canvas.py)). Sans lui,
   `matchBy=batch_number` ne déduplique plus et l'adoption des fiches saisies à
   la main échoue.

## Solution — voie unique

**Une seule écriture serveur par torréfaction**, passant par une outbox
persistante côté desktop.

```
   Zabawa Roast (desktop)                     ZABAWA.plus (Edge Functions)
   ──────────────────────                     ───────────────────────────
   DROP / SAVE / bouton
     │  ensure_batch_number()
     │  resolve_entity()
     ▼
   outbox.db + <uuid>.alog  ──POST──▶  upload-roast?entrepriseSlug=…
     │  state=pending                   &createMissingBean=true
     │                                  body {id, alogContent,
     │                                        contentSha256, syncRecord}
     │◀── 2xx {status, beanCreated, storeResolved…} ──
     │  state=sent
     │  ──GET──▶ artisan-api /v1/aroast-receipt/<uuid>
     │◀── {present, contentHash, …} ──
     │  hash identique → verified (+ sync.addSync)
     │  sinon → pending (backoff)
     ▼
   header : « 2 en attente », « 1 à vérifier »
```

Rien ne quitte l'outbox tant que le serveur n'a pas confirmé, **sur une requête
séparée**, qu'il détient bien cette version-là.

### Répartition des rôles après le changement

| Flux | Transport | Statut |
|---|---|---|
| Torréfaction (création et toute mise à jour) | outbox → `upload-roast` | **nouveau, voie unique** |
| Session live (bannière CHARGE/DROP) | `plus` → `/v1/asession/*` | inchangé |
| RoastGuard | POST direct `/roastguard` | inchangé |
| Verrou du planning | `plus` → `/v1/aschedule/lock` | inchangé |
| Référentiel café/magasins | `plus` → `GET /v1/acoffees` | inchangé |
| Sync descendante (web → desktop) | `GET /v1/aroast/<uuid>` | inchangé, voir ci-dessous |

`plus/queue.py` n'est plus alimenté par des enregistrements de torréfaction :
les six points d'appel de `addRoast()` ([canvas.py:4358](../../src/artisanlib/canvas.py),
[canvas.py:15595](../../src/artisanlib/canvas.py),
[roast_properties.py:6474](../../src/artisanlib/roast_properties.py),
[controller.py:95,470,478](../../src/plus/controller.py)) sont redirigés vers
l'outbox. La fonction est conservée comme façade mince pour ne pas disperser le
changement.

### Préservation de la sync descendante

`GET /v1/aroast/<uuid>` renvoie `roast_logs.artisan_payload`, aujourd'hui
alimenté par `POST /v1/aroast`. Pour ne pas casser ce round-trip, l'outbox joint
au corps le `syncRecord` produit par `roast.getSyncRecord()`, et `upload-roast`
le **fusionne** dans `artisan_payload` (`{...existant, ...syncRecord}`) au lieu
de l'écraser. Après vérification du reçu, l'outbox appelle `sync.addSync()` et
`sync.setSyncRecordHash()` exactement comme le faisait `Worker.addSyncItem()` :
l'icône d'état et le suivi des éditions continuent de fonctionner.

## A — La société dans le `.alog`

### Format

Deux clés nouvelles, calquées sur `plus_store` / `plus_store_label` :

```python
plus_entity       = 'esperanza'          # slug = entity_hr_id servi par artisan-api
plus_entity_label = 'Esperanza Coffee'   # libellé lisible (humain, CSV, récap)
```

Ajoutées à la liste des champs de profil ([canvas.py:344](../../src/artisanlib/canvas.py)),
à `getProfile()` / `setProfile()` ([main.py:6040-6152](../../src/artisanlib/main.py))
et à la lecture de fichier ([main.py:16539](../../src/artisanlib/main.py)).

### Origine de la valeur

La société se choisit dans **Propriétés de torréfaction**, où le sélecteur
existe déjà (`plus_entities_combo` / `plus_entity_selected`,
[roast_properties.py:1505](../../src/artisanlib/roast_properties.py)) mais reste
purement local au dialogue : il ne sert qu'à filtrer les listes.

Cascade, première valeur non vide gagnante :

1. slug du `plus_store` composite (`L1002@esperanza`) — le magasin fait foi ;
2. `plus_entity_selected`, désormais recopié dans `qmc.plus_entity` /
   `qmc.plus_entity_label` à la validation du dialogue ;
3. valeur déjà présente dans le profil chargé (édition d'un `.alog` existant).

Si rien ne résout au moment d'enfiler, l'app demande la société (dialogue court
listant les sociétés du stock) plutôt que d'envoyer « nu ». C'est le pendant
desktop du garde-fou `requireEntreprise` du web. Pas de réglage « société du
poste » : un poste sert les deux sociétés, le choix appartient à la fiche.

### Bénéfice hors envoi

Le champ vit dans le fichier : un `.alog` réimporté six mois plus tard depuis le
web, ou lu par un script CSV, porte encore sa société sans dépendre du magasin.

## B — Outbox persistante (desktop)

Nouveau module `src/plus/outbox.py`, indépendant de `plus/queue.py` (qui reste
dédié au protocole plus). Aucune dépendance nouvelle : `sqlite3` de la
bibliothèque standard.

### Stockage

Répertoire de configuration Artisan, sous-dossier `roast_outbox/` :
`outbox.db` pour les métadonnées, `<uuid>.alog` pour le contenu (un fichier par
item). Le contenu, qui pèse des dizaines à des centaines de Ko avec les courbes,
reste hors base : inspectable, sauvegardable, récupérable à la main.

```sql
CREATE TABLE outbox (
  uuid              TEXT PRIMARY KEY,   -- roastUUID canonique (avec tirets)
  created_at        REAL NOT NULL,
  updated_at        REAL NOT NULL,
  alog_path         TEXT NOT NULL,
  sync_record_json  TEXT,
  content_sha256    TEXT NOT NULL,
  entity_slug       TEXT,
  batch_label       TEXT,               -- '#42' / '#42bis' — affichage UI
  state             TEXT NOT NULL,      -- pending|sent|verified|failed
  attempts          INTEGER NOT NULL DEFAULT 0,
  next_attempt_at   REAL NOT NULL,
  last_http_status  INTEGER,
  last_error        TEXT,
  server_roast_id   TEXT,
  bean_created      INTEGER NOT NULL DEFAULT 0,
  store_resolved    INTEGER,
  sent_at           REAL,
  verified_at       REAL
);
```

### Machine à états

| État | Signification | Sortie |
|---|---|---|
| `pending` | à envoyer, ou à réessayer après `next_attempt_at` | POST 2xx → `sent` |
| `sent` | accusé reçu, pas encore vérifié | reçu conforme → `verified` |
| `verified` | présent en base avec le bon hash | ligne conservée 30 j, fichier supprimé |
| `failed` | tentatives épuisées ou erreur non transitoire | jamais supprimé, rejouable |

Toute erreur (réseau, 5xx, reçu absent, hash divergent) renvoie en `pending`
avec backoff exponentiel plafonné : 30 s, 1, 2, 5, 15, 30, 60 min, puis 60 min.
Après 12 tentatives → `failed`. Un 400 (corps invalide) passe directement en
`failed` : le rejouer à l'identique ne servirait à rien. **Aucun état ne
supprime un item non livré** — c'est la correction directe du défaut nº 1.

### Durabilité

Le fichier `.alog` est écrit, `fsync`é, puis renommé (écriture atomique)
**avant** l'insertion en base : un crash entre les deux laisse au pire un
fichier orphelin, nettoyé au démarrage, jamais une ligne sans contenu. Base en
`journal_mode=WAL`, `synchronous=FULL`.

### Worker

`QThread` dédié, réveil périodique (30 s) et réveil immédiat à l'enfilement. Au
démarrage : scan complet, remise en file de tout ce qui n'est pas `verified`.
Verrou fichier (`outbox.lock`, PID + horodatage) pour qu'une seconde instance
d'Artisan ne double pas les envois.

Le worker **ne dépend ni de `plus_account` ni de l'état de connexion** : il
tente, échoue, réessaie. C'est la correction des défauts nº 2 et nº 3.

### Déclenchement

- **DROP** ([canvas.py:15468](../../src/artisanlib/canvas.py), `markDrop`, après
  `incBatchCounter()`), hors simulateur et hors UNDO DROP, **sans condition de
  connexion** ;
- **validation des Propriétés de torréfaction** et **SAVE** : ré-enfilement du
  même UUID avec le contenu à jour ;
- **action de menu**, qui devient « enfiler + réveiller le worker ».

Un ré-enfilement remplace le contenu et repasse l'état à `pending` : une seule
ligne par torréfaction, toujours la dernière version. Comme le serveur écrase à
partir du `.alog` complet, une mise à jour ne peut plus effacer des champs —
correction du défaut nº 4.

## C — Serveur

### `upload-roast`

1. Accepte `entrepriseSlug=<slug>` en plus de `entrepriseId=<uuid>` : le desktop
   connaît le slug (`entity_hr_id`), pas l'UUID Supabase. Résolution sur
   `entreprises.slug`, insensible à la casse ; slug inconnu → 400.
2. À défaut des deux, lit `plus_entity` dans le `.alog` parsé.
   Priorité : `entrepriseId` > `entrepriseSlug` > `plus_entity` du fichier.
3. Accepte `contentSha256` et `syncRecord` dans le corps. Le hash est stocké en
   colonne ; le `syncRecord` est **fusionné** dans `artisan_payload`.
4. Écrit `entreprise_slug` sur `roast_logs`.
5. Réponse enrichie : `contentHash`, `entrepriseSlug`, `batchNumberSynthetic`.

### `parse-alog.ts`

- `alogToCanonical()` extrait `plus_entity` → `entrepriseSlug` et
  `plus_entity_label` → `entrepriseLabel`.
- `deriveBatchNumber()` : dernier recours `AUTO-<YYYYMMDD>-<8 hex du roastUUID>`
  au lieu de `null` — dérivé de l'UUID et non du contenu, donc idempotent même
  si le `.alog` est corrigé et réenvoyé. Marque `batch_number_synthetic`.

### Migration SQL

```sql
ALTER TABLE roast_logs
  ADD COLUMN entreprise_slug        text,
  ADD COLUMN artisan_content_hash   text,
  ADD COLUMN batch_number_synthetic boolean NOT NULL DEFAULT false;
```

Pas de backfill de l'historique : décision assumée, on repart de maintenant.

### Journal d'ingestion

```sql
CREATE TABLE roast_ingest_events (
  id              bigserial PRIMARY KEY,
  at              timestamptz NOT NULL DEFAULT now(),
  roast_log_id    text,
  source          text NOT NULL,        -- 'desktop-outbox' | 'web-import' | …
  content_hash    text,
  entreprise_slug text,
  bean_resolved   boolean,
  bean_created    boolean,
  store_resolved  boolean,
  http_status     int,
  error           text
);
```

Append-only, écrit par `upload-roast` à chaque appel. Le post-mortem d'un envoi
douteux devient une requête SQL au lieu d'une fouille dans les logs Deno.

### Nouvelle route `GET /v1/aroast-receipt/<uuid>` (artisan-api)

Relit `roast_logs`, `roasts` et `transactions` :

```json
{ "present": true,
  "roastLogId": "…", "roastId": "…",
  "contentHash": "…",
  "entrepriseSlug": "esperanza",
  "batchNumber": "#42", "batchNumberSynthetic": false,
  "beanResolved": true, "beanName": "Pérou APU", "beanCreated": false,
  "storeResolved": true, "storeName": "Nantes",
  "decrementKg": 12.5,
  "updatedAt": "2026-08-04T09:12:00Z" }
```

404 si absent. Le desktop n'acquitte que si `present` est vrai **et** que
`contentHash` correspond à ce qu'il a envoyé : la preuve que c'est bien *sa*
version qui est en base. Hash différent → réenvoi.

### Grain non résolu

Le desktop envoie `createMissingBean=true` : la fiche grain est créée et
rattachée à la bonne société (logique `resolveOrCreateBean()` existante). La
réponse porte `beanCreated`, que l'outbox stocke : l'item est bien `verified`
(la donnée est arrivée, le stock est décrémenté), et alimente un badge
d'avertissement persistant « grain créé automatiquement — à vérifier ».

## D — Batch number garanti

### Desktop — `ensure_batch_number()`

Appelée au DROP et avant tout enfilement :

1. `roastbatchnr > 0` → rien à faire.
2. Sinon : reprendre le **dernier batch number valide connu** (mémorisé en
   `QSettings` sous `zabawa/last_valid_batch` à chaque torréfaction numérotée) et
   le suffixer : `#42` → `#42bis`, puis `#42bis2`, `#42bis3`… Le compteur de
   suffixes est persisté ; le « dernier valide » reste `#42` (un `bis` ne devient
   jamais la référence, sinon on dériverait en `bisbis`).
3. Aucun « dernier valide » connu (poste neuf) → `<YYYYMMDD>-1`, puis `-2`…

`roastbatchnr` est un entier et ne peut pas porter `42bis` : la valeur textuelle
part dans une clé `batchnumber` du profil — clé que `deriveBatchNumber()` lit
**déjà** en seconde position, juste après `roastbatchnr`. Aucun changement de
contrat serveur n'est nécessaire pour ce point ; le repli `AUTO-…` ne sert plus
que pour les fichiers tiers ou anciens.

Le numéro attribué s'affiche comme un numéro normal ; son caractère dérivé est
visible dans le panneau d'outbox.

## E — Interface

Dans le header ([myspresso_header.py](../../src/artisanlib/myspresso_header.py)) :

- pastille compacte : « ✓ à jour », « 2 en attente », « 1 échec »,
  « 3 à vérifier », couleur selon la sévérité, cliquable ;
- panneau détaillé : une ligne par item (batch, société, café, état, tentatives,
  dernière erreur, horodatage) avec « Réessayer », « Réessayer tout »,
  « Ouvrir le `.alog` », « Voir sur le web » ;
- au démarrage, alerte non bloquante si un item traîne depuis plus de 24 h.

L'état doit être lisible d'un coup d'œil depuis le poste de torréfaction, sans
ouvrir de menu : c'est précisément ce qui manque aujourd'hui, où un échec est
totalement silencieux.

## Erreurs et cas limites

| Cas | Comportement |
|---|---|
| Réseau coupé au DROP | `pending`, retry en backoff, aucune perte |
| App fermée avec des items en file | repris au démarrage suivant |
| Connexion plus jamais établie | sans effet : l'outbox n'en dépend pas |
| Deuxième instance d'Artisan | verrou fichier, une seule instance envoie |
| 2xx mais ligne absente en base | reçu 404 → retour en `pending` |
| Reçu présent, hash différent | réenvoi (version antérieure en base) |
| 400 corps invalide | `failed` immédiat, visible dans le panneau |
| Grain inconnu | fiche créée, `verified`, badge « à vérifier » |
| Magasin non résolu malgré la société | `verified` + avertissement ; pas de décrément sur le magasin fallback (comportement serveur existant) |
| Société introuvable à l'enfilement | l'app demande la société ; rien n'est enfilé sans réponse |
| `.alog` réédité et renvoyé | même UUID → une seule ligne, écrasée par la dernière version |
| Torréfaction sans batch number | `#Nbis` / `<date>-N` attribué avant l'envoi |
| Simulateur | jamais enfilé |
| Item `verified` puis modifié côté web | inchangé : la sync descendante lit `artisan_payload`, toujours alimenté |

## Vérification

Desktop (`pytest`) :

- machine à états : transitions, backoff, plafond, `failed`, aucun item non
  livré supprimé ;
- reprise après crash simulé : fichier orphelin, ligne sans fichier, base WAL ;
- cascade de résolution de la société ;
- `ensure_batch_number()` : les trois branches, suite `bis` / `bis2` ;
- round-trip `plus_entity` / `plus_entity_label` dans `getProfile()` / `setProfile()` ;
- vérification du reçu : hash conforme, hash divergent, 404 ;
- non-régression : plus aucun roast record dans `plus/queue.py`, session live et
  verrou planning toujours enfilés.

Serveur (`deno test`) :

- `parse-alog` : extraction `plus_entity`, `deriveBatchNumber` avec repli `AUTO` ;
- résolution `entrepriseSlug` → UUID, slug inconnu → 400 ;
- priorité `entrepriseId` > `entrepriseSlug` > `plus_entity` ;
- fusion de `artisan_payload` (le `syncRecord` n'écrase pas l'existant) ;
- `aroast-receipt` : présent, absent, hash.

Bout-en-bout manuel : couper le réseau, torréfier jusqu'à DROP, fermer Artisan,
rouvrir, rétablir le réseau — l'item part seul et passe `verified` ; la
torréfaction apparaît côté web avec la bonne société, le bon grain et le
décrément de stock. Puis modifier les propriétés et vérifier qu'aucun champ
n'est effacé côté web.

## Hors périmètre

- Backfill de l'historique déjà en base.
- Envoi de checkpoints pendant la chauffe (seul le DROP déclenche).
- Réglage « société par défaut du poste ».
- Refonte de `plus/queue.py` pour ses autres usages (session, planning) : on ne
  fait que cesser de lui confier les torréfactions.
