# Auto-Update Design — Zabawa Roast

**Date:** 2026-06-03
**Platforms:** macOS, Windows
**Scope:** Background update check at startup + one-click silent install + auto-restart

---

## 1. Goals

- Users already running the app receive a non-intrusive notification when a newer version is published on GitHub Releases (`VeKTyS/myspe-artisan`)
- One button click downloads and silently installs the update, then restarts the app automatically
- No browser, no manual installer wizard, no extra steps

---

## 2. Architecture

### New file: `src/artisanlib/updater.py`

Three components with distinct responsibilities:

#### `UpdateChecker(QThread)`
- Triggered by `QTimer.singleShot(5000, ...)` at app startup (5 s delay)
- Calls `GET https://api.github.com/repos/VeKTyS/myspe-artisan/releases/latest` (timeout 4 s)
- Compares `tag_name` (e.g. `v1.2.3`) against `artisanlib.__version__`
- Emits `update_available(version: str, asset_url: str, asset_name: str)` if a newer version exists
- Picks the right asset based on platform: `*-mac-*.dmg` on macOS, `*-win-*.exe` on Windows
- Silently swallows network errors (no dialog on failure)

#### `UpdateDownloader(QThread)`
- Receives `asset_url` and `dest_dir` (e.g. `QDir.tempPath()`)
- Streams the download with `requests` in chunks, emits `progress(int)` (0–100)
- Emits `finished(local_path: str)` when done, `error(msg: str)` on failure

#### `run_updater_and_quit(asset_path: str) -> None`
- Writes a platform-specific helper script to a temp file
- **macOS** (`updater_<pid>.sh`):
  ```bash
  #!/bin/bash
  sleep 2
  hdiutil attach -nobrowse -quiet "$DMG" -mountpoint /tmp/zr_update
  rsync -a --delete /tmp/zr_update/*.app "$APP_DEST/"
  hdiutil detach /tmp/zr_update -quiet
  open "$APP_DEST/Zabawa Roast.app"
  rm -- "$0"
  ```
  `APP_DEST` = directory containing the current `.app` bundle (detected from `sys.executable`)
- **Windows** (`updater_<pid>.bat`):
  ```bat
  @echo off
  timeout /t 2 /nobreak >nul
  "%INSTALLER%" /S
  start "" "%PROGRAMFILES%\Zabawa Roast\Zabawa Roast.exe"
  del "%~f0"
  ```
- Launches the script with `subprocess.Popen`, then calls `QApplication.instance().quit()`
- **Fallback**: if the helper launch fails (e.g. permission error), opens the download folder in the file manager so the user can run the installer manually — no silent failure

### Changes to `src/artisanlib/main.py`

- `checkUpdate()` existing method: update GitHub API URL from `artisan-roaster-scope/artisan` → `VeKTyS/myspe-artisan`
- Add `_start_update_check()` method: creates `UpdateChecker`, connects its `update_available` signal to `_show_update_banner()`
- Add `QTimer.singleShot(5000, self._start_update_check)` at the end of `__init__`
- Add `_show_update_banner(version, asset_url, asset_name)`: instantiates `UpdateBanner` and inserts it at the top of `centralWidget()`'s layout

### New widget: `UpdateBanner(QFrame)` — in `updater.py`

Thin dismissible bar at the top of the main window:

```
┌────────────────────────────────────────────────────────────────────┐
│  Zabawa Roast v1.2.3 est disponible   [████████░░░░ 65%]  [✕]     │
└────────────────────────────────────────────────────────────────────┘
```

States:
1. **Idle**: text + "Mettre à jour" button + "✕" dismiss
2. **Downloading**: inline progress bar replaces the button
3. **Done**: "Installation en cours, fermeture…"
4. **Error**: "Échec du téléchargement. [Ouvrir le dossier]"

Styling follows the MySpresso design system (navy/red palette, Montserrat).

---

## 3. Data flow

```
app __init__
  └─ QTimer(5s) ──► UpdateChecker.run()
                        │ GET /releases/latest
                        │ compare versions
                        └─ signal: update_available(v, url, name)
                                │
                        main.py: _show_update_banner()
                                │
                        UpdateBanner inserted into window layout
                                │
                        User clicks "Mettre à jour"
                                │
                        UpdateDownloader.run()
                                │ progress(int) ──► banner progress bar
                                │
                                └─ finished(path)
                                        │
                                run_updater_and_quit(path)
                                        │ write helper script
                                        │ subprocess.Popen(script)
                                        └─ QApplication.quit()
```

---

## 4. "Ignore this version" behaviour

- On dismiss (✕), store skipped version in `QSettings` under `updater/skipped_version`
- `UpdateChecker` reads this value; if `latest == skipped`, emits nothing
- Resets automatically when the user installs a version equal to or beyond the skipped one

---

## 5. Error handling

| Scenario | Behaviour |
|---|---|
| No internet / API timeout | Checker silently exits, no UI shown |
| API returns non-200 | Silently ignored |
| Download fails mid-way | Banner shows error + "Ouvrir le dossier" fallback |
| Helper script launch fails | Open file manager at temp folder, show dialog "Installez manuellement" |
| macOS: app not writable (e.g. in `/Applications` without perms) | `rsync` will fail; script exits non-zero; app already quit — user must re-run from the newly installed location. Log error to stderr in script. |

---

## 6. NSIS silent install note

The existing `setup-install3-pi.nsi` must support the `/S` flag for silent mode. Standard NSIS installers support this by default if they use the `MUI2` macro set; verify this before implementation.

---

## 7. Security

- Downloads are verified by comparing the file size against the `size` field in the GitHub release asset JSON (a lightweight integrity check — not a cryptographic signature)
- No credentials are stored or transmitted; the GitHub API endpoint used is public (consistent with making the repo public)

---

## 8. Out of scope

- Linux (not in target user base for this feature)
- Delta/patch updates (full installer is acceptable given file sizes)
- Rollback mechanism
- Silent update without any user interaction (user must at least click "Mettre à jour")
