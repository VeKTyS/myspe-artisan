"""
MySpresso Artisan — design tokens (single source of truth).

Tokens produced from the Claude Design (claude.ai/design) handoff
2026-05-20. Three-layer structure: primitive (raw values) -> semantic
(role-based, light + dark) -> component (mapping for specific widgets).

Import from this module instead of hardcoding colors. The QSS
stylesheet `styles/myspresso.qss` mirrors these values; keep them in
sync if you change one side.
"""

from typing import Final

# ── PRIMITIVES ─────────────────────────────────────────────────────────────

# Navy ramp (brand primary)
NAVY_900: Final[str] = '#070D1F'
NAVY_800: Final[str] = '#0A1733'
NAVY_700: Final[str] = '#0F1E3D'  # brand primary
NAVY_600: Final[str] = '#172A52'
NAVY_500: Final[str] = '#243B6B'
NAVY_400: Final[str] = '#3E5685'
NAVY_300: Final[str] = '#6478A0'
NAVY_200: Final[str] = '#A2B0C8'
NAVY_100: Final[str] = '#D0D8E4'
NAVY_050: Final[str] = '#E8ECF2'

# Red brick (accent / destructive)
RED_900: Final[str] = '#5C1F18'
RED_800: Final[str] = '#7A2A21'
RED_700: Final[str] = '#8E2F26'
RED_600: Final[str] = '#A8392E'  # brand red
RED_500: Final[str] = '#B8473C'
RED_400: Final[str] = '#C66459'
RED_300: Final[str] = '#D78A82'
RED_200: Final[str] = '#E8B5AF'
RED_100: Final[str] = '#F2D6D2'
RED_050: Final[str] = '#FAEDEB'

# Warm neutrals (warm off-white -> graphite)
WARM_050: Final[str] = '#FDFCF9'
WARM_100: Final[str] = '#FAF8F4'  # canvas / app background
WARM_200: Final[str] = '#F2EFE7'  # surface alt / sunken
WARM_300: Final[str] = '#E8E3D6'  # border subtle
WARM_400: Final[str] = '#D4CCBA'
WARM_500: Final[str] = '#A8A092'
WARM_600: Final[str] = '#7A736A'
WARM_700: Final[str] = '#4E4A44'
WARM_800: Final[str] = '#2E2B27'
WARM_900: Final[str] = '#191816'

# Semantic chart colors (matplotlib mapping)
CHART_TE: Final[str] = '#A8392E'     # bean / environmental temp (ET)
CHART_BT: Final[str] = '#0F1E3D'     # drum temp (BT/TG)
CHART_DELTA: Final[str] = '#7A736A'  # ΔTG (rate of rise)
CHART_FC: Final[str] = '#C7873A'     # first crack ochre
CHART_SC: Final[str] = '#5C4A2E'     # second crack roast brown

# Feedback states
SUCCESS_FG: Final[str] = '#1F6B47'
SUCCESS_BG: Final[str] = '#E0EFE5'
WARNING_FG: Final[str] = '#8A5A0F'
WARNING_BG: Final[str] = '#F7E9CC'
ERROR_FG: Final[str] = '#8E2F26'
ERROR_BG: Final[str] = '#F2D6D2'
INFO_FG: Final[str] = '#0F1E3D'
INFO_BG: Final[str] = '#E8ECF2'

# ── SEMANTIC (LIGHT) ───────────────────────────────────────────────────────

LIGHT_BG: Final[str] = WARM_100
LIGHT_BG_RAISED: Final[str] = '#FFFFFF'
LIGHT_BG_SUNKEN: Final[str] = WARM_200
LIGHT_BG_INVERSE: Final[str] = NAVY_700

LIGHT_SURFACE: Final[str] = '#FFFFFF'
LIGHT_SURFACE_ALT: Final[str] = WARM_200

LIGHT_BORDER: Final[str] = WARM_300
LIGHT_BORDER_STRONG: Final[str] = WARM_400
LIGHT_BORDER_FOCUS: Final[str] = NAVY_700

LIGHT_FG_PRIMARY: Final[str] = NAVY_900
LIGHT_FG_SECONDARY: Final[str] = WARM_700
LIGHT_FG_MUTED: Final[str] = WARM_600
LIGHT_FG_ON_BRAND: Final[str] = '#FFFFFF'
LIGHT_FG_ACCENT: Final[str] = RED_600
LIGHT_FG_LINK: Final[str] = NAVY_600

