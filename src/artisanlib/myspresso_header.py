"""
MySpresso Artisan — top header strip.

Sits above the existing main_widget layout (level1frame + midlayout).
Hosts the MySpresso brand logo, cloud connection badge, and UI mode
badge. Designed to be additive — it does NOT touch any existing
widget. Wired by `MySpressoHeader.wire(app_window)` once after the
main window is fully constructed.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from artisanlib.styles import current_semantic_tokens

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


_ICON_DIR = pathlib.Path(__file__).parent.parent / 'icons' / 'myspresso'
# Prefer PNG (universally supported by Qt on all platforms including Windows).
# Fall back to webp for legacy builds that only ship that asset.
_LOGO_PATH = next(
    (p for p in (_ICON_DIR / 'logo.png', _ICON_DIR / 'logo.webp') if p.is_file()),
    _ICON_DIR / 'logo.png',
)


class MySpressoHeader(QFrame):
    """Top strip: [logo] [stretch] [cloud badge] [mode badge]."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysHeader')
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Slight bump from 56→72 so hosted action buttons fit comfortably.
        self.setFixedHeight(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # ── Logo ────────────────────────────────────────────────────────────
        # Slot for the re-parented matplotlib navtoolbar (home/back/forward/
        # pan/zoom) so it sits inside the brand header per the v2 mockup.
        self._nav_slot = QHBoxLayout()
        self._nav_slot.setSpacing(2)
        self._nav_slot.setContentsMargins(0, 0, 0, 0)

        self._logo = QLabel()
        if _LOGO_PATH.is_file():
            pm = QPixmap(str(_LOGO_PATH))
            if not pm.isNull():
                self._logo.setPixmap(
                    pm.scaledToHeight(40, Qt.TransformationMode.SmoothTransformation)
                )
        else:
            # Fallback when logo asset is missing — use the script-style label
            self._logo.setText('MySpresso')
            self._logo.setObjectName('brand')
        layout.addWidget(self._logo)
        # Thin vertical divider between logo and navtoolbar (per v2 mockup).
        self._nav_divider = QLabel()
        self._nav_divider.setFixedWidth(1)
        self._nav_divider.setFixedHeight(24)
        layout.addWidget(self._nav_divider)
        layout.addLayout(self._nav_slot)

        layout.addStretch()

        # ── Cloud connection badge ──────────────────────────────────────────
        self._connected: bool = False
        self._cloud_badge = QLabel()
        self._cloud_badge.setObjectName('cloudBadge')
        self._cloud_badge.setTextFormat(Qt.TextFormat.RichText)
        self._cloud_badge.setProperty('connected', 'false')
        # Force a tight height — QSS `padding` alone wasn't pulling the box
        # down to hug the text on every Qt platform (the QLabel's natural
        # sizeHint includes the font's full line height + leading).
        self._cloud_badge.setFixedHeight(22)
        layout.addWidget(self._cloud_badge)

        # ── UI mode badge — square outlined card (MySpresso DA) ─────────────
        self._mode_badge = QLabel('·  MODE STANDARD')
        self._mode_badge.setObjectName('modeBadge')
        self._mode_badge.setFixedHeight(22)
        layout.addWidget(self._mode_badge)

        # MySpresso DA: subtle drop shadow on both badges so they "lift" off
        # the warm header background (cards quasi-carrés + ombres subtiles).
        # Colours are (re-)applied in _apply_theme().
        self._badge_shadows: list[QGraphicsDropShadowEffect] = []
        for _badge in (self._cloud_badge, self._mode_badge):
            _shadow = QGraphicsDropShadowEffect(self)
            _shadow.setBlurRadius(8)
            _shadow.setOffset(0, 1)
            _badge.setGraphicsEffect(_shadow)
            self._badge_shadows.append(_shadow)

        # ── Slot for re-parented action buttons (RESET/ON/DÉBUT) ────────────
        # Buttons are added via host_action_buttons() once the ApplicationWindow
        # has finished constructing them. Adding to this layout implicitly
        # removes them from the original level1layout.
        layout.addSpacing(8)
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(6)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._actions_layout)

        self._layout = layout
        self._apply_theme()

    # ── Theming ─────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        """(Re-)apply all colour-bearing styles from the semantic tokens."""
        tok = current_semantic_tokens()
        self._nav_divider.setStyleSheet(f'background-color: {tok.border};')
        # Subtle badge lift: navy-tinted in light mode, plain black in dark
        # (a coloured glow reads wrong on a dark ground).
        shadow_colour = QColor(0, 0, 0, 70) if tok.dark else QColor(15, 30, 61, 28)
        for _shadow in self._badge_shadows:
            _shadow.setColor(shadow_colour)
        # Re-render the cloud badge so the status dot picks up theme colours.
        self.set_connected(self._connected)

    def restyle(self) -> None:
        """Public hook: re-resolve tokens after a light/dark switch."""
        self._apply_theme()

    # ── Wiring helpers ──────────────────────────────────────────────────────

    def set_connected(self, connected: bool) -> None:
        """Render the cloud badge with a coloured dot independent of text.

        We use HTML so the leading status dot stays its semantic colour
        (success-green / error-red) regardless of the badge's text colour —
        the v2 mockup shows a green dot next to navy-dark text.
        """
        self._connected = connected
        tok = current_semantic_tokens()
        dot_colour = tok.success_fg if connected else tok.accent
        label = 'CONNECTÉ' if connected else 'DÉCONNECTÉ'
        self._cloud_badge.setText(
            f'<span style="color:{dot_colour};">●</span>'
            f'&nbsp;&nbsp;MYSPRESSO · {label}'
        )
        self._cloud_badge.setProperty('connected', 'true' if connected else 'false')
        # Re-polish to apply the [connected="..."] property selector change
        style = self._cloud_badge.style()
        if style is not None:
            style.unpolish(self._cloud_badge)
            style.polish(self._cloud_badge)

    def set_mode(self, mode_label: str) -> None:
        # Small middle-dot before the mode label matches the mockup.
        self._mode_badge.setText(f'·  MODE {mode_label.upper()}')

    def host_action_buttons(
        self,
        reset_btn: QPushButton | None = None,
        onoff_btn: QPushButton | None = None,
        startstop_btn: QPushButton | None = None,
        control_btn: QPushButton | None = None,
    ) -> None:
        """Re-parent existing QPushButton widgets into the header and attach
        MySpresso line-icon QIcons (from src/icons/myspresso/).

        Using setIcon instead of inline unicode glyphs lets the icon survive
        Artisan's state-driven setText calls (ON ↔ OFF, START ↔ STOP) AND
        keeps its native colour (e.g. the ON dot stays green even when the
        button background is outlined warm).
        """
        icon_size = QSize(14, 14)
        order: list[tuple[QPushButton | None, str | None]] = [
            (reset_btn, 'reset.svg'),
            (onoff_btn, 'dot-green.svg'),
            (startstop_btn, 'play.svg'),
            (control_btn, None),
        ]
        for btn, icon_name in order:
            if btn is None:
                continue
            btn.setMinimumHeight(36)
            btn.setMaximumHeight(48)
            btn.setMinimumWidth(96)
            if icon_name is not None:
                p = _ICON_DIR / icon_name
                if p.is_file():
                    btn.setIcon(QIcon(str(p)))
                    btn.setIconSize(icon_size)
            self._actions_layout.addWidget(btn)

    def host_navtoolbar(self, ntb: QWidget | None) -> None:
        """Re-parent the matplotlib navtoolbar widget into the header slot.

        ``ntb`` is the existing ``VMToolbar`` instance — a QToolBar subclass.
        Adding it to ``_nav_slot`` removes it from its previous layout
        (level1frame) automatically.
        """
        if ntb is None:
            return
        try:
            ntb.setMaximumHeight(40)
            ntb.setStyleSheet(
                'QToolBar { background: transparent; border: none;'
                ' spacing: 2px; padding: 0px; }'
            )
        except Exception:  # noqa: BLE001
            pass
        self._nav_slot.addWidget(ntb)


    def wire(self, app_window: ApplicationWindow) -> None:
        """Connect to ApplicationWindow signals to keep badges in sync."""
        # Initial state — `plus_account` is set when connected.
        try:
            self.set_connected(app_window.plus_account is not None)
        except AttributeError:
            pass
        # Mode label from app_window.ui_mode (enum).
        try:
            mode_name = getattr(app_window.ui_mode, 'name', 'standard')
            self.set_mode(mode_name)
        except AttributeError:
            pass
        # Move RESET/ON/DÉBUT/CONTROL into the header strip.
        try:
            self.host_action_buttons(
                reset_btn=getattr(app_window, 'buttonRESET', None),
                onoff_btn=getattr(app_window, 'buttonONOFF', None),
                startstop_btn=getattr(app_window, 'buttonSTARTSTOP', None),
                control_btn=getattr(app_window, 'buttonCONTROL', None),
            )
        except (AttributeError, RuntimeError):
            pass
        # Move the matplotlib navtoolbar into the header strip.
        try:
            self.host_navtoolbar(getattr(app_window, 'ntb', None))
        except (AttributeError, RuntimeError):
            pass
