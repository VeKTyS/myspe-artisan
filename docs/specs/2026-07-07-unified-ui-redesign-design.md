# Redesign UI unifié Mac / Windows — spec (approche A)

Date : 2026-07-07 · Branche : `feat/redesign-unified-ui` · Maquette validée :
https://claude.ai/code/artifact/3e426ffb-eada-4175-adfe-a9aac11c46e2

## Objectif

Rendu strictement identique sur macOS et Windows, graphe et LCD au premier
plan, **zéro fonctionnalité supprimée** (re-skin pur : chaque menu, dialogue,
champ, bouton et raccourci reste en place). Les fenêtres d'options doivent
être modernes, épurées et aérées — pas d'écrans tassés.

## Causes traitées

1. **Deux bases de rendu Qt** — Windows force `Fusion`, macOS reste natif
   (`main.py:703`). Le QSS se superpose à deux moteurs différents.
2. **Trois sources de vérité couleurs** — `design_tokens.py`,
   `styles/myspresso.qss` (synchronisé à la main), hex en dur dans les
   widgets `myspresso_*`. Le hero/pilote ignore le mode sombre.
3. **LCD `QLCDNumber` 7-segments** — hors langage visuel (JetBrains Mono),
   rendu dépendant du DPI/de la plateforme.

## Lots

### Lot 1 — Base de rendu unifiée
`app.setStyle('Fusion')` sur toutes les plateformes (démarrage + valeur par
défaut du réglage `appearance`). Le menu reste natif (barre globale macOS /
menu dans la fenêtre Windows) : seule différence assumée entre OS.

### Lot 2 — QSS généré depuis les tokens
`myspresso.qss` devient un template : chaque hex est remplacé par un
placeholder `@TOKEN@` ; `styles/__init__.py` substitue les valeurs depuis
`design_tokens.py` au chargement. Les hex en dur des widgets
`myspresso_header/hero/pilot/eventlog/stats/settings` migrent vers des
imports `design_tokens`. Une seule source de vérité ; la dérive devient
impossible.

### Dialogues aérés (exigence ajoutée)
Point d'interception unique : `ArtisanDialog` (classe mère des ~45
dialogues) applique des marges génereuses (24 px) et un espacement vertical
confortable au layout racine à l'affichage, sauf si le dialogue a déjà des
marges personnalisées. Côté QSS : padding des panes d'onglets, group boxes
respirants, hauteur minimale des contrôles, `QDialogButtonBox` espacé.

### Lot 3 — `ValueTile` remplace `QLCDNumber`
Nouveau widget `ValueTile` (carte quasi-carrée, liseré couleur de courbe,
chiffres tabulaires JetBrains Mono) API-compatible avec `QLCDNumber`
(`display()`, `setDigitCount()`, `setSegmentStyle()` no-op, traduction des
stylesheets `QLCDNumber { color; background-color }` existants). Remplace
les LCD principaux, de phases, des sliders et des fenêtres « large LCDs »
sans toucher aux milliers de call-sites `display()`.

### Lot 4 — Mode sombre complet
Helper `design_tokens.semantic(dark)` ; les widgets MySpresso choisissent
leurs couleurs au runtime. Palette matplotlib sombre pour le graphe (fond
`#16181D`, courbes éclaircies). Bascule vivante du property `theme` du QSS
sur `colorSchemeChanged`.

### Lot 5 — Normalisation + vérifications
`nonedevDlg` (comm.py) et `MyspressoSettingsDialog` rebasés sur
`ArtisanDialog`. Compilation, tests, lancement local. L'audit visuel écran
par écran sur les deux OS se fait sur les builds CI (checklist des 45
dialogues dans la PR).

## Garanties

- Zéro fonctionnalité supprimée ; comportements, raccourcis et workflows intacts.
- Layout cockpit v4.1.2 inchangé (zones, splitters, boutons).
- Graphe matplotlib et toutes ses fonctions intacts ; ~65 % de la hauteur par défaut.
- Sélecteurs de fichiers, impression, boîtes système : natifs (volontaire).
