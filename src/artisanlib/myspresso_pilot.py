"""
MySpresso Artisan — pilot column.

Vertical readout column sitting to the right of the matplotlib chart
(inside ``mys_h_splitter``). Replaces the small meta panel that used to
live on the right of the hero strip with three large, glanceable
piloting indicators — the way the native Artisan LCD column reads:

    ┌──────────────┐
    │ TEMP BT      │
    │  210.4 °F    │   ← big red
    ├──────────────┤
    │ RoR Δ BT     │
    │  +8.2 °F/min │   ← big navy
    ├──────────────┤
    │ DÉVELOPPEMENT│
    │  18.4 %      │   ← big navy (DTR)
    ├──────────────┤
    │ MAGASIN  —   │   ← small context footer
    │ CHARGE   —   │
    └──────────────┘

Refreshed every 500 ms via QTimer, polling read-only state on the
canvas (qmc). The panel never writes to qmc — purely a display layer.
On chart cursor hover, TEMP / RoR mirror the pointed sample (driven by
``update_cursor`` forwarded from the navtoolbar's set_message).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


def _safe(getter, default):  # noqa: ANN001
    try:
        v = getter()
        return v if v is not None else default
    except Exception:  # noqa: BLE001
        return default


class MySpressoPilotColumn(QFrame):
    """Right-hand vertical column of large piloting readouts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysPilot')
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(170)
        # v2 design: thin warm divider separating the column from the chart.
        self.setStyleSheet(
            '#MysPilot { border-left: 1px solid #E8E3D6; background-color: #FBFAF6; }'
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 16)
        root.setSpacing(0)

        # ── TEMP (BT) ───────────────────────────────────────────────────────
        self._temp_value = self._big_value('210.4', '#A8392E', 38)
        root.addLayout(self._readout('TEMP BT', self._temp_value))
        root.addSpacing(14)
        root.addWidget(self._divider())
        root.addSpacing(14)

        # ── RoR (Δ BT) ──────────────────────────────────────────────────────
        self._ror_value = self._big_value('—', '#070D1F', 30)
        root.addLayout(self._readout('RoR Δ BT', self._ror_value))
        root.addSpacing(14)
        root.addWidget(self._divider())
        root.addSpacing(14)

        # ── DEV (development time ratio) ────────────────────────────────────
        self._dev_value = self._big_value('—', '#070D1F', 30)
        root.addLayout(self._readout('DÉVELOPPEMENT', self._dev_value))

        root.addStretch()

        # ── Context footer: MAGASIN / CHARGE ────────────────────────────────
        root.addWidget(self._divider())
        root.addSpacing(12)
        ctx = QGridLayout()
        ctx.setHorizontalSpacing(10)
        ctx.setVerticalSpacing(4)
        self._meta_store = self._ctx_value()
        self._meta_charge = self._ctx_value()
        ctx.addWidget(self._ctx_label('MAGASIN'), 0, 0)
        ctx.addWidget(self._meta_store, 0, 1)
        ctx.addWidget(self._ctx_label('CHARGE'), 1, 0)
        ctx.addWidget(self._meta_charge, 1, 1)
        ctx.setColumnStretch(1, 1)
        root.addLayout(ctx)

        # Refresh timer + cursor state
        self._aw: ApplicationWindow | None = None
        self._cursor_active: bool = False
        self._cursor_last_ms: int = 0
        self._refresh = QTimer(self)
        self._refresh.setInterval(500)
        self._refresh.timeout.connect(self._refresh_values)

    # ── widget builders ─────────────────────────────────────────────────────
    @staticmethod
    def _big_value(text: str, color: str, px: int) -> QLabel:
        lbl = QLabel(text)
        f = QFont('JetBrains Mono')
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPixelSize(px)
        f.setWeight(QFont.Weight.DemiBold)
        lbl.setFont(f)
        lbl.setStyleSheet(f'color: {color};')
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    @staticmethod
    def _kicker(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            'font-size: 10px; font-weight: 600; letter-spacing: 0.5px;'
            ' color: #7A736A;'
        )
        return lbl

    def _readout(self, label: str, value: QLabel) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(self._kicker(label))
        box.addWidget(value)
        return box

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet('color: #E8E3D6; background-color: #E8E3D6; max-height: 1px;')
        return line

    @staticmethod
    def _ctx_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            'font-size: 10px; font-weight: 600; letter-spacing: 0.5px;'
            ' color: #7A736A;'
        )
        return lbl

    @staticmethod
    def _ctx_value() -> QLabel:
        lbl = QLabel('—')
        lbl.setStyleSheet(
            'font-family: "JetBrains Mono"; font-size: 12px; font-weight: 500;'
            ' color: #070D1F;'
        )
        return lbl

    # ── lifecycle ───────────────────────────────────────────────────────────
    def wire(self, app_window: ApplicationWindow) -> None:
        """Bind to the application window and start polling."""
        self._aw = app_window
        self._refresh_values()
        self._refresh.start()

    def update_cursor(self, raw_message: str) -> None:
        """Display the matplotlib cursor temperature / RoR in the column.

        Forwarded from main.py's set_message wrapper. The upstream format is
        ``<PRE>{mode}  {xs}\\n{channel} {ys}°{mode}</PRE>``; when the cursor
        leaves the axes it collapses to just ``<PRE>F</PRE>`` (mode only) — we
        then fall back to live recording state.
        """
        import re
        txt = re.sub(r'<[^>]+>', '', raw_message or '').strip()
        if not txt:
            self._cursor_active = False
            return
        lines = [line.strip() for line in txt.split('\n') if line.strip()]
        if len(lines) < 2:
            self._cursor_active = False
            return
        from PyQt6.QtCore import QDateTime
        self._cursor_last_ms = QDateTime.currentMSecsSinceEpoch()
        # Line 2 — "{channel} {ys}°{mode}" (e.g. "BT 247.8°F" or "Δ 8.2°F/min").
        second = lines[1]
        if '°' in second:
            head, _, tail = second.rpartition('°')
            parts = head.split()
            val = parts[-1] if parts else head.strip()
            if '/min' in tail:
                # RoR sample under cursor
                self._ror_value.setText(f'{val} °{tail}')
            else:
                self._temp_value.setText(f'{val} °{tail}')
        self._cursor_active = True

    def _refresh_values(self) -> None:
        aw = self._aw
        if aw is None:
            return
        cursor_active = bool(getattr(self, '_cursor_active', False))
        if cursor_active:
            from PyQt6.QtCore import QDateTime
            last_ms = int(getattr(self, '_cursor_last_ms', 0))
            if QDateTime.currentMSecsSinceEpoch() - last_ms > 1200:
                self._cursor_active = False
                cursor_active = False
        qmc = aw.qmc
        mode = _safe(lambda: qmc.mode, 'F')

        # TEMP (BT) + RoR (Δ BT) — skipped while chart cursor owns them
        if not cursor_active:
            temp2 = _safe(lambda: qmc.temp2, [])
            if temp2 and temp2[-1] is not None and temp2[-1] != -1:
                self._temp_value.setText(f'{temp2[-1]:.1f} °{mode}')
            else:
                self._temp_value.setText(f'—.- °{mode}')

            delta2 = _safe(lambda: qmc.delta2, [])
            if delta2 and delta2[-1] is not None:
                self._ror_value.setText(f'{delta2[-1]:+.1f} °{mode}/min')
            else:
                self._ror_value.setText(f'— °{mode}/min')

        # DEV — development time ratio: (t - t_FCs) / (t - t_CHARGE)
        self._dev_value.setText(self._dev_ratio_text(qmc))

        # Context footer
        store = _safe(lambda: qmc.plus_store_label or qmc.plus_store or '', '') or '—'
        self._meta_store.setText(str(store)[:18])

        weight = _safe(lambda: qmc.weight, [0, 0, 'kg'])
        if weight and weight[0]:
            unit = weight[2] if len(weight) > 2 else 'kg'
            self._meta_charge.setText(f'{float(weight[0]):.2f} {unit}')
        else:
            self._meta_charge.setText('—')

    @staticmethod
    def _dev_ratio_text(qmc) -> str:  # noqa: ANN001
        """Development time ratio as a percentage string, or '—' before FCs."""
        try:
            timex = qmc.timex or []
            timeindex = qmc.timeindex or []
            if len(timeindex) < 7:
                return '—'
            i_charge = timeindex[0]
            i_fcs = timeindex[2]
            i_drop = timeindex[6]
            if i_fcs <= 0 or i_charge < 0 or i_fcs >= len(timex):
                return '—'
            t_charge = timex[i_charge] if 0 <= i_charge < len(timex) else timex[0]
            t_fcs = timex[i_fcs]
            # Current reference time: DROP if marked, else last sample.
            if i_drop > 0 and i_drop < len(timex):
                t_now = timex[i_drop]
            elif timex:
                t_now = timex[-1]
            else:
                return '—'
            total = t_now - t_charge
            if total <= 0:
                return '—'
            dtr = (t_now - t_fcs) / total * 100.0
            return f'{dtr:.1f} %'
        except Exception:  # noqa: BLE001
            return '—'
