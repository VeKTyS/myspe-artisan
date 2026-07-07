"""
MySpresso Artisan — RoastGuard.

Watches the live roast for anomalies and alerts the roaster:

    ┌──────────────────────────────────────────────────────────────────┐
    │ ⚠ ROASTGUARD — RoR négatif depuis 12 s (sonde ?)      [Ignorer] │
    └──────────────────────────────────────────────────────────────────┘

* rule-based detectors polled every second while recording (flagstart)
* in-app banner (theme-aware) + status-bar message + beep on critical
* optional fire-and-forget notification to zabawa.plus (Supabase Edge
  Function `roastguard`, action `notify`) — see
  docs/specs/2026-07-07-roastguard-design.md for the backend contract

Detectors (v1, thresholds in QSettings under RoastGuard/):
  sensor_dropout   BT/ET missing (-1) for N s while recording
  bt_stall         BT flat (<0.3°) for N s between TP and DROP
  ror_crash        negative BT RoR sustained N s between TP and FCs
  et_runaway       ET above hard ceiling (mode-aware default)
  phase_overrun    no DRY / no FCs by configurable deadlines; DTR cap
  divergence       BT deviates > X° from background profile for N s

Every detector has a per-anomaly cooldown so one condition never spams.
Read-only on qmc; never blocks the sampling loop.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.request
from typing import TYPE_CHECKING, Final

from PyQt6.QtCore import Qt, QSettings, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from artisanlib.styles import current_semantic_tokens

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow

_log: Final[logging.Logger] = logging.getLogger(__name__)

_COOLDOWN_S: Final[int] = 60  # per-anomaly re-alert cooldown


class RoastGuardBanner(QFrame):
    """Theme-aware alert strip pinned under the header (hidden by default)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MysRoastGuardBanner')
        self._label = QLabel('')
        self._label.setWordWrap(True)
        self._dismiss = QPushButton('Ignorer')
        self._dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss.clicked.connect(self.hide)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 8, 20, 8)
        lay.setSpacing(14)
        lay.addWidget(self._label, 1)
        lay.addWidget(self._dismiss)
        self.hide()
        self._apply_theme()

    def _apply_theme(self) -> None:
        tok = current_semantic_tokens()
        self.setStyleSheet(
            '#MysRoastGuardBanner {'
            f' background-color: {tok.error_bg};'
            f' border-bottom: 2px solid {tok.accent};'
            '}'
        )
        self._label.setStyleSheet(
            'font-size: 12px; font-weight: 600;'
            f' color: {tok.error_fg}; background: transparent;'
        )
        self._dismiss.setStyleSheet(
            'QPushButton {'
            f' color: {tok.error_fg}; background: transparent;'
            f' border: 1px solid {tok.error_fg}; border-radius: 2px;'
            ' padding: 3px 12px; font-size: 11px; font-weight: 700;'
            '}'
        )

    def restyle(self) -> None:
        self._apply_theme()

    def show_alert(self, message: str) -> None:
        self._label.setText(f'⚠ ROASTGUARD — {message}')
        self.show()


