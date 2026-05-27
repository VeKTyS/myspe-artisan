# MySpresso Artisan — Design system applied

> Implémentation locale du design produit par Claude Design (handoff
> 2026-05-20). Source de vérité couleurs : [`src/artisanlib/design_tokens.py`](../../../src/artisanlib/design_tokens.py).
> Stylesheet : [`src/artisanlib/styles/myspresso.qss`](../../../src/artisanlib/styles/myspresso.qss).

## Palette

### Navy (brand primary)
| Token | Hex | Usage |
|---|---|---|
| `NAVY_900` | `#070D1F` | Foreground primary |
| `NAVY_800` | `#0A1733` | Primary button hover |
| `NAVY_700` | `#0F1E3D` | **Brand primary** — boutons primary, headers |
| `NAVY_500` | `#243B6B` | OFF/STOP/PID idle state |
| `NAVY_400` | `#3E5685` | SV - button |

### Red brick (accent / destructive)
| Token | Hex | Usage |
|---|---|---|
| `RED_700` | `#8E2F26` | Danger button hover |
| `RED_600` | `#A8392E` | **Brand red** — ON/START/PIDactive, danger, accent text |
| `RED_500` | `#B8473C` | SV + button |
| `RED_400` | `#C66459` | Dark-mode danger |

### Warm neutrals
| Token | Hex | Usage |
|---|---|---|
| `WARM_100` | `#FAF8F4` | App background (canvas) |
| `WARM_200` | `#F2EFE7` | Surface alt / sunken |
| `WARM_300` | `#E8E3D6` | Border subtle |
| `WARM_400` | `#D4CCBA` | Border strong |
| `WARM_500` | `#A8A092` | Disabled foreground |
| `WARM_700` | `#4E4A44` | Secondary text |

### Chart colors (matplotlib)
| Token | Hex | Maps to |
|---|---|---|
| `CHART_TE` | `#A8392E` | ET (environmental temp) — red |
| `CHART_BT` | `#0F1E3D` | BT (drum temp) — navy |
| `CHART_DELTA` | `#7A736A` | ΔTG (rate of rise) — warm gray |
| `CHART_FC` | `#C7873A` | First crack marker — ochre |
| `CHART_SC` | `#5C4A2E` | Second crack marker — roast brown |

## Typographie

- **Sans** (UI) : `"Montserrat", -apple-system, "Segoe UI", sans-serif`. Montserrat n'est pas bundlée — fallback macOS=San Francisco / Windows=Segoe UI / Linux=système.
- **Mono** (chiffres tabulaires) : `"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace`. Bundlée dans `src/fonts/JetBrainsMono-*.ttf`.

| Token | px | Usage |
|---|---|---|
| `FONT_SIZE_TIMER` | 72 | Timer hero (si jamais remplacé par QLabel) |
| `FONT_SIZE_TEMP` | 32 | Affichage température |
| `FONT_SIZE_H1` | 26 | Titre de section principal |
| `FONT_SIZE_TITLE` | 18 | Titre de dialog |
| `FONT_SIZE_BODY` | 13 | Body / labels |
| `FONT_SIZE_CAPTION` | 11 | Captions, status bar |

Weights : 400 (regular) / 500 (medium) / 600 (semibold) / 700 (bold).

## Spacing (4pt grid)

| Token | px |
|---|---|
| `SPACE_2` | 4 |
| `SPACE_4` | 8 |
| `SPACE_5` | 12 |
| `SPACE_6` | 16 |
| `SPACE_8` | 24 |
| `SPACE_9` | 32 |

## Radius

| Token | px | Usage |
|---|---|---|
| `RADIUS_SM` | 2 | Boutons, cards MySpresso "quasi-carré" |
| `RADIUS_MD` | 4 | Inputs |

## Component roles (QSS property selectors)

Les composants Qt s'opt-in via `widget.setProperty('role', 'X')` puis sont stylés par les sélecteurs `QPushButton[role="X"]` / `QLabel[role="X"]` du QSS.

| Role | Selector cible | Quand l'utiliser |
|---|---|---|
| `primary` | QPushButton | Action principale (OK, Confirm, Submit) → navy 700 |
| `danger` | QPushButton | Action destructive (DROP, Annuler avec perte) → red 600 |
| `secondary` | QPushButton | Action secondaire (Cancel, Reset) → outlined warm |
| `event` | QPushButton | Boutons événement de roast — combinable avec `state` (active/charge/drop) |
| `icon` | QPushButton | Bouton icône (toolbar) → transparent |
| `timer` | QLabel | Hero timer 72px JetBrains Mono |
| `temperature` | QLabel | Affichage température 32px red |
| `title` | QLabel | Titre fort 18px navy 900 |
| `muted` | QLabel | Texte secondaire warm 600 |
| `dialogTitle` | QLabel (dans QDialog) | Titre de dialog |
| `section` | QLabel (dans QDialog) | Header de section uppercase |
| `mono` | QLineEdit / QSpinBox | Force JetBrains Mono (tabular) |

## Status bar severity (data property)

```python
status_bar.setProperty('severity', 'success' | 'error' | 'warn' | 'info')
status_bar.style().unpolish(status_bar)
status_bar.style().polish(status_bar)
```

Le QSS applique une bordure colorée à gauche selon la sévérité.

## Cloud badge (data property)

```python
cloud_label.setObjectName('cloudBadge')
cloud_label.setProperty('connected', 'true' | 'false')
```

Vert si connecté / rouge si déconnecté.

## Dark mode

L'app détecte automatiquement le mode système macOS via `QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark` et set la property `theme="dark"` sur la QApplication. Le QSS a un bloc complet `[theme="dark"]` qui override toutes les couleurs.

## Désactivation

Pour comparer avec le look upstream Artisan :

```bash
MYSPRESSO_STYLE_DISABLED=true python artisan.py
```

## Fichiers de référence

| Fichier | Rôle |
|---|---|
| [`src/artisanlib/design_tokens.py`](../../../src/artisanlib/design_tokens.py) | Constantes Python (source de vérité) |
| [`src/artisanlib/styles/myspresso.qss`](../../../src/artisanlib/styles/myspresso.qss) | QSS global |
| [`src/artisanlib/styles/__init__.py`](../../../src/artisanlib/styles/__init__.py) | Loader (QFontDatabase + setStyleSheet + dark mode) |
| `src/fonts/JetBrainsMono-*.ttf` | Fonts bundlées |
| `src/icons/myspresso/logo.webp` | Logo MySpresso |
