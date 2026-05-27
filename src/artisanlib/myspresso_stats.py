"""
MySpresso Artisan — slider stats strip.

A compact horizontal panel mirroring the four event-slider values
(typically Burner / Air / Drum / Fan, but names come from
ApplicationWindow.qmc.etypes since they are user-configurable).
Read-only: it never writes to eventslidervalues, only reads.

Polls every 500 ms via QTimer. Cheap: only updates labels when the
displayed string actually changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


class MySpressoStatsStrip(QFrame):
    """Compact single-line stats row matching the v2 mockup.

    Renders as: ``Burner 62% · Drum 58 RPM · Air OUVERT`` (muted gray with
    bold values) — meant to sit on the right of the event button bar.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysStatsStrip')
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(28)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 4, 20, 4)
        root.setSpacing(0)
        root.addStretch()

        # Single QLabel rendering rich HTML for the four slider readouts so
        # we can mix muted labels with bold tabular values inline.
        self._line = QLabel('—')
        self._line.setTextFormat(Qt.TextFormat.RichText)
        self._line.setStyleSheet(
            'font-family: "JetBrains Mono"; font-size: 12px; color: #7A736A;'
        )
        root.addWidget(self._line)

        self._aw: ApplicationWindow | None = None
        self._refresh = QTimer(self)
        self._refresh.setInterval(500)
        self._refresh.timeout.connect(self._refresh_stats)

    def wire(self, app_window: ApplicationWindow) -> None:
        self._aw = app_window
        self._refresh_stats()
        self._refresh.start()

    # ── Internal ────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_value(slot: int, raw: int) -> str:
        # Slot 0 = Air → percent; slot 1 = Burner → percent;
        # slot 2 = Drum → RPM; slot 3 = Fan → percent.
        if slot == 2:
            return f'{raw} RPM'
        return f'{raw} %'

    def _refresh_stats(self) -> None:
        aw = self._aw
        if aw is None:
            return
        try:
            qmc = aw.qmc
            names = getattr(qmc, 'etypes', None) or []
            values = getattr(aw, 'eventslidervalues', None) or []
            visible = getattr(aw, 'eventslidervisibilities', None) or []
            parts: list[str] = []
            for i in range(4):
                name = (names[i] if i < len(names) and isinstance(names[i], str)
                        else '').strip() or ['Air', 'Burner', 'Drum', 'Fan'][i]
                value = self._fmt_value(i, int(values[i])) if i < len(values) else '—'
                dimmed = i < len(visible) and not bool(visible[i])
                colour = '#A8A092' if dimmed else '#070D1F'
                parts.append(
                    f'<span style="color:#7A736A;">{name}</span>'
                    f'&nbsp;<b style="color:{colour};">{value}</b>'
                )
            self._line.setText(' &nbsp;·&nbsp; '.join(parts))
        except Exception:  # noqa: BLE001
            pass
