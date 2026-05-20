# Brief design — Refonte UI d'un logiciel de torréfaction de café

> **Pour qui** : agent / designer externe sans accès au code source.
> **Objectif** : produire les **maquettes**, le **système de design**, et les **assets** d'une refonte visuelle. L'implémentation technique sera faite séparément à partir de tes livrables.

---

## 1. Le produit

**MySpresso Artisan** est un logiciel desktop pour les torréfacteurs de café professionnels. Il sert à :
- Enregistrer en temps réel la courbe de température d'une torréfaction (Charge → Drop)
- Annoter les événements clés (1er crack, 2ème crack, etc.)
- Renseigner le stock consommé (quel café, depuis quel magasin, quel poids vert / torréfié)
- Synchroniser tout ça avec une plateforme web interne (ZABAWA / MySpresso) qui gère l'inventaire, le planning et l'historique.

C'est un fork rebrandé d'un logiciel open-source historique appelé **Artisan** (look "scientifique des années 2010"). On veut moderniser tout en respectant la **réalité du métier**.

### Profil utilisateur
- Opérateur torréfacteur dans un atelier
- Souvent debout devant une machine bruyante, parfois mains chargées (sale, chaude, en mouvement)
- Doit pouvoir lire l'écran à 1.5-2 m de distance
- Workflow : ouvrir l'app → choisir café + magasin → démarrer le scope → cliquer "Charge" au moment où il verse les grains → surveiller la courbe → cliquer "Drop" en fin → renseigner poids → sauvegarder

### Plateformes cibles
- Mac (référence — macOS Sonoma+)
- Windows 10/11
- Linux (Ubuntu 22+)
- Raspberry Pi avec écran tactile (parfois en atelier, fixé sur mur)

### Stack technique (pour info, pas à designer)
- Application **PyQt6** (Python desktop)
- Graphique de température en **matplotlib**
- Pas de web, pas de mobile, pas d'app native — desktop uniquement
- Styling via **QSS** (sous-ensemble de CSS adapté à Qt)

---

## 2. Identité visuelle MySpresso à appliquer

| Élément | Valeur |
|---|---|
| Palette primaire | **Navy** (deep blue, profond, sérieux) |
| Accent | **Red** (sobre, brique-rouge plutôt que pétant) |
| Neutrals | Tons chauds (off-white, beige clair, gris doux — pas du blanc clinique) |
| Typo | **Montserrat** (toutes graisses : Regular / Medium / SemiBold / Bold) |
| Forme | **Cards carrées** (border-radius 0 ou très faible — 2-4px max), ombres **subtiles** |
| Ton | Minimal, professionnel, industrie café spécialité |
| À éviter | Glassmorphism / gradients agressifs / neon / shapes rondes |

Si tu as déjà vu Modbar, La Marzocco, ou Slayer Espresso pour l'esthétique de la coffee industry — c'est cette direction. Sobre, robuste, premium.

---

## 3. État actuel — captures et pain points

(Capture du canvas principal jointe en annexe — `screenshots/current-canvas.png`.)

### 10 points de douleur identifiés

