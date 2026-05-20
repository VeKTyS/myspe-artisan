# Cahier des charges — Refonte visuelle du fork MySpresso Artisan

**Date** : 2026-05-20
**Pour** : skill design (ui-ux-pro-max, frontend-design, ou équivalent)
**Statut** : À chiffrer par le design agent

---

## 1. Contexte

Le fork **MySpresso Artisan** est un logiciel desktop PyQt6 (Python 3.12+) basé sur Artisan v4.0.3 (GPL-3.0), customisé pour ZABAWA / MySpresso. Il sert aux torréfacteurs de café à enregistrer et analyser leurs torréfactions (courbes de température, Rate of Rise, événements CHARGE/DROP, etc.). L'app communique avec un backend MySpresso (Supabase Edge Functions) pour synchroniser stock, planning, et résultats de roasts.

**Cible utilisateurs** : opérateurs torréfacteurs ZABAWA — souvent en milieu de production (atelier, machine en route, mains potentiellement chargées). Lisibilité, taille des contrôles, et clarté immédiate des états priment sur la densité d'information.

**Plateformes** : macOS (référence Sonoma+), Windows 10/11, Linux Ubuntu 22.04+, Raspberry Pi (display tactile parfois). Cross-platform Qt6 obligatoire.

**Identité visuelle MySpresso** (cf. skill `myspresso-ui` à activer côté design agent) :
- Palette navy / red
- Cards carrées, ombres subtiles
- Police Montserrat
- Style minimal, professionnel coffee industry

## 2. État actuel — pain points observés

(Voir capture du Main Canvas en annexe.)

| # | Problème | Détail |
|---|---|---|
| 1 | **Branding leak** | Coin haut-droit affiche encore "sponsorisé par artisan.plus" (alors qu'on est sur le fork MySpresso). Variables : `__release_sponsor_name__`, `__release_sponsor_domain__`, `__release_sponsor_url__` dans `src/artisanlib/__init__.py`. |
| 2 | **Identité visuelle générique Qt** | Look système macOS/Win/Linux par défaut, aucune cohérence MySpresso. Pas de couleurs de marque, pas de typo custom. |
| 3 | **Boutons d'action hétérogènes** | "REINITIALISER", "ON", "DEBUT" en haut-droite + boutons CHARGE/DROP/FCs/FCe/SCs/SCe/COOL en bas. Tailles inégales, couleurs hardcodées (`#4c97c3` / `#3979ae`). |
| 4 | **Status bar peu visible** | Messages d'état (`sendmessage(...)`) écrits dans une seule ligne avec les messages précédents qui se font écraser en 2 sec. Impossible de voir si un push cloud a réussi. |
| 5 | **Typographie sans hiérarchie** | Titre roast, timer central, échelles axes, labels boutons — toutes ~même poids visuel. Pas de scale claire. |
| 6 | **Chart canvas matplotlib brut** | Toolbar matplotlib standard (icônes home/back/forward/move/zoom), peu intégrée au reste. |
| 7 | **Dialogs non rebrandées** | Roast Properties, Settings, Alarms — toutes en style Qt natif. Pas d'icônes MySpresso, pas de spacing cohérent. |
| 8 | **Pas de feedback de connexion cloud visible** | L'icône cloud/plus dans la toolbar (déclencheur du `controller.toggle`) change d'état mais le statut "connecté à MySpresso" mériterait d'être plus visible (badge, halo, ou texte explicite). |
| 9 | **Mode UI Production vs Standard vs Expert** | Trois modes prévus côté code (`UIModeMenu` ligne 2600 main.py) mais aucune différenciation visuelle entre eux. |
| 10 | **Spec et tooltips en anglais** | Locale française activée mais nombreux tooltips et messages techniques restent EN. |

## 3. Objectifs de la refonte

**MUST-HAVE** (sans ça, pas de release) :
- M1 : Remplacer **toute** mention "artisan.plus" UI-visible par "MySpresso" (variables sponsor + chaînes restantes).
- M2 : Appliquer la palette MySpresso (navy primaire, red accent, neutrals chauds) sur les chrome de l'app : toolbar, boutons d'action, status bar, headers de dialogs.
- M3 : Hiérarchie typographique claire (3-4 niveaux : H1 titre roast, H2 sections, body, mono pour valeurs numériques).
- M4 : Status bar **non-volatile** pour les events critiques (succès/échec de push cloud, etc.) — soit zone dédiée, soit log inline visible.
- M5 : Indicateur de connexion cloud (icône + texte ou badge "MySpresso · connected") toujours visible.

**SHOULD-HAVE** (release polish) :
- S1 : Système de tokens couleur centralisé (un fichier `src/artisanlib/design_tokens.py` avec `colors`, `fonts`, `spacing`) consommé par les ~340 `setStyleSheet` actuellement inline.
- S2 : Dark mode cohérent (déjà détecté côté système au `style_hints.colorScheme()`, mais styling pas appliqué partout).
- S3 : Icons SVG MySpresso pour la toolbar principale (remplacer les PNG `src/icons/` les plus visibles : home, settings, cloud, schedule). Garder les PNG legacy pour les moins critiques.
- S4 : Roast Properties dialog redesigné — sections plus aérées, picker Stock+Magasin plus visuel.

**NICE-TO-HAVE** (si scope le permet) :
- N1 : Mockup d'un mode "Production" simplifié (3 boutons géants : Charger / Démarrer / Décharger, plus rien d'autre visible).
- N2 : Animation subtile sur les transitions d'état (CHARGE → DROP, connect/disconnect cloud).
- N3 : Theme MySpresso accessible depuis Config → Themes (utilise le `themeMenu` existant).

