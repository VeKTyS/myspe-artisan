# MySpresso Artisan — Visual QA checklist

Run after applying the design system. Lancer Artisan dans l'environnement
dev :

```bash
cd /Users/lv/Documents/myspe-artisan/src
MYSPRESSO_AUTH_ENABLED=false python artisan.py
```

Pour comparer avec l'upstream, ajouter `MYSPRESSO_STYLE_DISABLED=true`.

---

## Canvas principal

### Boutons toolbar haut-droite
- [ ] **REINITIALISER** : style outlined warm (background `#F2EFE7`, border `#D4CCBA`, texte navy)
- [ ] **ON** (état OFF) : navy `#243B6B` plein, texte blanc
- [ ] Cliquer ON → bascule en état ON : red `#A8392E`, texte blanc
- [ ] Cliquer OFF (en état ON) : retour navy
- [ ] **DEBUT** (état STOP) : navy
- [ ] Cliquer DEBUT → state START : red
- [ ] Transition CHARGE → DROP : couleurs cohérentes sur le ON/OFF tout du long

### Boutons événements (bas du canvas)
- [ ] CHARGE, DRY, FCs, FCe, SCs, SCe, COOL, DROP, RESET — tous avec border 2px et style aérée
- [ ] Hover : background s'éclaircit
- [ ] Pressed : background s'assombrit
- [ ] Disabled : couleur warm 500

### LCDs (timer + ET + BT + ΔET + ΔBT + SV)
- [ ] **Timer LCD** : fond warm `#FAF8F4`, segments navy `#070D1F`
- [ ] **ET LCD** : fond red `#A8392E`, segments blancs
- [ ] **BT LCD** : fond navy `#0F1E3D`, segments blancs
- [ ] **ΔET LCD** : fond warm 200, segments red
- [ ] **ΔBT LCD** : fond warm 200, segments navy

### Status bar (messagelabel)
- [ ] Sur fond canvas clair : texte navy 900
- [ ] Sur fond canvas sombre : texte blanc
- [ ] Pas d'écrasement trop rapide des messages critiques (limite : 8s pour push success/fail)

### Chart matplotlib
- [ ] Background canvas warm `#FAF8F4`
- [ ] Grille warm `#E8E3D6`
- [ ] Titre roast en haut : navy `#0F1E3D`
- [ ] Sponsor "sponsored by MySpresso" : warm gray
- [ ] Footer (date / profile / durée / poids) : navy 900
- [ ] Courbe ET : red `#A8392E`
- [ ] Courbe BT : navy `#0F1E3D`
- [ ] Courbe ΔBT (RoR) : warm gray
- [ ] Markers événements (CHARGE/DROP/FCs) : navy + red selon événement

## Dialog MySpresso Settings (Help → MySpresso Settings…)

- [ ] Titre "MySpresso Cloud" en gros (role=dialogTitle, 18px bold)
- [ ] Section "Endpoints" en uppercase avec border-bottom warm
- [ ] Section "Authentication" idem
- [ ] Champ API endpoint : input MySpresso-styled (border warm 400)
- [ ] Champ Web endpoint : idem
- [ ] Checkbox "Enable authentication" : style MySpresso (square 16px)
- [ ] Bouton "Reset to defaults" : outlined warm
- [ ] Bouton **OK** : navy plein (primary)
- [ ] Bouton **Cancel** : outlined warm (secondary)
- [ ] Note "Restart required..." : warm 600 italic

## Dialog Login (Help → Connect MySpresso si auth_enabled=true)

- [ ] Titre window : "MySpresso"
- [ ] Champs email / password : style input MySpresso
- [ ] Bouton **OK** : navy plein
- [ ] Bouton **Cancel** : outlined warm
- [ ] Liens Register / Reset Password en bas

## Dialog Roast Properties (Ctrl+I)

- [ ] QDialog background warm `#FAF8F4` / surface blanche
- [ ] Tabs "Torréfaction / Notes / Événements" : underline rouge sur tab sélectionnée
- [ ] Picker Stock (combobox) : style MySpresso
- [ ] Picker Magasin (combobox) : idem
- [ ] Inputs Poids vert / torréfié : style MySpresso
- [ ] Marqueurs phase (CHARGE/DRY/Cstart/Cend/CCstart/CCend/DROP/COOL) : **gardent leur orange domain-spécifique** (convention métier coffee roasting — non modifié)
- [ ] Bouton **OK** : navy plein
- [ ] Bouton **Cancel** : outlined warm

