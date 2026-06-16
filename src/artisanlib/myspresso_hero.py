"""
MySpresso Artisan — hero panel.

Sits between the top header strip and the existing main canvas
(`level1frame`). Three columns:

    [ title block ]   [ timer + temp ]   [ meta panel ]

Title block (left)
    PROFIL EN COURS · #N   (kicker, warm muted)
    {roast title}          (big bold navy)
    {filename}             (small mono muted)

Timer + temperature (center)
    {mm:ss}                (72 px JetBrains Mono navy)
    {temp}°{F|C} BT        (24 px JetBrains Mono red)

Meta panel (right)
    MAGASIN     {label}
    CHARGE      {kg} kg
    Δ T°        {±x.x} °/min
    DEV. RATIO  {x.x} %

Refreshed every 500 ms via QTimer, polling read-only state on the
canvas (qmc). The panel never writes to qmc — purely a display layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


def _fmt_mmss(seconds: float) -> str:
    if seconds < 0:
        return '0:00'
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f'{m}:{s:02d}'


def _safe(getter, default):  # noqa: ANN001
    try:
        v = getter()
        return v if v is not None else default
    except Exception:  # noqa: BLE001
        return default


class MySpressoHeroPanel(QFrame):
    """Hero strip between the brand header and the chart area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysHero')
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Not fixed: the hero is the top pane of mys_v_splitter and stays
        # user-resizable (drag the handle to give the chart more room). The
        # minimum keeps the title/timer readable.
        self.setMinimumHeight(96)

        # ── Title block (left) ──────────────────────────────────────────────
        title_block = QVBoxLayout()
        title_block.setSpacing(2)

        self._kicker = QLabel('PROFIL EN COURS · #0')
        self._kicker.setProperty('role', 'muted')
        self._kicker.setStyleSheet(
            'font-size: 11px; font-weight: 600; letter-spacing: 0.5px;'
            ' color: #7A736A;'
        )

        self._title = QLabel('Analyseur de torréfaction')
        self._title.setStyleSheet(
            'font-size: 26px; font-weight: 700; color: #070D1F;'
        )

        self._filename = QLabel('')
        self._filename.setStyleSheet(
            'font-family: "JetBrains Mono"; font-size: 11px; color: #7A736A;'
        )

        title_block.addWidget(self._kicker)
        title_block.addWidget(self._title)
        title_block.addWidget(self._filename)
        title_block.addStretch()

        title_w = QWidget()
        title_w.setLayout(title_block)

        # ── Timer + temperature (center) ────────────────────────────────────
        timer_block = QVBoxLayout()
        timer_block.setSpacing(0)
        timer_block.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._timer_label = QLabel('0:00')
        # Use an explicit QFont rather than QSS font-family so we can request
        # weight 700 reliably regardless of how the bundled TTF registered.
        # System fallback chain ensures crisp digits when JetBrains Mono is
        # absent (e.g. dev machine without the bundled font).
        from PyQt6.QtGui import QFont
        f_timer = QFont('JetBrains Mono')
        f_timer.setStyleHint(QFont.StyleHint.Monospace)
        f_timer.setPixelSize(46)
        f_timer.setWeight(QFont.Weight.DemiBold)
        self._timer_label.setFont(f_timer)
        self._timer_label.setStyleSheet('color: #070D1F;')
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Temperature echo under the timer (the authoritative, large readout
        # lives in the right pilot column; this is a glanceable duplicate next
        # to the clock so the top bar carries profil + temps + température).
        self._temp_label = QLabel('—.- °F BT')
        f_temp = QFont('JetBrains Mono')
        f_temp.setStyleHint(QFont.StyleHint.Monospace)
        f_temp.setPixelSize(17)
        f_temp.setWeight(QFont.Weight.Medium)
        self._temp_label.setFont(f_temp)
        self._temp_label.setStyleSheet('color: #A8392E;')
        self._temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        timer_block.addStretch()
        timer_block.addWidget(self._timer_label)
        timer_block.addWidget(self._temp_label)
        timer_block.addStretch()

        timer_w = QWidget()
        timer_w.setObjectName('MysHeroTimerBlock')
        timer_w.setLayout(timer_block)
        # v2 design: thin warm dividers framing the timer hero block.
        # Scope to objectName so descendants (QLabel) don't inherit borders.
        timer_w.setStyleSheet(
            '#MysHeroTimerBlock { border-left: 1px solid #E8E3D6;'
            ' border-right: 1px solid #E8E3D6; }'
        )

        # Meta panel (MAGASIN / CHARGE / Δ T° / DEV. RATIO) removed: the
        # piloting indicators now live in the right-hand MySpressoPilotColumn.

        # ── Top row: title (left) + timer (centre) ──────────────────────────
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(24)
        top_row.addWidget(title_w, 3)
        top_row.addWidget(timer_w, 4)
        # Right spacer keeps the timer visually centred now that the meta
        # panel is gone (title block on the left is wider than empty right).
        top_row.addStretch(3)

        # ── Phase LCDs row (centred, below the title/timer) ─────────────────
        # The native phasesLCDs widget is reparented here via attach_phases.
        self._phases_row = QHBoxLayout()
        self._phases_row.setContentsMargins(0, 0, 0, 0)
        self._phases_row.setSpacing(0)
        self._phases_row.addStretch(1)
        self._phases_row.addStretch(1)  # phases widget inserted at index 1

        # ── Outer layout ────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 10, 20, 8)
        root.setSpacing(6)
        root.addLayout(top_row)
        root.addLayout(self._phases_row)

        # Refresh timer
        self._aw: ApplicationWindow | None = None
        self._refresh = QTimer(self)
        self._refresh.setInterval(500)
        self._refresh.timeout.connect(self._refresh_values)

    def wire(self, app_window: ApplicationWindow) -> None:
        """Bind to the application window and start polling."""
        self._aw = app_window
        self._cursor_active: bool = False
        self._cursor_last_ms: int = 0
        self._refresh_values()
        self._refresh.start()

    def attach_phases(self, phases_widget: QWidget) -> None:
        """Reparent the native phase LCDs (SEC%/»SEC/»d1C …) into a centred row
        below the title/timer. The hero stays user-resizable via the top
        splitter handle — we never fix its height, only keep a minimum so the
        title/timer never clip."""
        self._phases_widget = phases_widget
        self._phases_row.insertWidget(1, phases_widget)

    def update_cursor(self, raw_message: str) -> None:
        """Display the matplotlib cursor X (time) in the hero timer.

        Called from main.py via a wrapper around ``ntb.set_message``. The
        upstream format is ``<PRE>{mode}  {xs}\\n{channel} {ys}°{mode}</PRE>``;
        when the cursor is outside the axes it collapses to just ``<PRE>F</PRE>``
        (mode only) — in that case we drop back to the live recording state.
        Temperature / RoR under the cursor are shown by the pilot column.
        """
        import re
        # Strip <PRE>/</PRE> wrappers and any other tags matplotlib may add.
        txt = re.sub(r'<[^>]+>', '', raw_message or '').strip()
        if not txt:
            self._cursor_active = False
            return
        lines = [line.strip() for line in txt.split('\n') if line.strip()]
        if len(lines) < 2:
            # mode-only payload → no cursor data to show, fall back to live.
            self._cursor_active = False
            return
        # Stamp the last time we got a real cursor payload so the refresh
        # loop can auto-clear the flag if matplotlib stops sending updates
        # (e.g. mouse leaves the whole window).
        from PyQt6.QtCore import QDateTime
        self._cursor_last_ms = QDateTime.currentMSecsSinceEpoch()
        # Line 1 — "{mode}  {xs}" (e.g. "F  2:11") or just "{xs}".
        first = lines[0].split()
        time_str = first[-1] if first else '—'
        self._timer_label.setText(time_str)
        # Line 2 — "{channel} {ys}°{mode}" — echo temperature (skip RoR lines).
        second = lines[1]
        if '°' in second and '/min' not in second:
            head, _, tail = second.rpartition('°')
            parts = head.split()
            temp_val = parts[-1] if parts else head.strip()
            channel = parts[0] if len(parts) > 1 else 'BT'
            self._temp_label.setText(f'{temp_val} °{tail} {channel}'.strip())
        self._cursor_active = True

    def _refresh_values(self) -> None:
        aw = self._aw
        if aw is None:
            return
        # If the chart cursor is hovering inside the axes, leave the timer /
        # temperature labels alone — update_cursor() owns them. The meta panel
        # (right side) still refreshes from live qmc state below.
        # Auto-clear the cursor flag if no cursor payload arrived in the last
        # ~1.2s — handles the case where the mouse leaves the entire window
        # without matplotlib firing a final "outside-axes" set_message.
        cursor_active = bool(getattr(self, '_cursor_active', False))
        if cursor_active:
            from PyQt6.QtCore import QDateTime
            last_ms = int(getattr(self, '_cursor_last_ms', 0))
            if QDateTime.currentMSecsSinceEpoch() - last_ms > 1200:
                self._cursor_active = False
                cursor_active = False
        qmc = aw.qmc

        # Title block
        title = _safe(lambda: qmc.title, '')
        batch_nr = _safe(lambda: qmc.roastbatchnr, 0)
        batch_prefix = _safe(lambda: qmc.roastbatchprefix, '#')
        kicker = (
            f'PROFIL EN COURS · {batch_prefix}{batch_nr}'
            if batch_nr else 'PROFIL EN COURS'
        )
        self._kicker.setText(kicker)
        if title:
            self._title.setText(title)
        filename = _safe(lambda: aw.curFile or '', '')
        if filename:
            # show only basename
            import os.path
            self._filename.setText(os.path.basename(filename))
        else:
            self._filename.setText('')

        # Timer (skipped when chart cursor is active — update_cursor owns it)
        if not cursor_active:
            # Use Artisan's authoritative ArtisanTime clock — it advances
            # every frame as long as monitoring is on, even when the user
            # has no real probe (in which case qmc.timex stays empty).
            elapsed = 0.0
            try:
                if getattr(qmc, 'flagstart', False):
                    elapsed = max(0.0, qmc.timeclock.elapsed() / 1000.0)
                elif getattr(qmc, 'flagon', False):
                    elapsed = max(0.0, qmc.timeclock.elapsedMilli() / 1000.0)
                else:
                    timez = _safe(lambda: qmc.timex, [])
                    timeindex = _safe(lambda: qmc.timeindex, [-1])
                    if (timez and timeindex and timeindex[0] >= 0
                            and timeindex[0] < len(timez)):
                        elapsed = max(0.0, timez[-1] - timez[timeindex[0]])
            except Exception:  # noqa: BLE001
                pass
            self._timer_label.setText(_fmt_mmss(elapsed))

            mode = _safe(lambda: qmc.mode, 'F')
            temp2 = _safe(lambda: qmc.temp2, [])
            if temp2 and temp2[-1] is not None and temp2[-1] != -1:
                self._temp_label.setText(f'{temp2[-1]:.1f} °{mode} BT')
            else:
                self._temp_label.setText(f'—.- °{mode} BT')