| # | Problème | Description visuelle |
|---|---|---|
| 1 | **Logo / sponsor concurrent affiché** | Coin haut-droit affiche "sponsorisé par artisan.plus" (le SaaS upstream, qu'on a remplacé par MySpresso). Doit disparaître ou devenir "MySpresso". |
| 2 | **Identité visuelle inexistante** | Look Qt natif macOS/Win/Linux par défaut — aucune cohérence visuelle MySpresso. Aucune couleur de marque visible. |
| 3 | **Boutons d'action hétérogènes** | 3 boutons en haut-droite (REINITIALISER, ON, DEBUT) + ~8 boutons en bas (Charge, Drop, FCs, FCe, SCs, SCe, Cool, Reset). Tailles inégales, couleurs bleues hardcodées sans système. |
| 4 | **Status bar volatile** | La barre de statut affiche les messages "Roast uploadé", "Profil sauvegardé"… mais chaque nouveau message écrase l'ancien en moins de 2 secondes. Impossible de vérifier qu'un événement critique (push cloud) a réussi. |
| 5 | **Hiérarchie typographique plate** | Titre du roast, timer central, valeurs des axes, labels des boutons — tout à peu près le même poids visuel. Pas de scale claire. |
| 6 | **Toolbar du graphique brute** | Icônes home/back/forward/move/zoom standard matplotlib, non intégrées au reste. |
| 7 | **Dialogs (Propriétés, Settings) en style Qt natif** | Aucune cohérence avec une éventuelle identité MySpresso. |
| 8 | **Feedback de connexion cloud invisible** | Une icône change d'état quand l'app se connecte au backend MySpresso, mais ça n'est pas évident. Un badge "MySpresso · connecté" ou similaire manquerait. |
| 9 | **Pas de différenciation par mode UI** | L'app prévoit trois modes (Production / Standard / Expert) mais visuellement ils sont identiques. |
| 10 | **Tooltips mélangés FR/EN** | App en français mais certains tooltips et messages techniques restent en anglais. |

---

## 4. Objectifs

### MUST-HAVE — sans ça pas de release

- **M1** Tous les visuels affichent **"MySpresso"**, jamais "artisan.plus".
- **M2** Palette MySpresso (navy + red + neutrals chauds) sur : header, toolbar principale, status bar, boutons CHARGE / DROP / Connect cloud, headers des dialogs principales.
- **M3** **Hiérarchie typographique** claire en 3-4 niveaux :
  - H1 : titre de la torréfaction en cours
  - H2 : sections (Stock, Magasin, Poids, etc.)
  - Body : labels, métadonnées
  - Mono / Tabular : valeurs numériques (timer, températures, poids)
- **M4** **Status bar non-volatile** pour les événements critiques (push cloud success/fail) — soit zone dédiée, soit log inline persistant ≥ 8 secondes.
- **M5** Indicateur de **connexion cloud** persistant et lisible (badge ou texte explicite).

### SHOULD-HAVE — release polishée

- **S1** Système de tokens centralisé (palette + typo + spacing) en format consommable par le dev (JSON ou table claire dans la doc design).
- **S2** **Dark mode** cohérent et appliqué partout (l'app détecte déjà le système).
- **S3** **Icônes SVG** MySpresso essentielles (toolbar : home, settings, cloud, schedule, upload) — pas besoin de redessiner les 100+ icônes secondaires.
- **S4** Dialog **"Propriétés de la torréfaction"** redesigné (le plus utilisé après le canvas — sections aérées, picker café/magasin plus visuel).

### NICE-TO-HAVE — si scope le permet

- **N1** Mockup d'un mode "Production" simplifié : 3 boutons géants (Charger / Démarrer / Décharger), tout le reste caché. Pour les opérateurs qui ne veulent que l'essentiel.
- **N2** Animations subtiles sur les transitions d'état (CHARGE → DROP, connect / disconnect).
- **N3** Theme MySpresso sélectionnable depuis le menu Config → Themes existant.

---

## 5. Contraintes techniques (pour cadrer le design)

### Stack que le dev utilisera pour implémenter
- **QSS** (Qt Style Sheets) — sous-ensemble de CSS supportant `color`, `background`, `border`, `padding`, `margin`, `font`, et la plupart des sélecteurs (`QPushButton`, `#objectName`, `:hover`, `:focus`, `[property=value]`). **Pas de** flexbox, pas de grid, pas de pseudo-éléments complexes.
- Les polices custom doivent pouvoir être bundlées avec l'app (fichiers `.ttf` ou `.otf` chargeables via `QFontDatabase.addApplicationFont()`).
- Les icônes peuvent être SVG ou PNG (Qt supporte les deux). SVG préférable pour le scaling sur écrans Retina + Raspberry Pi.

### À NE PAS designer
- Refonte structurelle des menus / layout des widgets (le dev ne peut pas restructurer le code).
- Une web app, une mobile app, une PWA — c'est du desktop pur.
- Refonte du graphique matplotlib lui-même (juste sa palette et fonts).
- Tous les dialogs secondaires (Alarms, Designer, Comparator, Energy, Phidget…) — restent en style Qt natif pour cette release. **Focus** : canvas principal + Propriétés + Settings.

### À respecter
- **Cross-platform** : design doit fonctionner sur macOS / Windows / Linux / Raspberry Pi (tactile). Pas de hover-only.
- **Accessibilité** WCAG AA minimum (contraste 4.5:1 sur texte body, 3:1 sur texte large).
- **Locale française** par défaut, mais structure i18n préservée — donc les boutons doivent supporter des labels plus longs qu'en anglais (ex: "REINITIALISER" vs "RESET").
- **Modes UI** : Standard par défaut (= l'opérateur typique), Production = simplifié, Expert = tout visible.

---

## 6. Livrables attendus

| # | Livrable | Format |
|---|---|---|
| **L1** | **Maquettes hi-fi** du canvas principal | Figma / PDF / PNG @2x, mode clair + sombre |
| **L2** | **Maquettes hi-fi** du dialog Propriétés de la torréfaction | Figma / PDF / PNG @2x, mode clair + sombre |
| **L3** | **Maquettes hi-fi** du dialog Settings MySpresso (URL endpoints, toggle auth) | Figma / PDF / PNG @2x |
| **L4** | **Design system MySpresso** documenté | Markdown ou Figma — palette complète (primary, semantic, neutral) avec hex + WCAG ratios, typo scale (4 niveaux + line-heights), spacing scale (8 ou 4-pt grid), ombres, états des composants (hover/active/disabled) |
| **L5** | **Tokens** en format machine-lisible | JSON ou YAML — pour que le dev les transpose en QSS / Python facilement. Structure trois couches (primitive → semantic → component) appréciée mais pas obligatoire. |
| **L6** | **Icônes essentielles** | SVG (et @2x PNG si l'agent préfère bitmap) — toolbar : home, settings, cloud-connect, cloud-disconnect, schedule, upload-roast. Style cohérent : line-icons fins, navy par défaut. |
| **L7** | **Fonts** | Lien vers la source Montserrat (Google Fonts) ou fichiers `.ttf` directement. |
| **L8** | **Avant / après** | Captures comparatives (screenshot actuel à gauche, mockup à droite) pour chaque écran refait. |
| **L9** | **Guide d'application QSS** | Pour chaque composant clé, snippet QSS commenté (boutons primaires/secondaires/destructifs, status bar, header, dialog), prêt à coller dans le code. |

Si tu utilises Figma : un fichier partagé avec composants nommés conventionnellement (`Button/Primary/Default`, `Button/Primary/Hover`, etc.) idéal.

---

## 7. Critères d'acceptation

Le livrable est considéré complet quand :

1. ✅ Trois maquettes hi-fi finies (canvas + Propriétés + Settings) en mode clair + sombre.
2. ✅ Aucune mention "artisan.plus" dans les maquettes.
3. ✅ La palette navy + red + neutrals chauds est visible et cohérente sur les 3 écrans.
4. ✅ Quatre niveaux de typographie distincts visibles (H1 timer + titre, H2 sections, body, mono pour chiffres).
5. ✅ Un design system doc lisible et autosuffisant (un dev qui n'a jamais vu MySpresso peut implémenter à partir de ce doc).
6. ✅ Tokens livrés en JSON / YAML / table claire (palette + typo + spacing + ombres).
7. ✅ Au moins 6 icônes SVG essentielles fournies, style cohérent.
8. ✅ Dark mode mockup pour les 3 écrans.
9. ✅ Snippets QSS prêts à coller pour les 5 composants prioritaires (bouton primary, bouton danger, status bar, header window, dialog).
10. ✅ Avant/après PNG pour chaque écran.

---

## 8. Hors périmètre

- **Implémentation du code** — c'est le dev qui prendra tes maquettes et tokens pour patcher le QSS et les `setStyleSheet` dans le code Python.
- **Refonte de TOUS les dialogs** (40+ existent) — focus sur 3 écrans clés.
- **Branding logo / charte graphique générale MySpresso** — supposée déjà définie ailleurs, tu n'as qu'à l'**appliquer** sur ce produit desktop.
- **Animations complexes** — Qt supporte les transitions CSS limitées, donc reste sur du simple (fade, color shift).
- **i18n** : pas ton chantier, traductions FR/EN/etc. gérées séparément.
- **Print** / **mobile companion** : ce produit est desktop only pour cette release.

---

## 9. Process suggéré

1. **Briefing** : tu reçois ce doc + la capture du canvas actuel + (idéalement) un mood-board MySpresso si existant.
2. **Wireframes basse-fi** (1-2 jours) — confirmer que la nouvelle structure visuelle te semble cohérente avant de partir en hi-fi.
3. **Design system** (palette, typo, spacing) parallèle aux wireframes.
4. **Hi-fi mockups** pour les 3 écrans, mode clair + sombre.
5. **Tokens + QSS snippets** pour passer au dev.
6. **Itération** : 1-2 rounds de revue avec moi (ou l'équipe MySpresso).
7. **Handoff au dev** : assets bundle (Figma share link + ZIP icônes + JSON tokens + doc markdown).

---

## 10. Questions probables que tu te poseras

**Q** : Est-ce que je peux changer la position des widgets ?
**R** : Non, juste l'habillage. Les widgets, leurs positions, et leurs interactions restent identiques.

**Q** : Est-ce que je peux proposer des animations Lottie / vidéo ?
**R** : Non, Qt ne supporte pas Lottie. Reste sur des transitions CSS basiques.

**Q** : Quelle taille d'écran cible ?
**R** : Référence : MacBook Pro 13'' Retina (1440x900 logique, 2880x1800 physique). Doit aussi tenir sur Raspberry Pi avec écran 7'' tactile (1024x600 ou 1280x800). Donc design **scalable** mais avec une référence 1440x900.

**Q** : Y a-t-il un guide brand MySpresso existant ?
**R** : Si tu reçois un brand book, suis-le. Sinon les indications du §2 + l'esthétique coffee specialty premium suffisent.

**Q** : Combien de variantes de boutons ?
**R** : Au minimum 3 : Primary (action principale comme CHARGE), Secondary (actions neutres comme RESET), Destructive (annuler, arrêter). Plus les états hover / pressed / disabled / focused pour chacun.

**Q** : Le timer central — 0:06 / 236.0°F — doit-il rester aussi gros ?
**R** : OUI ou plus. C'est l'info la plus consultée en pleine torréfaction. Suggestion : timer en H1 énorme (60-80px), température en H2 (32-40px) juste en dessous.

---

## 11. Annexes

- `screenshots/current-canvas.png` — capture actuelle du canvas principal (à fournir séparément avec ce brief)
- `screenshots/current-properties.png` — capture du dialog Propriétés (à fournir si tu veux les fichier source)
- `screenshots/current-settings.png` — capture du dialog Settings MySpresso (à fournir si tu veux les fichier source)
- Brand guidelines MySpresso (si existant, joindre)