## Tous les autres dialogs (Curves, Events, Phases, Alarms, Statistics, etc.)

- [ ] Background MySpresso warm 100
- [ ] Inputs (QLineEdit / QComboBox / QSpinBox) : border warm, focus navy
- [ ] Tabs : underline rouge sur sélection
- [ ] Tables (QTableWidget) : header warm 200 uppercase, alternating row warm 100/blanc
- [ ] Scrollbars : warm 400, hover warm 500
- [ ] Bouton OK par défaut : navy plein (via `:default` pseudo-class)
- [ ] Bouton Cancel non-default : outlined warm

## Dark mode (macOS Settings → Appearance → Dark)

- [ ] Canvas background passe à `#16181D`
- [ ] Status bar passe à `#0F1115`
- [ ] Boutons primary : `#243B6B` (navy 500 — légèrement plus clair pour contraste)
- [ ] Boutons danger : `#C66459` (red 400 — idem)
- [ ] Inputs : `#1E2128` avec texte `#F0EDE5`
- [ ] Borders : `#3E444F`
- [ ] Tabs : underline `#D78A82` (red 300 plus clair)
- [ ] Tooltips inversées : texte navy sur fond warm

## Résolutions

- [ ] **1440x900** (référence Mac) : pas de tronquage, le canvas et les LCDs tiennent
- [ ] **1024x600** (Raspberry Pi tactile) : tester aussi si possible

## Modes UI (Config → Mode → ...)

- [ ] **Standard** (défaut) : tous les boutons d'événements visibles
- [ ] **Production** : doit être plus simplifié (à vérifier)
- [ ] **Expert** : tous les menus visibles (Config → Device, Curves, etc.)

## Tests fonctionnels (non régression)

- [ ] Connect MySpresso fonctionne (status bar affiche "Connected to MySpresso")
- [ ] Disconnect MySpresso fonctionne (pas de freeze — bug deadlock corrigé en Phase précédente)
- [ ] Stock picker dans Roast Properties : 35 cafés MySpresso visibles
- [ ] Magasin picker : 7 magasins visibles dont DESKTOP
- [ ] DUMMY device : ON → CHARGE → DROP → push auto fonctionne (status bar "Torréfaction téléchargée…")
- [ ] Bouton manuel Help → "Envoyer la torréfaction sur MySpresso" fonctionne
- [ ] Tests unitaires verts : `pytest test/unitary/plus/` → 16/16

## Smoke commandes

```bash
# Lancer en mode normal
cd src && MYSPRESSO_AUTH_ENABLED=false python artisan.py

# Désactiver le design system (comparer upstream)
MYSPRESSO_STYLE_DISABLED=true python artisan.py

# Vérifier le QSS se charge
python -c "
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from artisanlib.styles import apply_myspresso_stylesheet
apply_myspresso_stylesheet(app)
print('theme:', app.property('theme'))
print('stylesheet size:', len(app.styleSheet()))
"
```

## Limitations connues / hors scope

- **Pacifico script logo MySpresso** : pas bundlée — utilise un fallback dans le QSS pour le hero brand label. Pour l'avoir exactement comme le design mockup, ajouter `Pacifico-Regular.ttf` à `src/fonts/`.
- **Montserrat** : pas bundlée non plus (mauvaise URL Google Fonts). Fallback macOS/Windows OK.
- **Cloud badge widget** : QSS prêt (`QLabel#cloudBadge[connected="true|false"]`) mais aucun widget Artisan ne l'utilise — il faudrait ajouter un QLabel dans la toolbar principale.
- **Icônes SVG MySpresso** : pas livrées par Claude Design (seulement logo.webp). Toolbar matplotlib utilise toujours ses icônes natives.
- **Hero timer 72px JetBrains Mono** : le QSS le prévoit (`QLabel[role="timer"]`) mais le timer Artisan est un `QLCDNumber` (segment display), pas un QLabel. Le QSS sur QLabel n'est pas appliqué. Pour avoir le hero design exact, faudrait remplacer le QLCDNumber par un QLabel — plus invasif.
- **Inline setStyleSheet préservés** : les ~340 inline styles d'Artisan ne sont pas tous patchés. Le QSS global gère les widgets sans style inline. Les boutons CHARGE/DRY/Cstart/etc. dans Roast Properties gardent leur convention orange (lexique métier coffee roasting).
