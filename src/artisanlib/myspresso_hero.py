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

from artisanlib.styles import current_semantic_tokens

if TYPE_CHECKING:
    from PyQt6.QtGui import QResizeEvent

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

    # Resizable but never hidable: main.py floors the pane at FLOOR_HEIGHT and
    # marks it non-collapsible. Between the floor and FULL_HEIGHT the title and
    # timer scale down (resizeEvent) so a shrunk bar stays clean instead of
    # clipping its big glyphs.
    FLOOR_HEIGHT = 44
    FULL_HEIGHT = 96
    _TIMER_PX = (26, 46)   # (at floor, at full)
    _TITLE_PX = (15, 26)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysHero')
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Not fixed: the hero is the top pane of mys_v_splitter and stays
        # user-resizable. main.py floors it at FLOOR_HEIGHT and makes it
        # non-collapsible, so it can be shrunk but never dragged away.
        # Current scaled glyph sizes (updated by resizeEvent); start at full.
        self._timer_px: int = self._TIMER_PX[1]
        self._title_px: int = self._TITLE_PX[1]

        # ── Title block (left) ──────────────────────────────────────────────
        title_block = QVBoxLayout()
        title_block.setSpacing(2)

        self._kicker = QLabel('PROFIL EN COURS · #0')
        self._kicker.setProperty('role', 'muted')

        self._title = QLabel('Analyseur de torréfaction')

        self._filename = QLabel('')

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
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Caption under the clock, per the mockup ("TEMPS DE TORRÉFACTION").
        self._timer_caption = QLabel('TEMPS DE TORRÉFACTION')
        self._timer_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        timer_block.addStretch()
        timer_block.addWidget(self._timer_label)
        timer_block.addWidget(self._timer_caption)
        timer_block.addStretch()

        timer_w = QWidget()
        timer_w.setObjectName('MysHeroTimerBlock')
        timer_w.setLayout(timer_block)
        # Thin dividers framing the timer hero block are applied (with the
        # current theme's border token) in _apply_theme().
        self._timer_w = timer_w

        # ── ET / BT echo (right, per the mockup) ────────────────────────────
        def _echo(unit_label: str) -> tuple[QLabel, QLabel, QVBoxLayout]:
            value = QLabel('—.-°')
            f_echo = QFont('JetBrains Mono')
            f_echo.setStyleHint(QFont.StyleHint.Monospace)
            f_echo.setPixelSize(21)
            f_echo.setWeight(QFont.Weight.Medium)
            value.setFont(f_echo)
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            caption = QLabel(unit_label)
            caption.setAlignment(Qt.AlignmentFlag.AlignRight)
            box = QVBoxLayout()
            box.setSpacing(1)
            box.addStretch()
            box.addWidget(value)
            box.addWidget(caption)
            box.addStretch()
            return value, caption, box

        self._echo_et, self._echo_et_cap, et_box = _echo('ET')
        self._echo_bt, self._echo_bt_cap, bt_box = _echo('BT')
        echo_row = QHBoxLayout()
        echo_row.setSpacing(22)
        echo_row.addStretch()
        echo_row.addLayout(et_box)
        echo_row.addLayout(bt_box)
        echo_w = QWidget()
        echo_w.setLayout(echo_row)

        # ── Outer layout: title (left) + timer (centre) + echo (right) ──────
        # Phase LCDs are NOT here — they live in their own resizable splitter
        # pane below the hero (independent of this bar).
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 10, 20, 10)
        root.setSpacing(24)
        root.addWidget(title_w, 3)
        root.addWidget(timer_w, 4)
        root.addWidget(echo_w, 3)

        # Refresh timer
        self._aw: ApplicationWindow | None = None
        self._refresh = QTimer(self)
        self._refresh.setInterval(500)
        self._refresh.timeout.connect(self._refresh_values)

        self._apply_theme()

    # ── Theming ──────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        """(Re-)apply all colour-bearing styles from the current semantic
        tokens. Called once at the end of __init__ and again via restyle()
        whenever the OS colour scheme flips."""
        tok = current_semantic_tokens()
        self._kicker.setStyleSheet(
            'font-size: 11px; font-weight: 600; letter-spacing: 0.5px;'
            f' color: {tok.fg_muted};'
        )
        self._title.setStyleSheet(
            f'font-size: {self._title_px}px; font-weight: 700; color: {tok.fg_primary};'
        )
        self._filename.setStyleSheet(
            'font-family: "JetBrains Mono"; font-size: 11px;'
            f' color: {tok.fg_muted};'
        )
        self._timer_label.setStyleSheet(f'color: {tok.fg_primary};')
        _tf = self._timer_label.font()
        if _tf.pixelSize() != self._timer_px:
            _tf.setPixelSize(self._timer_px)
            self._timer_label.setFont(_tf)
        self._timer_caption.setStyleSheet(
            'font-size: 10px; font-weight: 600; letter-spacing: 1.5px;'
            f' color: {tok.fg_muted};'
        )
        # ET / BT echoes take their curve colours, captions muted (mockup).
        self._echo_et.setStyleSheet(f'color: {tok.chart_et};')
        self._echo_bt.setStyleSheet(f'color: {tok.chart_bt};')
        caption_style = (
            'font-size: 9px; font-weight: 700; letter-spacing: 1.5px;'
            f' color: {tok.fg_muted};'
        )
        self._echo_et_cap.setStyleSheet(caption_style)
        self._echo_bt_cap.setStyleSheet(caption_style)
        # v2 design: thin warm dividers framing the timer hero block.
        # Scope to objectName so descendants (QLabel) don't inherit borders.
        self._timer_w.setStyleSheet(
            f'#MysHeroTimerBlock {{ border-left: 1px solid {tok.border};'
            f' border-right: 1px solid {tok.border}; }}'
        )

    def restyle(self) -> None:
        """Public hook: re-apply theme-dependent styles (OS theme flip)."""
        self._apply_theme()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Scale the title and timer with the pane height.

        The bar is floored and non-collapsible (see main.py), so it can be
        dragged smaller but never away. Interpolating the two big glyphs
        between FLOOR_HEIGHT and FULL_HEIGHT keeps a shrunk bar legible instead
        of clipping them.
        """
        super().resizeEvent(event)
        span = self.FULL_HEIGHT - self.FLOOR_HEIGHT
        t = 1.0 if span <= 0 else max(0.0, min(1.0, (event.size().height() - self.FLOOR_HEIGHT) / span))
        timer_px = round(self._TIMER_PX[0] + t * (self._TIMER_PX[1] - self._TIMER_PX[0]))
        title_px = round(self._TITLE_PX[0] + t * (self._TITLE_PX[1] - self._TITLE_PX[0]))
        if (timer_px, title_px) != (self._timer_px, self._title_px):
            self._timer_px = timer_px
            self._title_px = title_px
            self._apply_theme()

    def wire(self, app_window: ApplicationWindow) -> None:
        """Bind to the application window and start polling."""
        self._aw = app_window
        self._cursor_active: bool = False
        self._cursor_last_ms: int = 0
        self._refresh_values()
        self._refresh.start()

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
            head, _, _tail = second.rpartition('°')
            parts = head.split()
            temp_val = parts[-1] if parts else head.strip()
            self._echo_bt.setText(f'{temp_val}°')
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

            temp2 = _safe(lambda: qmc.temp2, [])
            if temp2 and temp2[-1] is not None and temp2[-1] != -1:
                self._echo_bt.setText(f'{temp2[-1]:.1f}°')
            else:
                self._echo_bt.setText('—.-°')
            temp1 = _safe(lambda: qmc.temp1, [])
            if temp1 and temp1[-1] is not None and temp1[-1] != -1:
                self._echo_et.setText(f'{temp1[-1]:.1f}°')
            else:
                self._echo_et.setText('—.-°')
