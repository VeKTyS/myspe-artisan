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
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from artisanlib.styles import current_semantic_tokens

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

        # Registries of colour-bearing sub-widgets, restyled by _apply_theme().
        # _big_values maps each big readout label to the SemanticTokens
        # attribute providing its colour (temp = chart_et red, others navy).
        self._big_values: list[tuple[QLabel, str]] = []
        self._kickers: list[QLabel] = []
        self._dividers: list[QFrame] = []
        self._ctx_values: list[QLabel] = []

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

        # ── Styled readouts (mockup pilot column) ───────────────────────────
        #   BT · GRAIN   196.8 °C   (big, chart-navy)
        #   ET · AIR     212.4 °C   (big, chart-red)
        #   ─────────────────────
        #   ΔBT   12.6°/min   DEV   10.9 %   AUC   412
        #   ─────────────────────
        #   AIR 70 %   TAMBOUR 62 %   BRÛLEUR 38 %   (first 3 event sliders)
        self._kv_values: list[QLabel] = []
        styled = QVBoxLayout()
        styled.setContentsMargins(0, 0, 0, 0)
        styled.setSpacing(0)
        self._bt_value = self._big_value('—.-', 'chart_bt', 32)
        styled.addLayout(self._readout('BT · GRAIN', self._bt_value))
        styled.addSpacing(12)
        self._et_value = self._big_value('—.-', 'chart_et', 32)
        styled.addLayout(self._readout('ET · AIR', self._et_value))
        styled.addSpacing(14)
        styled.addWidget(self._divider())
        styled.addSpacing(12)
        self._ror_value = self._kv_row(styled, 'ΔBT')
        self._dev_value = self._kv_row(styled, 'DEV')
        self._auc_value = self._kv_row(styled, 'AUC')
        styled.addSpacing(12)
        styled.addWidget(self._divider())
        styled.addSpacing(12)
        # First three event sliders (AIR / TAMBOUR / BRÛLEUR on MySpresso
        # machines — labels follow the configured event types).
        self._slider_rows: list[tuple[QLabel, QLabel]] = []
        for _ in range(3):
            box = QHBoxLayout()
            box.setContentsMargins(0, 2, 0, 2)
            lab = self._kicker('—')
            val = QLabel('—')
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._kv_values.append(val)
            box.addWidget(lab)
            box.addStretch()
            box.addWidget(val)
            styled.addLayout(box)
            self._slider_rows.append((lab, val))
        self._styled_block = QWidget()
        self._styled_block.setLayout(styled)
        root.addWidget(self._styled_block)

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

        # All sub-widgets exist — apply the theme-dependent colours.
        self._apply_theme()

    # ── widget builders (structure only — colours applied by _apply_theme) ──
    def _big_value(self, text: str, token_attr: str, px: int) -> QLabel:
        """Big readout label; ``token_attr`` names the SemanticTokens colour."""
        lbl = QLabel(text)
        f = QFont('JetBrains Mono')
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPixelSize(px)
        f.setWeight(QFont.Weight.DemiBold)
        lbl.setFont(f)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._big_values.append((lbl, token_attr))
        return lbl

    def _kicker(self, text: str) -> QLabel:
        lbl = QLabel(text)
        self._kickers.append(lbl)
        return lbl

    def _readout(self, label: str, value: QLabel) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(self._kicker(label))
        box.addWidget(value)
        return box

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        self._dividers.append(line)
        return line

    def _kv_row(self, into: QVBoxLayout, label: str) -> QLabel:
        """Key/value line: muted caption left, tabular mono value right."""
        box = QHBoxLayout()
        box.setContentsMargins(0, 2, 0, 2)
        val = QLabel('—')
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._kv_values.append(val)
        box.addWidget(self._kicker(label))
        box.addStretch()
        box.addWidget(val)
        into.addLayout(box)
        return val

    def _ctx_label(self, text: str) -> QLabel:
        # Same kicker treatment (small warm-grey caption).
        return self._kicker(text)

    def _ctx_value(self) -> QLabel:
        lbl = QLabel('—')
        self._ctx_values.append(lbl)
        return lbl

    # ── theming ─────────────────────────────────────────────────────────────
    def _apply_theme(self) -> None:
        """(Re-)apply every colour-bearing style from the current semantic
        tokens. Called at the end of __init__ and again via restyle() when
        the system colour scheme flips."""
        tok = current_semantic_tokens()
        # Column: thin divider separating it from the chart, on the app bg.
        self.setStyleSheet(
            f'#MysPilot {{ border-left: 1px solid {tok.border};'
            f' background-color: {tok.bg}; }}'
        )
        for lbl, token_attr in self._big_values:
            lbl.setStyleSheet(f'color: {getattr(tok, token_attr)};')
        for lbl in self._kickers:
            lbl.setStyleSheet(
                'font-size: 10px; font-weight: 600; letter-spacing: 0.5px;'
                f' color: {tok.fg_muted};'
            )
        for line in self._dividers:
            line.setStyleSheet(
                f'color: {tok.border}; background-color: {tok.border};'
                ' max-height: 1px;'
            )
        for lbl in self._ctx_values:
            lbl.setStyleSheet(
                'font-family: "JetBrains Mono"; font-size: 12px;'
                f' font-weight: 500; color: {tok.fg_primary};'
            )
        for lbl in self._kv_values:
            lbl.setStyleSheet(
                'font-family: "JetBrains Mono"; font-size: 15px;'
                f' font-weight: 500; color: {tok.fg_primary};'
            )

    def restyle(self) -> None:
        """Public hook: re-apply theme colours (e.g. on scheme change)."""
        self._apply_theme()

    # ── lifecycle ───────────────────────────────────────────────────────────
    def wire(self, app_window: ApplicationWindow) -> None:
        """Bind to the application window and start polling."""
        self._aw = app_window
        self._refresh_values()
        self._refresh.start()

    def set_native_lcds(self, lcd_frame: QWidget) -> None:
        """Host (and keep hidden) the native Artisan LCD panel.

        Mockup design: the styled BT/ET/ΔBT readouts are THE canonical
        display of this column. The native panel is still re-parented here
        so it has a sane parent and its LCDs keep receiving values (the
        Large LCD windows and all display() call-sites are unaffected) —
        it just never competes visually with the styled block."""
        from PyQt6.QtWidgets import QSizePolicy
        lcd_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._native_slot.addWidget(lcd_frame)
        self._native_frame: QWidget | None = lcd_frame
        lcd_frame.setVisible(False)
        self.set_native_mode(False)

    def set_native_mode(self, native_on: bool) -> None:
        """Mockup design: the styled readouts always win — the hosted native
        panel stays hidden whatever Artisan's Readings toggle does."""
        del native_on
        native_frame = getattr(self, '_native_frame', None)
        if native_frame is not None:
            native_frame.setVisible(False)
        self._styled_block.setVisible(True)
        self._native_divider.setVisible(False)
        self._native_gap.setVisible(False)

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
                self._ror_value.setText(f'{val}°{tail}')
            else:
                self._bt_value.setText(f'{val} °{tail}')
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

        # BT / ET / RoR — skipped while the chart cursor owns them
        if not cursor_active:
            temp2 = _safe(lambda: qmc.temp2, [])
            if temp2 and temp2[-1] is not None and temp2[-1] != -1:
                self._bt_value.setText(f'{temp2[-1]:.1f} °{mode}')
            else:
                self._bt_value.setText(f'—.- °{mode}')

            temp1 = _safe(lambda: qmc.temp1, [])
            if temp1 and temp1[-1] is not None and temp1[-1] != -1:
                self._et_value.setText(f'{temp1[-1]:.1f} °{mode}')
            else:
                self._et_value.setText(f'—.- °{mode}')

            delta2 = _safe(lambda: qmc.delta2, [])
            if delta2 and delta2[-1] is not None:
                self._ror_value.setText(f'{delta2[-1]:+.1f}°/min')
            else:
                self._ror_value.setText('—')

        # DEV — development time ratio: (t - t_FCs) / (t - t_CHARGE)
        self._dev_value.setText(self._dev_ratio_text(qmc))

        # AUC — mirror the native AUC readout (already computed by Artisan)
        auc = _safe(aw.AUClcd.text, '')
        self._auc_value.setText(auc if auc and auc not in ('--', '0') else '—')

        # Event sliders 1-3 (AIR / TAMBOUR / BRÛLEUR on MySpresso machines)
        try:
            etypes = _safe(lambda: qmc.etypes, [])
            sliders = (aw.slider1, aw.slider2, aw.slider3)
            for i, (lab, val) in enumerate(self._slider_rows):
                name = str(etypes[i]) if i < len(etypes) else ''
                if name and not name.startswith('-'):
                    lab.setText(name.upper())
                    val.setText(f'{sliders[i].value()} %')
                else:
                    lab.setText('—')
                    val.setText('—')
        except Exception:  # noqa: BLE001
            pass

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
