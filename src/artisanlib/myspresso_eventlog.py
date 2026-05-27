"""
MySpresso Artisan — bottom event log strip.

Sits below the matplotlib chart. Displays a timestamped list of recent
events (profile saved, roast synced, drop detected, errors, etc.).
Read-only mirror of ApplicationWindow.messagehist — no modification of
the upstream sendmessage flow.

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
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


class MySpressoEventLog(QFrame):
    """Footer log strip with two columns:
        [ left card: TORRÉFACTION info ]   [ right: timestamped events list ]
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysEventLog')
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(110)

        # ── Left card: TORRÉFACTION info ────────────────────────────────────
        left_block = QVBoxLayout()
        left_block.setSpacing(2)
        left_block.setContentsMargins(0, 0, 0, 0)

        self._left_kicker = QLabel('TORRÉFACTION')
        self._left_kicker.setStyleSheet(
            'font-size: 10px; font-weight: 600; letter-spacing: 0.5px;'
            ' color: #7A736A;'
        )

        self._left_date = QLabel('')
        self._left_date.setStyleSheet(
            'font-family: "JetBrains Mono"; font-size: 11px; color: #4E4A44;'
        )

        self._left_stats = QLabel('— écoulé · — vert')
        self._left_stats.setStyleSheet(
            'font-family: "JetBrains Mono"; font-size: 13px; font-weight: 500;'
            ' color: #070D1F;'
        )

        left_block.addWidget(self._left_kicker)
        left_block.addWidget(self._left_date)
        left_block.addStretch()
        left_block.addWidget(self._left_stats)

        left_card = QFrame()
        left_card.setObjectName('MysEventLogCard')
        left_card.setLayout(left_block)
        # Widened so "30.00 Kg vert" (and similar full-unit strings) fit on
        # one line rather than getting truncated to "30.00 Kg v…".
        left_card.setMinimumWidth(300)
        left_card.setStyleSheet(
            'QFrame#MysEventLogCard { background-color: #F2EFE7;'
            ' border-radius: 2px; padding: 12px 16px; }'
        )

        # ── Right: timestamped events ───────────────────────────────────────
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
            ' padding: 2px 0;'
            ' border: none;'
            '}'
        )

        # ── Outer layout ────────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 8, 20, 12)
        root.setSpacing(16)
        root.addWidget(left_card)
        root.addWidget(self._list, 1)

        # Refresh state
        self._aw: ApplicationWindow | None = None
        self._last_count: int = 0
        self._refresh = QTimer(self)
        self._refresh.setInterval(500)
        self._refresh.timeout.connect(self._refresh_log)

    def wire(self, app_window: ApplicationWindow) -> None:
        self._aw = app_window
        self._refresh_log()
        self._refresh.start()

    # ── Internal ────────────────────────────────────────────────────────────

    def _refresh_log(self) -> None:
        aw = self._aw
        if aw is None:
            return

        # ── Left card: date + elapsed / green weight ────────────────────────
        try:
            from PyQt6.QtCore import QDateTime
            now = QDateTime.currentDateTime()
            self._left_date.setText(now.toString('dd/MM/yyyy HH:mm'))
        except Exception:  # noqa: BLE001
            pass

        try:
            qmc = aw.qmc
            # Prefer Artisan's authoritative ArtisanTime clock — it advances
            # every frame as long as monitoring is on, even if the user has
            # no real probe (in which case qmc.timex stays empty and the
            # previous timex-based fallback would have shown 0:00 forever).
            elapsed: float = 0.0
            try:
                if getattr(qmc, 'flagstart', False):
                    # Recording is running → timeclock.elapsed() ticks since
                    # CHARGE (or since DEBUT when no CHARGE yet).
                    elapsed = max(0.0, qmc.timeclock.elapsed() / 1000.0)
                elif getattr(qmc, 'flagon', False):
                    # Monitoring only — show time since ON.
                    elapsed = max(0.0, qmc.timeclock.elapsedMilli() / 1000.0)
                else:
                    # Idle: fall back to the last frame in timex if any.
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
            self._left_stats.setText(
                f'{elapsed_str} écoulé · {green:.2f} {unit} vert'
            )
        except Exception:  # noqa: BLE001
            pass

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
