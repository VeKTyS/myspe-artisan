"""
MySpresso Artisan — phase tile.

Surfaces the roast's DÉVELOPPEMENT phase as a single quasi-square card
between the hero and the chart:

    ┌ DÉVELOPPEMENT · en cours ┐
    │ 00:57                    │
    │ 10.9 %                   │
    └━━━━━━ (accent bar) ──────┘

The tile: kicker label + state mark, big JetBrains Mono value (time in
develop), muted subtitle (DTR %), and a 3 px progress bar pinned to the
bottom edge. States: ``done`` (green bar + ✓), ``active`` (accent border
+ accent bar + "en cours"), ``idle`` (dimmed).

The development stopwatch is anchored to a fixed BT threshold of 202 °C
(first-crack territory) — *not* to the 1C event marker (``timeindex[2]``).
Several machines/events (Modbus, Santoker, WebSocket, manual crack) mark 1C
before BT actually reaches 202 °C, which made the counter start too early;
anchoring to the temperature crossing keeps it deterministic. See
``development_display`` for the rule.

(TP, SÉCHAGE and MAILLARD tiles were removed from the band by product
decision — only DÉVELOPPEMENT is rendered.)

Read-only mirror of qmc state, polled every 500 ms like the other
MySpresso panels — nothing here writes to qmc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from artisanlib.styles import current_semantic_tokens
from artisanlib.util import fromCtoFstrict

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


# BT (in °C) at which the development stopwatch starts. Fixed at 202 °C by
# product decision ("toujours 202°C"); converted to °F when the scope runs in
# Fahrenheit mode so the trigger stays physically 202 °C.
DEV_THRESHOLD_C: float = 202.0


def _fmt_mmss(seconds: float) -> str:
    if seconds < 0:
        return '--:--'
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f'{m:02d}:{s:02d}'


def _dev_threshold(mode: str, threshold_c: float = DEV_THRESHOLD_C) -> float:
    """The development threshold expressed in the active display unit."""
    return fromCtoFstrict(threshold_c) if mode == 'F' else threshold_c


def _dev_start_index(temp2: list[float], charge_i: int, threshold: float) -> int | None:
    """Index of the first BT sample that reaches ``threshold`` on the way up.

    BT must first sit *below* the threshold after CHARGE (which always happens
    at the turning point) before a crossing is accepted, so residual drum heat
    right after CHARGE cannot start the clock early. Invalid readings (the -1
    sentinel) are skipped. Returns ``None`` while 202 °C has not been reached.
    """
    seen_below = False
    for i in range(max(0, charge_i), len(temp2)):
        v = temp2[i]
        if v is None or v == -1:
            continue
        if not seen_below:
            if v < threshold:
                seen_below = True
            continue
        if v >= threshold:
            return i
    return None


def development_display(
    timex: list[float],
    temp2: list[float],
    timeindex: list[int],
    mode: str,
    now: float,
    threshold_c: float = DEV_THRESHOLD_C,
) -> tuple[str, str, str, float]:
    """Compute the DÉVELOPPEMENT tile content from the fixed BT threshold.

    The stopwatch is anchored to the first moment BT crosses 202 °C — NOT to the
    1C event marker (``timeindex[2]``), which some machines/events set earlier.
    Returns ``(value, subtitle, state, progress)`` for ``_PhaseTile.set_content``.
    ``now`` is the roast clock (seconds since CHARGE).
    """
    if not timex or not timeindex or timeindex[0] < 0:
        return ('--:--', '', 'idle', 0.0)
    charge_i = timeindex[0]
    t0 = timex[charge_i]
    drop_i = timeindex[6]
    drop_t = (timex[drop_i] - t0) if drop_i else None
    total = drop_t if drop_t is not None else max(now, 1.0)

    threshold = _dev_threshold(mode, threshold_c)
    start_i = _dev_start_index(temp2, charge_i, threshold)
    if start_i is None:
        return ('--:--', '', 'idle', 0.0)

    dev_start_t = timex[start_i] - t0
    dev_end = drop_t if drop_t is not None else now
    dev = max(0.0, dev_end - dev_start_t)
    dtr = (dev / total * 100) if total else 0.0
    state = 'done' if drop_t is not None else 'active'
    progress = 1.0 if drop_t is not None else (dev / total if total else 0.0)
    return (_fmt_mmss(dev), f'{dtr:.1f} %', state, progress)


class _PhaseTile(QFrame):
    """One quasi-square phase card (label / value / subtitle / progress)."""

    def __init__(self, kicker: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysPhaseTile')
        self.setMinimumWidth(120)
        self.setMaximumWidth(230)
        # Hug the content height instead of stretching to fill the column.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.state: str = 'idle'  # 'idle' | 'active' | 'done'
        self.progress: float = 0.0  # 0..1 for the bottom bar

        self._kicker = QLabel(kicker)
        self._state_mark = QLabel('')
        self._state_mark.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        head.addWidget(self._kicker)
        head.addStretch()
        head.addWidget(self._state_mark)

        self._value = QLabel('--:--')
        f_val = QFont('JetBrains Mono')
        f_val.setStyleHint(QFont.StyleHint.Monospace)
        f_val.setPixelSize(23)
        f_val.setWeight(QFont.Weight.Medium)
        self._value.setFont(f_val)

        self._sub = QLabel('')
        f_sub = QFont('JetBrains Mono')
        f_sub.setStyleHint(QFont.StyleHint.Monospace)
        f_sub.setPixelSize(11)
        self._sub.setFont(f_sub)

        # 3 px progress bar pinned at the bottom (track + fill)
        self._bar_track = QFrame()
        self._bar_track.setFixedHeight(3)
        self._bar_fill = QFrame(self._bar_track)
        self._bar_fill.setFixedHeight(3)
        self._bar_fill.move(0, 0)

        content = QVBoxLayout()
        content.setContentsMargins(14, 7, 14, 4)
        content.setSpacing(1)
        content.addLayout(head)
        content.addWidget(self._value)
        content.addWidget(self._sub)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(content)
        root.addWidget(self._bar_track)  # bleeds edge-to-edge like the mockup

    def set_content(self, value: str, sub: str, state: str, progress: float) -> None:
        self._value.setText(value)
        self._sub.setText(sub)
        changed = state != self.state
        self.state = state
        self.progress = max(0.0, min(1.0, progress))
        self._layout_bar()
        if changed:
            self._apply_theme()

    def _layout_bar(self) -> None:
        self._bar_fill.setFixedWidth(int(self._bar_track.width() * self.progress))

    def resizeEvent(self, a0) -> None:  # noqa: ANN001
        super().resizeEvent(a0)
        self._layout_bar()

    def _apply_theme(self) -> None:
        tok = current_semantic_tokens()
        border = tok.accent if self.state == 'active' else tok.border
        dim = self.state == 'idle'
        self.setStyleSheet(
            '#MysPhaseTile {'
            f' background-color: {tok.bg_raised};'
            f' border: 1px solid {border};'
            ' border-radius: 2px;'
            '}'
        )
        kicker_colour = tok.accent if self.state == 'active' else tok.fg_muted
        self._kicker.setStyleSheet(
            'font-size: 10px; font-weight: 700; letter-spacing: 1px;'
            f' color: {kicker_colour}; background: transparent;'
        )
        self._state_mark.setStyleSheet(
            'font-size: 9px; font-weight: 600; letter-spacing: 0.5px;'
            f' color: {tok.success_fg if self.state == "done" else tok.fg_muted};'
            ' background: transparent;'
        )
        self._state_mark.setText(
            '✓' if self.state == 'done' else ('en cours' if self.state == 'active' else '')
        )
        value_colour = tok.fg_muted if dim else tok.fg_primary
        self._value.setStyleSheet(f'color: {value_colour}; background: transparent;')
        self._sub.setStyleSheet(f'color: {tok.fg_muted}; background: transparent;')
        self._bar_track.setStyleSheet(f'background-color: {tok.border};')
        fill = {'done': tok.success_fg, 'active': tok.accent}.get(self.state, tok.border)
        self._bar_fill.setStyleSheet(f'background-color: {fill};')

    def restyle(self) -> None:
        self._apply_theme()


class MySpressoPhaseTiles(QFrame):
    """Row of phase cards, centred like the mockup's phase bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysPhases')
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Stay at content height; do not stretch to fill the pilot column.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        # MySpresso fork: only the DÉVELOPPEMENT phase is surfaced (TP, SÉCHAGE
        # and MAILLARD were dropped from the band by product decision). The
        # single tile stays centred in the resizable phases pane.
        self._dev = _PhaseTile('DÉVELOPPEMENT')
        self._tiles = (self._dev,)

        # Tight margins and no centring stretches: the single tile fills the
        # width it is given, so it stays visible even in the narrow pilot column
        # it now lives in (far right of the chart).
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(10)
        for t in self._tiles:
            row.addWidget(t)

        self._aw: ApplicationWindow | None = None
        self._refresh = QTimer(self)
        self._refresh.setInterval(500)
        self._refresh.timeout.connect(self._refresh_values)

        self._apply_theme()

    # ── theming ──────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        for t in self._tiles:
            t.restyle()

    def restyle(self) -> None:
        self._apply_theme()

    # ── wiring / polling ─────────────────────────────────────────────────────

    def wire(self, app_window: ApplicationWindow) -> None:
        self._aw = app_window
        self._refresh_values()
        self._refresh.start()

    def _elapsed(self) -> float:
        """Current roast clock in seconds (mirrors the hero timer logic)."""
        aw = self._aw
        if aw is None:
            return 0.0
        qmc = aw.qmc
        try:
            if getattr(qmc, 'flagstart', False):
                return max(0.0, qmc.timeclock.elapsed() / 1000.0)
        except Exception:  # noqa: BLE001
            pass
        try:
            if qmc.timex and qmc.timeindex[0] > -1:
                return max(0.0, qmc.timex[-1] - qmc.timex[qmc.timeindex[0]])
        except Exception:  # noqa: BLE001
            pass
        return 0.0

    def _refresh_values(self) -> None:
        aw = self._aw
        if aw is None:
            return
        qmc = aw.qmc
        try:
            # DÉVELOPPEMENT — stopwatch anchored to the 202 °C BT crossing (not
            # the 1C event marker), running until DROP. See development_display.
            value, sub, state, progress = development_display(
                qmc.timex, qmc.temp2, qmc.timeindex, qmc.mode, self._elapsed())
            self._dev.set_content(value, sub, state, progress)
        except Exception:  # noqa: BLE001
            pass
