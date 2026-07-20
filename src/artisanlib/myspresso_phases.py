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
    QVBoxLayout,
    QWidget,
)

from artisanlib.styles import current_semantic_tokens

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


def _fmt_mmss(seconds: float) -> str:
    if seconds < 0:
        return '--:--'
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f'{m:02d}:{s:02d}'


class _PhaseTile(QFrame):
    """One quasi-square phase card (label / value / subtitle / progress)."""

    def __init__(self, kicker: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysPhaseTile')
        self.setMinimumWidth(150)
        self.setMaximumWidth(230)

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
        content.addStretch()

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

        # MySpresso fork: only the DÉVELOPPEMENT phase is surfaced (TP, SÉCHAGE
        # and MAILLARD were dropped from the band by product decision). The
        # single tile stays centred in the resizable phases pane.
        self._dev = _PhaseTile('DÉVELOPPEMENT')
        self._tiles = (self._dev,)

        row = QHBoxLayout(self)
        row.setContentsMargins(20, 8, 20, 8)
        row.setSpacing(10)
        row.addStretch()
        for t in self._tiles:
            row.addWidget(t)
        row.addStretch()

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
            timex = qmc.timex
            timeindex = qmc.timeindex
            charge_i = timeindex[0]
            if not timex or charge_i < 0:
                self._dev.set_content('--:--', '', 'idle', 0.0)
                return
            t0 = timex[charge_i]
            now = self._elapsed()
            drop_t = timex[timeindex[6]] - t0 if timeindex[6] else None
            total = drop_t if drop_t is not None else max(now, 1.0)
            fcs_t = timex[timeindex[2]] - t0 if timeindex[2] else None

            # DÉVELOPPEMENT — FC START → DROP (DTR)
            if fcs_t is not None:
                dev_end = drop_t if drop_t is not None else now
                dev = max(0.0, dev_end - fcs_t)
                dtr = dev / total * 100 if total else 0.0
                state = 'done' if drop_t is not None else 'active'
                self._dev.set_content(_fmt_mmss(dev), f'{dtr:.1f} %',
                                      state, 1.0 if drop_t is not None else dev / total)
            else:
                self._dev.set_content('--:--', '', 'idle', 0.0)
        except Exception:  # noqa: BLE001
            pass
