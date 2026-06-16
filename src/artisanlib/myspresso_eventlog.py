"""
MySpresso Artisan — bottom event log strip.

A thin, always-visible footer bar sits below the matplotlib chart:

    [ ▸ Historique ]   TORRÉFACTION · {date} · {elapsed} · {green} vert        … stats …

The timestamped event list is hidden by default (so the chart grid keeps
the height) and unfolds above the footer bar when the user clicks the
``Historique`` toggle. Read-only mirror of ApplicationWindow.messagehist
— no modification of the upstream sendmessage flow.

Polls messagehist every 500 ms via QTimer. Cheap: messagehist is a
bounded list (≤ 100 entries upstream), and we only redraw when the
length actually changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow
    from artisanlib.widgets import Splitter


# Splitter heights (px) for the bottom section when the history list is
# folded (footer bar only) vs unfolded (footer + list).
_COLLAPSED_PX = 40
_EXPANDED_PX = 190


class MySpressoEventLog(QFrame):
    """Collapsible footer: thin bar + on-demand timestamped event list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysEventLog')
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Footer bar is always visible; list adds height only when unfolded.
        self.setMinimumHeight(_COLLAPSED_PX)

        # ── Timestamped events list (hidden by default) ─────────────────────
        self._list = QListWidget()
        self._list.setObjectName('MysEventLogList')
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        f = QFont('JetBrains Mono')
        f.setPointSize(11)
        self._list.setFont(f)
        self._list.setStyleSheet(
            'QListWidget#MysEventLogList {'
            ' background-color: transparent;'
            ' border: none;'
            ' color: #4E4A44;'
            '}'
            'QListWidget#MysEventLogList::item {'
            ' padding: 2px 0 2px 20px;'
            ' border: none;'
            '}'
        )
        self._list.setVisible(False)

        # ── Footer bar (always visible) ─────────────────────────────────────
        self._toggle = QPushButton('▸  Historique')
        self._toggle.setObjectName('MysEventLogToggle')
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setFlat(True)
        self._toggle.setStyleSheet(
            'QPushButton#MysEventLogToggle {'
            ' font-size: 11px; font-weight: 600; letter-spacing: 0.5px;'
            ' color: #4E4A44; border: 1px solid #D9D2C5; border-radius: 3px;'
            ' padding: 4px 10px; background-color: #F2EFE7; }'
            'QPushButton#MysEventLogToggle:hover { background-color: #E8E3D6; }'
        )
        self._toggle.clicked.connect(self._toggle_history)

        self._summary = QLabel('TORRÉFACTION · —')
        self._summary.setStyleSheet(
            'font-family: "JetBrains Mono"; font-size: 12px; font-weight: 500;'
            ' color: #4E4A44;'
        )

        footer = QHBoxLayout()
        footer.setContentsMargins(20, 6, 20, 6)
        footer.setSpacing(14)
        footer.addWidget(self._toggle)
        footer.addWidget(self._summary)
        footer.addStretch(1)
        self._footer_extra_slot = footer  # stats inserted before the trailing edge
        self._footer_bar = QWidget()
        self._footer_bar.setObjectName('MysEventLogFooter')
        self._footer_bar.setFixedHeight(_COLLAPSED_PX)
        self._footer_bar.setLayout(footer)

        # ── Outer layout: list above, footer bar pinned at the bottom ───────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._list, 1)
        root.addWidget(self._footer_bar)

        # Splitter wiring (set via attach_splitter) for fold / unfold resizing.
        self._splitter: Splitter | None = None
        self._splitter_index: int = -1

        # Refresh state
        self._aw: ApplicationWindow | None = None
        self._last_count: int = 0
        self._refresh = QTimer(self)
        self._refresh.setInterval(500)
        self._refresh.timeout.connect(self._refresh_log)

    # ── Public wiring ─────────────────────────────────────────────────────────
    def wire(self, app_window: ApplicationWindow) -> None:
        self._aw = app_window
        self._refresh_log()
        self._refresh.start()

    def set_footer_extra(self, widget: QWidget | None) -> None:
        """Embed an extra widget (e.g. the slider stats strip) on the right
        of the footer bar, after the stretch so it sits flush right."""
        if widget is not None:
            self._footer_extra_slot.addWidget(widget)

    def attach_splitter(self, splitter: Splitter, index: int) -> None:
        """Remember the vertical splitter + this section's index so the
        toggle can grow/shrink the bottom zone (taking space from the chart)."""
        self._splitter = splitter
        self._splitter_index = index

    # ── Internal ──────────────────────────────────────────────────────────────
    def _toggle_history(self) -> None:
        show = not self._list.isVisible()
        self._list.setVisible(show)
        self._toggle.setText(('▾  ' if show else '▸  ') + 'Historique')
        sp = self._splitter
        idx = self._splitter_index
        if sp is None or idx < 0:
            return
        sizes = sp.sizes()
        if not (0 <= idx < len(sizes)):
            return
        target = _EXPANDED_PX if show else _COLLAPSED_PX
        delta = target - sizes[idx]
        sizes[idx] = target
        # Take/give the difference from the chart section (the one above us).
        graph_idx = idx - 1
        if 0 <= graph_idx < len(sizes):
            sizes[graph_idx] = max(80, sizes[graph_idx] - delta)
        sp.setSizes(sizes)

    def _refresh_log(self) -> None:
        aw = self._aw
        if aw is None:
            return

        # ── Footer summary: date · elapsed · green weight ───────────────────
        try:
            from PyQt6.QtCore import QDateTime
            date_str = QDateTime.currentDateTime().toString('dd/MM HH:mm')
        except Exception:  # noqa: BLE001
            date_str = '—'

        elapsed_str = '—'
        green_str = ''
        try:
            qmc = aw.qmc
            # Prefer Artisan's authoritative ArtisanTime clock — it advances
            # every frame while monitoring is on, even without a real probe.
            elapsed: float = 0.0
            try:
                if getattr(qmc, 'flagstart', False):
                    elapsed = max(0.0, qmc.timeclock.elapsed() / 1000.0)
                elif getattr(qmc, 'flagon', False):
                    elapsed = max(0.0, qmc.timeclock.elapsedMilli() / 1000.0)
                else:
                    timez = getattr(qmc, 'timex', None) or []
                    timeindex = getattr(qmc, 'timeindex', None) or [-1]
                    if (timez and timeindex and timeindex[0] >= 0
                            and timeindex[0] < len(timez)):
                        elapsed = max(0.0, timez[-1] - timez[timeindex[0]])
            except Exception:  # noqa: BLE001
                pass
            m, s = int(elapsed) // 60, int(elapsed) % 60
            elapsed_str = f'{m}:{s:02d}'
            weight = getattr(qmc, 'weight', None) or [0, 0, 'kg']
            green = float(weight[0]) if weight and weight[0] else 0
            unit = weight[2] if len(weight) > 2 else 'kg'
            if green:
                green_str = f'{green:.2f} {unit} vert'
        except Exception:  # noqa: BLE001
            pass

        summary = f'TORRÉFACTION · {date_str} · {elapsed_str} écoulé'
        if green_str:
            summary += f' · {green_str}'
        self._summary.setText(summary)

        # ── Right list: only redraw when messagehist actually changed ───────
        try:
            hist = getattr(aw, 'messagehist', None) or []
            if len(hist) == self._last_count:
                return
            self._last_count = len(hist)
            self._list.clear()
            # Display the last ~6 entries newest at bottom (matches mockup).
            # v2 design: prefix each entry with a kind marker (✓ / ✕ / ·)
            # based on the message keywords. Read-only — never mutates hist.
            for entry in hist[-6:]:
                marker = self._classify(entry)
                self._list.addItem(QListWidgetItem(f'{marker}  {entry}'))
            self._list.scrollToBottom()
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _classify(entry: str) -> str:
        """Pick a marker glyph for a messagehist line.

        Heuristic — Artisan does not tag messages with severity, so we sniff
        keywords (FR + EN). Defaults to ``·`` (info) when nothing matches.
        """
        low = entry.lower()
        ok_kw = ('enregistré', 'saved', 'synchronisé', 'synced', 'uploaded',
                 'connecté', 'connected', 'sauvegardé', 'started', 'détecté',
                 'detected')
        err_kw = ('erreur', 'error', 'échec', 'failed', 'fail', 'timeout',
                  'refus', 'denied', 'aborted', 'disconnect', 'déconnecté')
        for kw in err_kw:
            if kw in low:
                return '✕'
        for kw in ok_kw:
            if kw in low:
                return '✓'
        return '·'