## 4. Contraintes techniques

**STACK** :
- **PyQt6 6.11.x** — utilisation de QSS (Qt Style Sheets, sous-ensemble de CSS) pour le styling.
- **Matplotlib 3.10** — pour le canvas du graphique de température. Style configurable via `rcParams` ou des color tokens passés au plot. Pas de Web stack.
- **PyInstaller** pour le packaging final (Win/macOS/Linux/RPi). Les assets (fonts, icons, QSS) doivent être bundlables.

**INTERDITS** :
- Pas de réécriture du `main.py` (28 000 lignes, monolithique, risqué). Les changements doivent se faire par **stylesheets** + **fichiers d'assets** + au max ajout d'un fichier `design_tokens.py` consommé sans changer la structure des classes.
- Pas de changement du menu / des widgets / de l'arbre de la fenêtre principale. C'est juste de l'**habillage**.
- Pas de réécriture du chart matplotlib (juste rc params + couleurs).
- Pas de dépendance frontend (React, Tailwind, shadcn) — c'est du desktop Qt, pas du web.
- Garder la compat avec les 3 plateformes (macOS Sonoma+, Win10+, Linux Ubuntu22+). Tester au minimum macOS (env du dev).

**RESPECTS** :
- Conventions Qt (QSS class selectors `QPushButton#ONButton`, etc.)
- Locale française par défaut (operateur ZABAWA = FR), mais structure i18n préservée (`QApplication.translate(...)`).
- Accessibilité : contraste WCAG AA minimum sur boutons et status bar.
- Mode UI **Standard** par défaut (le user opérateur), Production = simplifié, Expert = tout.

## 5. Livrables attendus

| # | Livrable | Format | Localisation |
|---|---|---|---|
| L1 | **Design tokens** (couleurs, polices, espacements) | `src/artisanlib/design_tokens.py` (constantes Python) + miroir QSS | nouveau fichier |
| L2 | **Stylesheet global QSS** | `src/artisanlib/styles/myspresso.qss` chargé au démarrage via `app.setStyleSheet(open(...).read())` | nouveau dossier |
| L3 | **Patch des `setStyleSheet` inline** prioritaires | Edit des call-sites les plus visibles : `main.py` (toolbar, status bar, boutons CHARGE/DROP), `roast_properties.py` (dialog). Pas obligé de toucher les 340. | edits ciblés |
| L4 | **Icons MySpresso** essentiels | SVG ou PNG @1x/@2x — toolbar (home, cloud, settings, schedule, send/upload), boutons d'action si custom | `src/icons/myspresso/` |
| L5 | **Rebrand sponsor variables** | `__release_sponsor_*` → MySpresso dans `artisanlib/__init__.py` | edit 3 lignes |
| L6 | **Mockup screenshots** (avant/après) | Une capture par écran refait (canvas principal, Properties, Settings) en PNG | `docs/superpowers/design/screenshots/` |
| L7 | **Guide d'application** | `docs/superpowers/design/design_system.md` avec : palette, échelle typo, spacing scale, état des composants, exemples QSS | nouveau fichier |
| L8 | **Tests visuels manuels** | Checklist `docs/superpowers/design/visual_qa.md` : 20-30 items vérifiables à l'œil (boutons cliquables, focus visible, dark mode OK, etc.) | nouveau fichier |

