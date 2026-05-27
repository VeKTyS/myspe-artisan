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
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


_ICON_DIR = pathlib.Path(__file__).parent.parent / 'icons' / 'myspresso'
_LOGO_PATH = _ICON_DIR / 'logo.webp'


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
        self._nav_divider.setStyleSheet('background-color: #E8E3D6;')
        layout.addWidget(self._nav_divider)
        layout.addLayout(self._nav_slot)

        layout.addStretch()

        # ── Cloud connection badge ──────────────────────────────────────────
        self._cloud_badge = QLabel()
        self._cloud_badge.setObjectName('cloudBadge')
        self._cloud_badge.setTextFormat(Qt.TextFormat.RichText)
        self._cloud_badge.setProperty('connected', 'false')
        layout.addWidget(self._cloud_badge)

        # ── UI mode badge — outlined pill (matches the v2 mockup) ───────────
        self._mode_badge = QLabel('·  MODE STANDARD')
        self._mode_badge.setObjectName('modeBadge')
        self._mode_badge.setStyleSheet(
            'QLabel#modeBadge {'
            ' color: #4E4A44;'
            ' background-color: transparent;'
            ' border: 1px solid #D4CCBA;'
            ' border-radius: 12px;'
            ' padding: 4px 12px;'
            ' font-size: 10px; font-weight: 700;'
            ' letter-spacing: 0.05em;'
            '}'
        )
        layout.addWidget(self._mode_badge)

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

    # ── Wiring helpers ──────────────────────────────────────────────────────

    def set_connected(self, connected: bool) -> None:
        """Render the cloud badge with a coloured dot independent of text.

        We use HTML so the leading status dot stays its semantic colour
        (success-green / error-red) regardless of the badge's text colour —
        the v2 mockup shows a green dot next to navy-dark text.
        """
        dot_colour = '#2DAE6D' if connected else '#A8392E'
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
