#
# realtime.py
#
# Transport de l'abonnement temps réel : WebSocket, heartbeat, reconnexion.
#
# Le protocole lui-même (URL, messages, reconnaissance des événements) vit dans
# plus/realtime_protocol.py, sans dépendance Qt, pour rester testable seul.

import json
import logging
from typing import Final

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebSockets import QWebSocket

from plus import config
from plus.realtime_protocol import (
    COALESCE_MS,
    HEARTBEAT_MS,
    RECONNECT_DELAYS_MS,
    WATCHED_TABLES,
    changed_table,
    heartbeat_payload,
    join_payload,
    realtime_url,
)

_log: Final[logging.Logger] = logging.getLogger(__name__)


class RealtimeClient(QObject):
    """Client Supabase Realtime : signale les changements du référentiel.

    Émet `changed(table)` à chaque modification reçue, déjà regroupée : une
    rafale de mouvements ne produit qu'un signal.
    """

    changed = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)

    def __init__(self, parent: 'QObject|None' = None) -> None:
        super().__init__(parent)
        self._socket = QWebSocket()
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.textMessageReceived.connect(self._on_message)
        self._socket.errorOccurred.connect(self._on_error)

        self._ref = 0
        self._attempt = 0
        self._stopped = False
        self._pending_tables: set[str] = set()

        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(HEARTBEAT_MS)
        self._heartbeat.timeout.connect(self._send_heartbeat)

        self._reconnect = QTimer(self)
        self._reconnect.setSingleShot(True)
        self._reconnect.timeout.connect(self._open)

        # Regroupement des rafales : un import de stock émet des centaines
        # d'événements, on ne rafraîchit qu'une fois.
        self._coalesce = QTimer(self)
        self._coalesce.setSingleShot(True)
        self._coalesce.setInterval(COALESCE_MS)
        self._coalesce.timeout.connect(self._emit_pending)

    # ---------------------------------------------------------------- cycle de vie

    def start(self) -> None:
        self._stopped = False
        self._open()

    def stop(self) -> None:
        self._stopped = True
        self._heartbeat.stop()
        self._reconnect.stop()
        try:
            self._socket.close()
        except RuntimeError:
            pass

    def _open(self) -> None:
        if self._stopped:
            return
        url = realtime_url(config.api_base_url, config.SUPABASE_ANON_KEY)
        if url is None:
            _log.info('temps réel indisponible : URL de l\'API non configurée')
            return
        _log.debug('realtime: connexion')
        self._socket.open(QUrl(url))

    def _schedule_reconnect(self) -> None:
        if self._stopped:
            return
        delay = RECONNECT_DELAYS_MS[min(self._attempt, len(RECONNECT_DELAYS_MS) - 1)]
        self._attempt += 1
        _log.debug('realtime: reconnexion dans %s ms', delay)
        self._reconnect.start(delay)

    # ------------------------------------------------------------------- signaux

    @pyqtSlot()
    def _on_connected(self) -> None:
        _log.info('temps réel connecté')
        self._attempt = 0
        self._ref += 1
        self._socket.sendTextMessage(json.dumps(join_payload(WATCHED_TABLES, self._ref)))
        self._heartbeat.start()
        self.connectionChanged.emit(True)

    @pyqtSlot()
    def _on_disconnected(self) -> None:
        _log.info('temps réel déconnecté')
        self._heartbeat.stop()
        self.connectionChanged.emit(False)
        self._schedule_reconnect()

    @pyqtSlot()
    def _on_error(self, *_args: object) -> None:
        # errorOccurred est suivi de disconnected : la reprise est planifiée là.
        _log.debug('realtime: erreur socket')

    @pyqtSlot(str)
    def _on_message(self, raw: str) -> None:
        table = changed_table(raw)
        if table is None:
            return
        self._pending_tables.add(table)
        if not self._coalesce.isActive():
            self._coalesce.start()

    @pyqtSlot()
    def _emit_pending(self) -> None:
        tables, self._pending_tables = self._pending_tables, set()
        for table in sorted(tables):
            self.changed.emit(table)

    @pyqtSlot()
    def _send_heartbeat(self) -> None:
        self._ref += 1
        try:
            self._socket.sendTextMessage(json.dumps(heartbeat_payload(self._ref)))
        except RuntimeError:
            pass