## 6. Périmètre — ce qui est INCLUS / EXCLU

**INCLUS** :
- Refonte des composants top-level visibles : main window header/footer, toolbars, boutons d'action, status bar, dialog Roast Properties, dialog MySpresso Settings.
- Système de tokens consommable par tout le code futur.
- Dark mode appliqué cohéremment sur ces composants.

**EXCLU** :
- Tous les dialogs secondaires (Alarms, Designer, Comparator, Energy, ColorMeter, Phidget config…). Trop nombreux, trop spécifiques. Ils restent en style Qt natif pour cette release.
- Le canvas matplotlib lui-même (juste sa palette / fonts). La toolbar matplotlib en bas reste native.
- Les machines templates dans `src/includes/`.
- Les traductions `.ts/.qm` (chantier i18n séparé).

## 7. Critères d'acceptation

Quand le design agent peut considérer son travail livré :

1. ✅ Lancer Artisan avec `MYSPRESSO_AUTH_ENABLED=false python artisan.py` montre **zéro mention "artisan.plus"** dans l'UI visible (sauf URL `shop_base_url` qui n'apparaît pas en UI directe).
2. ✅ La palette navy/red MySpresso est appliquée sur le header, status bar, et au moins 3 boutons d'action principaux (CHARGE, DROP, plus toolbar Connect cloud).
3. ✅ Le fichier `design_tokens.py` existe et est importé par au minimum 5 call-sites précédemment hardcodés (e.g., `light_blue` / `dark_blue` de `main.py:239-240`).
4. ✅ Le QSS global se charge sans erreur (vérifié par `python -c "from PyQt6.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); app.setStyleSheet(open('src/artisanlib/styles/myspresso.qss').read()); print('OK')"`).
5. ✅ Dark mode : passer macOS en mode sombre → l'app suit (header/status restent lisibles, palette adaptée).
6. ✅ Le status bar conserve les messages critiques (push success/fail) au moins 8 sec OU les copie dans une zone secondaire persistante.
7. ✅ Les screenshots avant/après sont commit dans `docs/superpowers/design/screenshots/`.
8. ✅ La checklist visual_qa.md passe sur macOS (la plateforme du dev). Pour Win/Linux/RPi, livrer un noted "à vérifier ultérieurement".
9. ✅ Aucun test unitaire existant ne casse (`cd src && python -m pytest test/unitary/plus/` reste vert).
10. ✅ Aucune fonctionnalité métier (Connect cloud, push roast, fetch stock, CHARGE+DROP) ne casse — smoke test via lancement de l'app.

## 8. Hors périmètre — pour itérations futures

- Mode "Production" simplifié end-to-end (mockup possible mais pas d'implémentation cette release).
- Animation et transitions.
- Refonte canvas matplotlib (juste couleurs).
- Multi-langue (i18n).
- Mode kiosque / tablette tactile.
- Refonte de TOUS les dialogs (~40 dialogs Qt).

## 9. Process suggéré pour le design agent

1. **Découverte** : activer la skill `myspresso-ui` pour récupérer le design system. Cloner un visuel screenshot du canvas actuel (déjà fourni).
2. **Audit** : confirmer / amender les pain points §2.
3. **Wireframes** : produire 3-5 wireframes des écrans principaux (canvas, Properties, Settings) en mode clair + sombre, en respectant les contraintes Qt.
4. **Tokens** : définir la palette, typo scale, spacing scale (cf. skill `ckm-design-system` pour la structure trois-couches primitive→semantic→component si pertinent).
5. **QSS implementation** : traduire les tokens en QSS, appliquer aux composants prioritaires.
6. **Validation** : lancer l'app, screenshot avant/après, checklist visual_qa.
7. **Documentation** : remplir `design_system.md` et `visual_qa.md`.

## 10. Annexe — capture du canvas actuel

(Voir image jointe par le user — Main Canvas Artisan v4.0.3 fork MySpresso, no recording active, mode F°, profile "#8 Pérou, APU Cenfrocafe 2024".)

Éléments visibles à conserver fonctionnellement :
- Compteur horaire central + température courante (top center)
- 3 boutons d'action droite : REINITIALISER, ON, DEBUT
- Toolbar gauche : home, back, forward, move, zoom, chart (matplotlib)
- Axes Y gauche (température °F) + droite (RoR °F/min)
- Légende bas droite (TE / TG / ΔTG)
- Footer avec date, profil, durée, poids vert
- Coin haut-droit "sponsorisé par X" → **doit devenir "MySpresso"** ou disparaître.
