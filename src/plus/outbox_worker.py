#
# outbox_worker.py
#
# Thread d'envoi de la file : réveille process_once périodiquement, tient le
# verrou d'instance et fait l'entretien au démarrage.
#
# La logique d'acquittement vit dans plus/outbox_processor.py (sans Qt) ; ce
# module ne fait que la cadencer.
#
# Le worker ne dépend NI de plus_account NI de l'état de connexion. C'était le
# défaut de l'ancien dispositif : une connexion échouée au démarrage suffisait à
# ce que la torréfaction ne soit même pas mise en file.

import logging
import os
import threading
import time
from pathlib import Path
from typing import Final

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from plus import outbox_client
from plus.outbox import STATE_VERIFIED, OutboxStore, get_store, outbox_directory
from plus.outbox_processor import default_on_verified, process_once

_log: Final[logging.Logger] = logging.getLogger(__name__)

# Intervalle de réveil. Les reprises réelles sont pilotées par le backoff de
# chaque item ; ce tic ne fait que réveiller la boucle.
POLL_SECONDS: Final[float] = 30.0

# Les torréfactions confirmées sont conservées 24 h, le temps qu'un opérateur
# les retrouve dans l'onglet « passées » en fin de journée. Au-delà, elles n'ont
# plus d'intérêt local : la donnée vit sur ZABAWA.plus, et le journal
# d'ingestion côté serveur garde la trace de ce qui a été reçu.
KEEP_VERIFIED_SECONDS: Final[float] = 24 * 3600

# Une application qui tourne plusieurs jours doit purger sans redémarrage.
PURGE_INTERVAL_SECONDS: Final[float] = 3600

# Au-delà, l'interface signale un envoi qui traîne.
STALE_SECONDS: Final[float] = 24 * 3600


def acquire_lock(directory: str) -> bool:
    """Verrou d'instance : une seule application envoie.

    Deux Artisan ouverts sur le même profil utilisateur enverraient les mêmes
    items en double. L'envoi reste idempotent côté serveur, mais le doublon
    brouille le journal d'ingestion et double la charge.
    """
    lock_path = Path(directory) / 'outbox.lock'
    try:
        if lock_path.exists():
            raw = lock_path.read_text(encoding='utf-8').strip()
            pid = int(raw.split()[0]) if raw else 0
            if pid and pid != os.getpid():
                try:
                    os.kill(pid, 0)  # le détenteur est-il encore vivant ?
                    return False
                except OSError:
                    pass  # verrou périmé (crash) : on le reprend
        lock_path.write_text(f'{os.getpid()} {time.time()}', encoding='utf-8')
        return True
    except (OSError, ValueError) as e:
        # Mieux vaut envoyer que rester muet : le pire cas est un doublon
        # idempotent, le pire cas inverse est une torréfaction jamais envoyée.
        _log.warning('verrou de la file indisponible: %s', e)
        return True


def release_lock(directory: str) -> None:
    try:
        lock_path = Path(directory) / 'outbox.lock'
        if lock_path.exists():
            raw = lock_path.read_text(encoding='utf-8').strip()
            if raw and int(raw.split()[0]) == os.getpid():
                lock_path.unlink()
    except (OSError, ValueError):
        pass


class _WorkerObject(QObject):
    """Boucle d'envoi, exécutée dans son propre thread."""

    changed = pyqtSignal()

    def __init__(self, store: OutboxStore, owns_lock: bool) -> None:
        super().__init__()
        self._store = store
        self._owns_lock = owns_lock
        self._wake = threading.Event()
        self._stopped = False

    def _housekeeping(self) -> None:
        """Fichiers orphelins d'un crash, torréfactions confirmées expirées."""
        try:
            self._store.cleanup_orphans()
            self._store.purge_verified(before=time.time() - KEEP_VERIFIED_SECONDS)
        except Exception as e:  # pylint: disable=broad-except
            _log.exception(e)

    @pyqtSlot()
    def run(self) -> None:
        # Entretien au démarrage. Tout ce qui n'est PAS confirmé est repris tel
        # quel : seules les confirmées expirent.
        self._housekeeping()
        last_purge = time.time()

        while not self._stopped:
            # Une application qui tourne plusieurs jours doit purger sans
            # redémarrage, sinon la liste des passées grossit indéfiniment.
            if time.time() - last_purge > PURGE_INTERVAL_SECONDS:
                self._housekeeping()
                last_purge = time.time()
            if self._owns_lock:
                try:
                    treated = process_once(
                        self._store,
                        uploader=outbox_client.upload,
                        receipter=outbox_client.fetch_receipt,
                        now=time.time(),
                        on_verified=default_on_verified,
                    )
                    if treated:
                        self.changed.emit()
                except Exception as e:  # pylint: disable=broad-except
                    _log.exception(e)
            self._wake.wait(POLL_SECONDS)
            self._wake.clear()

    def wake(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stopped = True
        self._wake.set()


class OutboxWorker(QObject):
    """Façade : possède le thread et expose wake()/stop() au reste de l'app."""

    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._directory = outbox_directory()
        self._store = get_store()
        self._owns_lock = acquire_lock(self._directory)
        if not self._owns_lock:
            _log.info("file d'envoi : une autre instance détient le verrou, envoi désactivé ici")
        self._obj = _WorkerObject(self._store, self._owns_lock)
        self._thread = QThread()
        self._obj.moveToThread(self._thread)
        self._obj.changed.connect(self.changed)
        self._thread.started.connect(self._obj.run)

    @property
    def store(self) -> OutboxStore:
        return self._store

    def start(self) -> None:
        self._thread.start()

    def wake(self) -> None:
        self._obj.wake()

    def stop(self) -> None:
        self._obj.stop()
        self._thread.quit()
        self._thread.wait(3000)
        if self._owns_lock:
            release_lock(self._directory)

    def pending_count(self) -> int:
        counts = self._store.counts()
        return sum(n for state, n in counts.items() if state != STATE_VERIFIED)
