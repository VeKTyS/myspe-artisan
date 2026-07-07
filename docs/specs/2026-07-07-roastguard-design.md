# RoastGuard — spec & document de passation

Date : 2026-07-07 · Branche : `feat/artisan-4.2.0` · Desktop : implémenté (fondation) · Backend zabawa.plus : **à faire** (autre agent)

## Objet

Surveiller la torréfaction en direct dans Zabawa Roast (fork Artisan MySpresso),
alerter le torréfacteur en cas d'anomalie (bannière in-app + message + bip),
et notifier zabawa.plus pour tracer/pousser l'alerte côté cloud.

## Côté desktop — FAIT (src/artisanlib/myspresso_roastguard.py)

- **Moteur** `RoastGuard` : QTimer 1 s, actif uniquement pendant l'enregistrement
  (`qmc.flagstart`), lecture seule sur `qmc`, ne bloque jamais la boucle
  d'échantillonnage. Chaque détecteur a une condition « soutenue N secondes »
  et un cooldown de 60 s par type d'anomalie.
- **Détecteurs v1** (seuils dans QSettings `RoastGuard/*`) :
  | kind | condition | défaut | sévérité |
  |---|---|---|---|
  | `sensor_dropout` | BT invalide (-1) pendant N s | 5 s | critical |
  | `bt_stall` | BT plate (<0.3°) sur fenêtre N s, entre TP et DROP | 30 s | warning |
  | `ror_crash` | RoR BT négatif soutenu, entre TP et 1er crack | 10 s | warning |
  | `et_runaway` | ET > plafond (`etMax`) | 500°F / 260°C | critical |
  | `dry_overrun` | pas de FIN SÉCHAGE après `dryDeadline` | 8 min | warning |
  | `fcs_overrun` | pas de 1er crack après `fcsDeadline` | 13 min | warning |
  | `divergence` | \|BT − BT référence\| > `divergenceDeg` pendant `divergenceSeconds` (si profil d'arrière-plan chargé) | 15° / 15 s | warning |
- **Alerte in-app** : `RoastGuardBanner` sous le header (tokens `error_bg`/`error_fg`,
  theme-aware, bouton Ignorer), message dans la barre Artisan, `QApplication.beep()`
  si critical.
- **Réglages** : Réglages MySpresso → section 04 RoastGuard :
  `RoastGuard/enabled` (défaut ON), `RoastGuard/cloudNotify` (défaut OFF tant que
  le backend n'existe pas).
- **Notification cloud** : POST fire-and-forget (thread daemon, timeout 6 s,
  échec silencieux loggué) vers `{cloud/api_base_url}/functions/v1/roastguard`.

### Payload envoyé (contrat)

```json
POST /functions/v1/roastguard
{
  "action": "notify",
  "event": {
    "kind": "ror_crash",
    "severity": "warning",
    "message": "RoR négatif — chute de température anormale",
    "roast_title": "Ethiopia 2025, TARAMESA…",
    "batch_nr": 23213,
    "roast_time_s": 512.4,
    "bt": 388.2, "et": 415.9, "ror": -1.8,
    "mode": "F",
    "app_version": "zabawa-roast"
  }
}
```

## Côté zabawa.plus — À FAIRE (prompt pour l'autre agent)

Conventions MySpresso (cf. guide dev web) : Supabase projet `edvrzoisxdivzyfjxuyg`,
schéma `myspresso` (PAS `public`), Edge Functions Deno **1 fonction par domaine
avec `switch(action)`**, partagés `_shared/cors.ts` + `_shared/supabase.ts`,
déploiement `npx supabase functions deploy roastguard --no-verify-jwt`.

1. **Table `myspresso.roastguard_events`** : `id`, `created_at`, `kind`,
   `severity`, `message`, `roast_title`, `batch_nr`, `roast_time_s`,
   `bt`, `et`, `ror`, `mode`, `machine_sn` (nullable), `user_email` (nullable).
2. **Edge Function `roastguard`** avec `switch(action)` :
   - `notify` : valider le payload ci-dessus, insérer dans `roastguard_events`,
     retourner `{ ok: true, id }`.
   - `list` : derniers événements paginés (`.range()` — penser à la limite 1000).
3. **Frontend** : brancher le composant `Notifications` existant (components/)
   pour afficher les alertes RoastGuard (badge + liste), page ou section dans
   le dashboard Opérationnel. CSS plain (pas de Tailwind), icônes Lucide
   `strokeWidth={1.5}`, palette `#1E2A49`/`#B22418`, Montserrat.
4. **Auth** : le desktop n'envoie pas encore de token (l'auth cloud du fork est
   en chantier — QSettings `cloud/auth_enabled`). La fonction est déployée
   `--no-verify-jwt` comme les autres ; si un token devient disponible côté
   desktop, l'ajouter en header `Authorization: Bearer …` dans
   `myspresso_roastguard.py::_notify_cloud` (un seul endroit).

## Reste à faire côté desktop (peut être fait par l'autre agent ou plus tard)

- UI de réglage des seuils (les clés QSettings `RoastGuard/dropoutSeconds`,
  `stallSeconds`, `rorCrashSeconds`, `etMax`, `dryDeadline`, `fcsDeadline`,
  `divergenceDeg`, `divergenceSeconds` sont lues dynamiquement — il ne manque
  que le formulaire).
- Son dédié (actuellement `QApplication.beep()`), option « bip aussi sur warning ».
- Tests unitaires du moteur (`_sustained`, chaque détecteur avec un qmc mocké).
- Historique local des alertes de la session (liste dans le footer Historique).
- `machine_sn`/`user_email` dans le payload quand ces infos existeront côté app.

## Garde-fous

- Ne JAMAIS bloquer la boucle d'échantillonnage : tout le cloud est en thread
  daemon best-effort ; le tick est intégralement sous try/except.
- Cooldown 60 s par type : une condition persistante ne spamme pas.
- `RoastGuard/cloudNotify` reste OFF par défaut tant que l'Edge Function
  n'est pas déployée.
