"""
MySpresso Artisan — design tokens (single source of truth).

Tokens produced from the Claude Design (claude.ai/design) handoff
2026-05-20. Three-layer structure: primitive (raw values) -> semantic
(role-based, light + dark) -> component (mapping for specific widgets).

Import from this module instead of hardcoding colors. The QSS
stylesheet `styles/myspresso.qss` is a TEMPLATE: it references these
tokens as `@TOKEN_NAME@` placeholders, substituted at load time by
`styles.load_qss()`. Change a value here and the whole app follows —
never hardcode a hex in the QSS or in a widget.
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

# Feedback states (dark)
DARK_SUCCESS_FG: Final[str] = '#6FB78D'
DARK_SUCCESS_BG: Final[str] = '#1F2D24'
DARK_ERROR_BG: Final[str] = '#2D1E1B'

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

# ── RUNTIME THEME SELECTION ────────────────────────────────────────────────

class SemanticTokens:
    """Role-based colours resolved for one theme (light or dark).

    Widgets that style themselves in code (the myspresso_* modules)
    call ``semantic(dark)`` once and read roles from the result instead
    of hardcoding light hex values — that is what makes them dark-mode
    aware for free.
    """

    __slots__ = ('dark', 'bg', 'bg_raised', 'bg_sunken', 'surface', 'surface_alt',
                 'border', 'border_strong', 'fg_primary', 'fg_secondary',
                 'fg_muted', 'fg_on_brand', 'fg_accent', 'brand', 'accent',
                 'chart_et', 'chart_bt', 'chart_delta',
                 'success_fg', 'success_bg', 'error_fg', 'error_bg')

    def __init__(self, dark: bool) -> None:
        self.dark = dark
        if dark:
            self.bg = DARK_BG
            self.bg_raised = DARK_BG_RAISED
            self.bg_sunken = DARK_BG_SUNKEN
            self.surface = DARK_SURFACE
            self.surface_alt = DARK_SURFACE_ALT
            self.border = DARK_BORDER
            self.border_strong = DARK_BORDER_STRONG
            self.fg_primary = DARK_FG_PRIMARY
            self.fg_secondary = DARK_FG_SECONDARY
            self.fg_muted = DARK_FG_MUTED
            self.fg_on_brand = DARK_FG_ON_BRAND
            self.fg_accent = DARK_FG_ACCENT
            self.brand = DARK_BRAND
            self.accent = DARK_ACCENT
            # chart colours lightened for a dark canvas
            self.chart_et = RED_300
            self.chart_bt = NAVY_200
            self.chart_delta = DARK_FG_MUTED
            self.success_fg = DARK_SUCCESS_FG
            self.success_bg = DARK_SUCCESS_BG
            self.error_fg = RED_300
            self.error_bg = DARK_ERROR_BG
        else:
            self.bg = LIGHT_BG
            self.bg_raised = LIGHT_BG_RAISED
            self.bg_sunken = LIGHT_BG_SUNKEN
            self.surface = LIGHT_SURFACE
            self.surface_alt = LIGHT_SURFACE_ALT
            self.border = LIGHT_BORDER
            self.border_strong = LIGHT_BORDER_STRONG
            self.fg_primary = LIGHT_FG_PRIMARY
            self.fg_secondary = LIGHT_FG_SECONDARY
            self.fg_muted = LIGHT_FG_MUTED
            self.fg_on_brand = LIGHT_FG_ON_BRAND
            self.fg_accent = LIGHT_FG_ACCENT
            self.brand = LIGHT_BRAND
            self.accent = LIGHT_ACCENT
            self.chart_et = CHART_TE
            self.chart_bt = CHART_BT
            self.chart_delta = CHART_DELTA
            self.success_fg = SUCCESS_FG
            self.success_bg = SUCCESS_BG
            self.error_fg = ERROR_FG
            self.error_bg = ERROR_BG


def semantic(dark: bool) -> SemanticTokens:
    """Semantic tokens for the requested theme."""
    return SemanticTokens(dark)


# ── LEGACY ALIASES ─────────────────────────────────────────────────────────
# Match variable names used in original Artisan main.py (line 239-240) so we
# can migrate existing button-color call-sites with minimal churn.

light_blue: Final[str] = NAVY_500       # was '#4c97c3'
dark_blue: Final[str] = NAVY_700        # was '#3979ae'