class RoastGuard(QFrame):
    """Anomaly watcher. Invisible QObject-ish (QFrame for parent lifetime)."""

    anomaly = pyqtSignal(str, str, str)  # kind, severity ('warning'|'critical'), message

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        self._aw: ApplicationWindow | None = None
        self.banner: RoastGuardBanner | None = None
        self._last_fired: dict[str, float] = {}   # kind -> roast time of last alert
        self._cond_since: dict[str, float] = {}   # kind -> roast time condition started
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.anomaly.connect(self._on_anomaly)

    # ── wiring ───────────────────────────────────────────────────────────────

    def wire(self, app_window: ApplicationWindow, banner: RoastGuardBanner) -> None:
        self._aw = app_window
        self.banner = banner
        self._timer.start()

    def _settings(self) -> QSettings:
        return QSettings()

    def _enabled(self) -> bool:
        return bool(self._settings().value('RoastGuard/enabled', True, type=bool))

    def _cloud_enabled(self) -> bool:
        return bool(self._settings().value('RoastGuard/cloudNotify', False, type=bool))

    def _threshold(self, key: str, default: float) -> float:
        try:
            return float(self._settings().value(f'RoastGuard/{key}', default))
        except (TypeError, ValueError):
            return default

    # ── engine ───────────────────────────────────────────────────────────────

    def _tick(self) -> None:  # noqa: PLR0912
        aw = self._aw
        if aw is None or not self._enabled():
            return
        qmc = aw.qmc
        try:
            if not getattr(qmc, 'flagstart', False):
                # roast not recording: reset state, hide stale banner
                self._cond_since.clear()
                self._last_fired.clear()
                return
            timex = qmc.timex
            timeindex = qmc.timeindex
            if not timex or timeindex[0] < 0:
                return
            t0 = timex[timeindex[0]]
            now = timex[-1] - t0
            fahrenheit = getattr(qmc, 'mode', 'F') == 'F'

            bt = qmc.temp2[-1] if qmc.temp2 else -1
            et = qmc.temp1[-1] if qmc.temp1 else -1
            ror = qmc.delta2[-1] if qmc.delta2 and qmc.delta2[-1] is not None else None
            tp_i = int(getattr(qmc, 'TPalarmtimeindex', 0) or 0)
            after_tp = tp_i > 0
            fcs_marked = bool(timeindex[2])
            dropped = bool(timeindex[6])
            if dropped:
                return

            # 1 — sensor dropout
            self._sustained('sensor_dropout', now,
                            active=(bt is None or bt == -1),
                            hold=self._threshold('dropoutSeconds', 5),
                            severity='critical',
                            message='lecture BT invalide (sonde déconnectée ?)')

            # 2 — BT stall between TP and DROP
            window_s = self._threshold('stallSeconds', 30)
            stalled = False
            if after_tp and len(timex) > 3:
                i = len(timex) - 1
                while i > 0 and timex[-1] - timex[i] < window_s:
                    i -= 1
                seg = [t for t in qmc.temp2[i:] if t is not None and t != -1]
                stalled = len(seg) > 3 and (max(seg) - min(seg)) < 0.3
            self._sustained('bt_stall', now, active=stalled, hold=0,
                            severity='warning',
                            message=f'BT stagnante depuis {int(window_s)} s (décrochage ?)')

            # 3 — negative RoR between TP and FCs
            self._sustained('ror_crash', now,
                            active=(after_tp and not fcs_marked
                                    and ror is not None and ror < 0),
                            hold=self._threshold('rorCrashSeconds', 10),
                            severity='warning',
                            message='RoR négatif — chute de température anormale')

            # 4 — ET runaway
            et_max = self._threshold('etMax', 500.0 if fahrenheit else 260.0)
            self._sustained('et_runaway', now,
                            active=(et is not None and et != -1 and et > et_max),
                            hold=3,
                            severity='critical',
                            message=f'ET au-dessus du plafond ({et_max:g}°)')

            # 5 — phase overruns
            dry_deadline = self._threshold('dryDeadline', 8 * 60)
            fcs_deadline = self._threshold('fcsDeadline', 13 * 60)
            self._sustained('dry_overrun', now,
                            active=(not timeindex[1] and now > dry_deadline),
                            hold=0, severity='warning',
                            message='fin de séchage non marquée — phase anormalement longue')
            self._sustained('fcs_overrun', now,
                            active=(not fcs_marked and now > fcs_deadline),
                            hold=0, severity='warning',
                            message='pas de 1er crack — torréfaction anormalement longue')

            # 6 — divergence vs background profile
            if getattr(qmc, 'background', False) and after_tp:
                dev = self._background_deviation(qmc)
                self._sustained('divergence', now,
                                active=(dev is not None
                                        and dev > self._threshold('divergenceDeg', 15.0)),
                                hold=self._threshold('divergenceSeconds', 15),
                                severity='warning',
                                message='BT s\'écarte fortement du profil de référence')
        except Exception as e:  # noqa: BLE001 — never break the UI loop
            _log.debug('roastguard tick error: %s', e)

    @staticmethod
    def _background_deviation(qmc) -> float | None:  # noqa: ANN001
        try:
            if not qmc.timeB or not qmc.temp2B or not qmc.timex:
                return None
            t = qmc.timex[-1]
            # nearest background sample (timeB aligned by Artisan)
            import bisect
            j = min(bisect.bisect_left(qmc.timeB, t), len(qmc.temp2B) - 1)
            bg = qmc.temp2B[j]
            cur = qmc.temp2[-1]
            if bg is None or cur is None or bg == -1 or cur == -1:
                return None
            return abs(cur - bg)
        except Exception:  # noqa: BLE001
            return None

    def _sustained(self, kind: str, now: float, *, active: bool, hold: float,
                   severity: str, message: str) -> None:
        """Fire `kind` when its condition has been active for `hold` seconds,
        with a per-kind cooldown."""
        if not active:
            self._cond_since.pop(kind, None)
            return
        start = self._cond_since.setdefault(kind, now)
        if now - start < hold:
            return
        last = self._last_fired.get(kind)
        if last is not None and now - last < _COOLDOWN_S:
            return
        self._last_fired[kind] = now
        self.anomaly.emit(kind, severity, message)

    # ── alerting ─────────────────────────────────────────────────────────────

    def _on_anomaly(self, kind: str, severity: str, message: str) -> None:
        aw = self._aw
        _log.warning('RoastGuard [%s/%s]: %s', kind, severity, message)
        if self.banner is not None:
            self.banner.show_alert(message)
        if aw is not None:
            try:
                aw.sendmessage(f'RoastGuard : {message}')
            except Exception:  # noqa: BLE001
                pass
        if severity == 'critical':
            QApplication.beep()
        if self._cloud_enabled():
            self._notify_cloud(kind, severity, message)

    def _notify_cloud(self, kind: str, severity: str, message: str) -> None:
        """Fire-and-forget POST to the zabawa.plus RoastGuard endpoint.

        Contract (backend: Supabase Edge Function `roastguard`, deployed per
        MySpresso conventions — see the design doc):
            POST {cloud/api_base_url}/functions/v1/roastguard
            { "action": "notify", "event": { ... } }
        """
        aw = self._aw
        base = str(self._settings().value('cloud/api_base_url', '')).rstrip('/')
        if not base or aw is None:
            return
        try:
            qmc = aw.qmc
            payload = {
                'action': 'notify',
                'event': {
                    'kind': kind,
                    'severity': severity,
                    'message': message,
                    'roast_title': str(getattr(qmc, 'title', '') or ''),
                    'batch_nr': int(getattr(qmc, 'roastbatchnr', 0) or 0),
                    'roast_time_s': (qmc.timex[-1] - qmc.timex[qmc.timeindex[0]]
                                     if qmc.timex and qmc.timeindex[0] >= 0 else 0),
                    'bt': qmc.temp2[-1] if qmc.temp2 else None,
                    'et': qmc.temp1[-1] if qmc.temp1 else None,
                    'ror': (qmc.delta2[-1] if qmc.delta2 else None),
                    'mode': getattr(qmc, 'mode', 'F'),
                    'app_version': 'zabawa-roast',
                },
            }
        except Exception as e:  # noqa: BLE001
            _log.debug('roastguard payload error: %s', e)
            return

        def _post() -> None:
            try:
                req = urllib.request.Request(
                    f'{base}/functions/v1/roastguard',
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST')
                with urllib.request.urlopen(req, timeout=6) as resp:
                    _log.info('roastguard notify: HTTP %s', resp.status)
            except Exception as e:  # noqa: BLE001 — cloud is best-effort
                _log.info('roastguard notify failed: %s', e)

        threading.Thread(target=_post, name='roastguard-notify', daemon=True).start()
