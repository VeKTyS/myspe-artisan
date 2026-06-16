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

        # ── Native Artisan LCD panel slot (ET / BT / Δ BT …) ────────────────
        # The native lcdFrame is reparented here by main.py via set_native_lcds
        # when the user enables "Readings" (Ctrl+L). It owns ET/BT/RoR with the
        # familiar seven-segment look + tare / curve-toggle interactions.
        self._native_slot = QVBoxLayout()
        self._native_slot.setContentsMargins(0, 0, 0, 0)
        self._native_slot.setSpacing(0)
        root.addLayout(self._native_slot)
        self._native_divider = self._divider()
        self._native_divider.setVisible(False)
        root.addWidget(self._native_divider)
        self._native_gap = QWidget()
        self._native_gap.setFixedHeight(14)
        self._native_gap.setVisible(False)
        root.addWidget(self._native_gap)

        # ── Styled TEMP / RoR block (shown when native LCDs are OFF) ─────────
        styled = QVBoxLayout()
        styled.setContentsMargins(0, 0, 0, 0)
        styled.setSpacing(0)
        self._temp_value = self._big_value('210.4', '#A8392E', 38)
        styled.addLayout(self._readout('TEMP BT', self._temp_value))
        styled.addSpacing(14)
        styled.addWidget(self._divider())
        styled.addSpacing(14)
        self._ror_value = self._big_value('—', '#070D1F', 30)
        styled.addLayout(self._readout('RoR Δ BT', self._ror_value))
        styled.addSpacing(14)
        styled.addWidget(self._divider())
        styled.addSpacing(14)
        self._styled_block = QWidget()
        self._styled_block.setLayout(styled)
        root.addWidget(self._styled_block)

        # ── DEV (development time ratio) — always shown ─────────────────────
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
        # Long store names wrap onto multiple lines rather than being clipped.
        self._meta_store.setWordWrap(True)
        self._meta_charge = self._ctx_value()
        _store_label = self._ctx_label('MAGASIN')
        # Keep the label aligned with the first line of a wrapped value.
        ctx.addWidget(_store_label, 0, 0, Qt.AlignmentFlag.AlignTop)
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

    def set_native_lcds(self, lcd_frame: QWidget) -> None:
        """Reparent the native Artisan LCD panel (ET/BT/ΔBT …) into the top of
        this column. Its visibility stays owned by Artisan's Readings toggle
        (showLCDs/hideLCDs); set_native_mode mirrors that to avoid duplication."""
        from PyQt6.QtWidgets import QSizePolicy
        # In the column the panel sits at its natural height at the top; the
        # column's trailing stretch absorbs the slack.
        lcd_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._native_slot.addWidget(lcd_frame)
        self.set_native_mode(lcd_frame.isVisible())

    def set_native_mode(self, native_on: bool) -> None:
        """When the native LCDs are visible, hide the styled TEMP/RoR block
        (they show the same BT / Δ BT) so nothing is duplicated. DÉVELOPPEMENT
        and the MAGASIN/CHARGE footer are unique and always remain visible."""
        self._styled_block.setVisible(not native_on)
        self._native_divider.setVisible(native_on)
        self._native_gap.setVisible(native_on)

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
        # Full name — the label wraps (setWordWrap) instead of clipping.
        self._meta_store.setText(str(store))

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