LIGHT_BRAND: Final[str] = NAVY_700
LIGHT_ACCENT: Final[str] = RED_600

# ── SEMANTIC (DARK) ────────────────────────────────────────────────────────

DARK_BG: Final[str] = '#16181D'
DARK_BG_RAISED: Final[str] = '#1E2128'
DARK_BG_SUNKEN: Final[str] = '#0F1115'
DARK_BG_INVERSE: Final[str] = WARM_100

DARK_SURFACE: Final[str] = '#1E2128'
DARK_SURFACE_ALT: Final[str] = '#262A33'

DARK_BORDER: Final[str] = '#2E333C'
DARK_BORDER_STRONG: Final[str] = '#3E444F'
DARK_BORDER_FOCUS: Final[str] = '#7A8FB8'

DARK_FG_PRIMARY: Final[str] = '#F0EDE5'
DARK_FG_SECONDARY: Final[str] = '#B4ADA0'
DARK_FG_MUTED: Final[str] = '#7E7A72'
DARK_FG_ON_BRAND: Final[str] = '#FFFFFF'
DARK_FG_ACCENT: Final[str] = '#D78A82'
DARK_FG_LINK: Final[str] = '#A2B0C8'

DARK_BRAND: Final[str] = NAVY_500
DARK_ACCENT: Final[str] = RED_400

# ── TYPOGRAPHY ─────────────────────────────────────────────────────────────

FONT_SANS: Final[str] = '"Montserrat", -apple-system, "Segoe UI", sans-serif'
FONT_MONO: Final[str] = (
    '"JetBrains Mono", "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace'
)
FONT_SERIF: Final[str] = '"Source Serif Pro", Georgia, serif'

FONT_SIZE_CAPTION: Final[int] = 11
FONT_SIZE_BODY: Final[int] = 13
FONT_SIZE_SECTION: Final[int] = 13
FONT_SIZE_TITLE: Final[int] = 18
FONT_SIZE_H1: Final[int] = 26
FONT_SIZE_TEMP: Final[int] = 32
FONT_SIZE_TIMER: Final[int] = 72

WEIGHT_REGULAR: Final[int] = 400
WEIGHT_MEDIUM: Final[int] = 500
WEIGHT_SEMIBOLD: Final[int] = 600
WEIGHT_BOLD: Final[int] = 700

# ── SPACING (4pt grid) ─────────────────────────────────────────────────────

SPACE_1: Final[int] = 2
SPACE_2: Final[int] = 4
SPACE_3: Final[int] = 6
SPACE_4: Final[int] = 8
SPACE_5: Final[int] = 12
SPACE_6: Final[int] = 16
SPACE_7: Final[int] = 20
SPACE_8: Final[int] = 24
SPACE_9: Final[int] = 32
SPACE_10: Final[int] = 40
SPACE_11: Final[int] = 48
SPACE_12: Final[int] = 64

# ── RADIUS / ELEVATION ─────────────────────────────────────────────────────

RADIUS_NONE: Final[int] = 0
RADIUS_SM: Final[int] = 2  # default for cards & buttons (MySpresso "quasi-square")
RADIUS_MD: Final[int] = 4
RADIUS_LG: Final[int] = 6

# Elevation: QSS doesn't support box-shadow, so these are documentation only.
# For real shadow effects, use QGraphicsDropShadowEffect on the widget.
ELEVATION_CARD = '0 1px 0 rgba(15,30,61,0.04), 0 1px 2px rgba(15,30,61,0.06)'
ELEVATION_DROPDOWN = (
    '0 6px 16px rgba(15,30,61,0.08), 0 2px 4px rgba(15,30,61,0.06)'
)
ELEVATION_MODAL = '0 24px 48px rgba(15,30,61,0.18), 0 2px 8px rgba(15,30,61,0.08)'

# ── LEGACY ALIASES ─────────────────────────────────────────────────────────
# Match variable names used in original Artisan main.py (line 239-240) so we
# can migrate existing button-color call-sites with minimal churn.

light_blue: Final[str] = NAVY_500       # was '#4c97c3'
dark_blue: Final[str] = NAVY_700        # was '#3979ae'
