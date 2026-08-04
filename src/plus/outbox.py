#
# outbox.py
#
# File d'envoi persistante des torréfactions vers ZABAWA.plus.
#
# POURQUOI CE MODULE EXISTE
# -------------------------
# Le desktop possédait deux voies d'envoi concurrentes :
#   * plus/queue.py -> POST /v1/aroast, qui appelait task_done() même après
#     l'échec de toutes les tentatives : une coupure réseau de quelques minutes
#     faisait disparaître la torréfaction sans aucun message ;
#   * un POST direct vers upload-roast, sans persistance ni reprise.
# Les deux écrivaient la même ligne serveur et s'écrasaient mutuellement.
#
# Ce module est la voie unique. Il garantit trois choses que l'ancien dispositif
# ne garantissait pas :
#   1. rien n'est perdu — aucun état ne supprime un item non livré ;
#   2. rien ne dépend de l'état de connexion au moment de la torréfaction ;
#   3. un envoi n'est acquitté qu'après confirmation serveur indépendante
#      (cf. plus/outbox_worker.py, qui relit un reçu et compare le hash).
#
# STOCKAGE
# --------
# Une base SQLite pour les métadonnées, un fichier .alog par item pour le
# contenu. Le contenu (dizaines à centaines de Ko avec les courbes) reste hors
# base : inspectable, sauvegardable et récupérable à la main si tout le reste
# échoue.

import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

_log: Final[logging.Logger] = logging.getLogger(__name__)

STATE_PENDING: Final[str] = 'pending'
STATE_SENT: Final[str] = 'sent'
STATE_VERIFIED: Final[str] = 'verified'
STATE_FAILED: Final[str] = 'failed'

# Délais de reprise, en secondes. Le plafond d'une heure évite qu'une panne
# serveur longue ne martèle l'API, sans jamais abandonner l'item.
BACKOFF_SCHEDULE: Final[tuple[int, ...]] = (30, 60, 120, 300, 900, 1800, 3600)

# Au-delà, l'item passe en 'failed' : il reste visible et rejouable d'un clic,
# mais il cesse d'occuper le worker. 12 tentatives ≈ 5 h de reprises.
MAX_ATTEMPTS: Final[int] = 12

# Sous-dossier du répertoire de configuration Artisan. Volontairement distinct
# de 'outbox', utilisé par plus/queue.py pour le protocole plus.
OUTBOX_DIRNAME: Final[str] = 'roast_outbox'

_SCHEMA: Final[str] = """
CREATE TABLE IF NOT EXISTS outbox (
  uuid              TEXT PRIMARY KEY,
  created_at        REAL NOT NULL,
  updated_at        REAL NOT NULL,
  alog_path         TEXT NOT NULL,
  sync_record_json  TEXT,
  content_sha256    TEXT NOT NULL,
  entity_slug       TEXT,
  batch_label       TEXT,
  roast_at          REAL,
  bean_label        TEXT,
  state             TEXT NOT NULL,
  attempts          INTEGER NOT NULL DEFAULT 0,
  next_attempt_at   REAL NOT NULL,
  last_http_status  INTEGER,
  last_error        TEXT,
  server_roast_id   TEXT,
  bean_created      INTEGER NOT NULL DEFAULT 0,
  store_resolved    INTEGER,
  review_ack        INTEGER NOT NULL DEFAULT 0,
  sent_at           REAL,
  verified_at       REAL
);
CREATE INDEX IF NOT EXISTS outbox_state_idx ON outbox (state, next_attempt_at);
"""


@dataclass(frozen=True)
class OutboxItem:
    """Une torréfaction en attente de confirmation serveur."""

    uuid: str
    created_at: float
    updated_at: float
    alog_path: str
    content_sha256: str
    state: str
    attempts: int
    next_attempt_at: float
    sync_record: dict[str, Any] | None = None
    entity_slug: str | None = None
    batch_label: str | None = None
    # Date de la torréfaction (epoch s) et libellé du grain : sans eux, une
    # ligne en échec ne dit pas de quelle cuisson il s'agit.
    roast_at: float | None = None
    bean_label: str | None = None
    last_http_status: int | None = None
    last_error: str | None = None
    server_roast_id: str | None = None
    bean_created: bool = False
    store_resolved: bool | None = None
    review_ack: bool = False
    sent_at: float | None = None
    verified_at: float | None = None


def _row_to_item(r: sqlite3.Row) -> OutboxItem:
    sync_record: dict[str, Any] | None = None
    raw = r['sync_record_json']
    if raw:
        try:
            sync_record = json.loads(raw)
        except (ValueError, TypeError):  # journal illisible : on n'en fait pas un échec
            _log.warning('sync_record illisible pour %s', r['uuid'])
    store_resolved = r['store_resolved']
    return OutboxItem(
        uuid=r['uuid'],
        created_at=r['created_at'],
        updated_at=r['updated_at'],
        alog_path=r['alog_path'],
        content_sha256=r['content_sha256'],
        state=r['state'],
        attempts=r['attempts'],
        next_attempt_at=r['next_attempt_at'],
        sync_record=sync_record,
        entity_slug=r['entity_slug'],
        batch_label=r['batch_label'],
        roast_at=r['roast_at'],
        bean_label=r['bean_label'],
        last_http_status=r['last_http_status'],
        last_error=r['last_error'],
        server_roast_id=r['server_roast_id'],
        bean_created=bool(r['bean_created']),
        store_resolved=None if store_resolved is None else bool(store_resolved),
        review_ack=bool(r['review_ack']),
        sent_at=r['sent_at'],
        verified_at=r['verified_at'],
    )


class OutboxStore:
    """Persistance de la file d'envoi. Sûr vis-à-vis des threads."""

    def __init__(self, directory: str) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self._dir / 'outbox.db'), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        # WAL + synchronous=FULL : une coupure de courant juste après un DROP ne
        # doit pas coûter la torréfaction qu'on vient d'enfiler.
        self._db.execute('PRAGMA journal_mode=WAL')
        self._db.execute('PRAGMA synchronous=FULL')
        self._db.executescript(_SCHEMA)
        self._migrate()
        self._db.commit()

    def _migrate(self) -> None:
        """Ajoute les colonnes apparues après la première mise en service.

        CREATE TABLE IF NOT EXISTS n'ajoute rien à une table déjà créée : sans
        cette reprise, une file remplie par une version précédente ferait
        échouer toute lecture. Les items en attente doivent survivre aux mises
        à jour de l'application — c'est toute la raison d'être de cette base.
        """
        existing = {row['name'] for row in self._db.execute('PRAGMA table_info(outbox)')}
        for column, ddl in (('roast_at', 'REAL'), ('bean_label', 'TEXT')):
            if column not in existing:
                self._db.execute(f'ALTER TABLE outbox ADD COLUMN {column} {ddl}')

    # ---------------------------------------------------------------- écriture

    def enqueue(
        self,
        uuid: str,
        alog_content: str,
        *,
        sync_record: dict[str, Any] | None,
        entity_slug: str | None,
        batch_label: str | None,
        now: float,
        roast_at: float | None = None,
        bean_label: str | None = None,
    ) -> OutboxItem:
        """Dépose (ou remplace) une torréfaction dans la file.

        Un ré-enfilement du même UUID écrase le contenu et repart de zéro : une
        seule ligne par torréfaction, toujours la dernière version. Comme le
        serveur écrase à partir du .alog complet, une mise à jour ne peut plus
        effacer des champs — ce que faisaient les records partiels de l'ancienne
        file.
        """
        import hashlib

        digest = hashlib.sha256(alog_content.encode('utf-8')).hexdigest()
        path = self._dir / f'{uuid}.alog'

        # Écriture atomique AVANT l'insertion en base : un crash entre les deux
        # laisse au pire un fichier orphelin (nettoyé au démarrage), jamais une
        # ligne sans contenu.
        tmp = path.with_suffix('.alog.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(alog_content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

        with self._lock:
            self._db.execute(
                """
                INSERT INTO outbox (uuid, created_at, updated_at, alog_path, sync_record_json,
                                    content_sha256, entity_slug, batch_label, roast_at, bean_label,
                                    state, attempts,
                                    next_attempt_at, last_http_status, last_error,
                                    server_roast_id, bean_created, store_resolved, review_ack,
                                    sent_at, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, 0, NULL, 0, NULL, NULL)
                ON CONFLICT(uuid) DO UPDATE SET
                    updated_at       = excluded.updated_at,
                    alog_path        = excluded.alog_path,
                    sync_record_json = excluded.sync_record_json,
                    content_sha256   = excluded.content_sha256,
                    entity_slug      = excluded.entity_slug,
                    batch_label      = excluded.batch_label,
                    roast_at         = excluded.roast_at,
                    bean_label       = excluded.bean_label,
                    state            = excluded.state,
                    attempts         = 0,
                    next_attempt_at  = excluded.next_attempt_at,
                    last_http_status = NULL,
                    last_error       = NULL,
                    bean_created     = 0,
                    store_resolved   = NULL,
                    review_ack       = 0,
                    sent_at          = NULL,
                    verified_at      = NULL
                """,
                (uuid, now, now, str(path),
                 json.dumps(sync_record) if sync_record is not None else None,
                 digest, entity_slug, batch_label, roast_at, bean_label, STATE_PENDING, now),
            )
            self._db.commit()
        item = self.get(uuid)
        assert item is not None  # on vient de l'écrire
        return item

    def mark_sent(
        self,
        uuid: str,
        *,
        http_status: int,
        server_roast_id: str | None,
        bean_created: bool,
        store_resolved: bool | None,
        now: float,
    ) -> None:
        """Le serveur a accusé réception. Pas encore acquitté : le reçu reste à lire."""
        with self._lock:
            self._db.execute(
                """UPDATE outbox SET state=?, updated_at=?, sent_at=?, last_http_status=?,
                                     last_error=NULL, server_roast_id=?, bean_created=?,
                                     store_resolved=?
                   WHERE uuid=?""",
                (STATE_SENT, now, now, http_status, server_roast_id,
                 1 if bean_created else 0,
                 None if store_resolved is None else (1 if store_resolved else 0),
                 uuid),
            )
            self._db.commit()

    def mark_verified(self, uuid: str, now: float) -> None:
        """Le reçu serveur confirme la présence de CETTE version : envoi terminé."""
        with self._lock:
            self._db.execute(
                'UPDATE outbox SET state=?, updated_at=?, verified_at=?, last_error=NULL WHERE uuid=?',
                (STATE_VERIFIED, now, now, uuid),
            )
            self._db.commit()

    def mark_error(
        self,
        uuid: str,
        *,
        http_status: int | None,
        error: str,
        permanent: bool,
        now: float,
    ) -> None:
        """Échec d'une tentative.

        `permanent` vaut True pour les erreurs que rejouer à l'identique ne peut
        pas résoudre (400 corps invalide). L'item passe alors en 'failed'
        immédiatement — mais il n'est jamais supprimé.
        """
        with self._lock:
            row = self._db.execute(
                'SELECT attempts FROM outbox WHERE uuid=?', (uuid,)).fetchone()
            if row is None:
                return
            attempts = int(row['attempts']) + 1
            if permanent or attempts >= MAX_ATTEMPTS:
                state = STATE_FAILED
                next_at = now
            else:
                state = STATE_PENDING
                delay = BACKOFF_SCHEDULE[min(attempts - 1, len(BACKOFF_SCHEDULE) - 1)]
                next_at = now + delay
            self._db.execute(
                """UPDATE outbox SET state=?, attempts=?, next_attempt_at=?, updated_at=?,
                                     last_http_status=?, last_error=? WHERE uuid=?""",
                (state, attempts, next_at, now, http_status, error, uuid),
            )
            self._db.commit()

    def retry(self, uuid: str, now: float) -> None:
        """Relance manuelle depuis l'interface : remet l'item en tête de file."""
        with self._lock:
            self._db.execute(
                """UPDATE outbox SET state=?, attempts=0, next_attempt_at=?, updated_at=?,
                                     last_error=NULL WHERE uuid=?""",
                (STATE_PENDING, now, now, uuid),
            )
            self._db.commit()

    def acknowledge_review(self, uuid: str) -> None:
        """L'opérateur a pris acte du grain créé automatiquement."""
        with self._lock:
            self._db.execute('UPDATE outbox SET review_ack=1 WHERE uuid=?', (uuid,))
            self._db.commit()

    # ---------------------------------------------------------------- lecture

    def get(self, uuid: str) -> OutboxItem | None:
        with self._lock:
            row = self._db.execute('SELECT * FROM outbox WHERE uuid=?', (uuid,)).fetchone()
        return _row_to_item(row) if row is not None else None

    def all_items(self) -> list[OutboxItem]:
        with self._lock:
            rows = self._db.execute('SELECT * FROM outbox ORDER BY created_at').fetchall()
        return [_row_to_item(r) for r in rows]

    def due_items(self, now: float) -> list[OutboxItem]:
        """Items à (ré)envoyer maintenant."""
        with self._lock:
            rows = self._db.execute(
                'SELECT * FROM outbox WHERE state=? AND next_attempt_at<=? ORDER BY created_at',
                (STATE_PENDING, now)).fetchall()
        return [_row_to_item(r) for r in rows]

    def sent_items(self) -> list[OutboxItem]:
        """Items envoyés dont le reçu n'a pas encore confirmé la présence."""
        with self._lock:
            rows = self._db.execute(
                'SELECT * FROM outbox WHERE state=? ORDER BY created_at', (STATE_SENT,)).fetchall()
        return [_row_to_item(r) for r in rows]

    def stale_items(self, older_than: float, now: float) -> list[OutboxItem]:
        """Items non livrés qui traînent depuis plus de `older_than` secondes."""
        with self._lock:
            rows = self._db.execute(
                'SELECT * FROM outbox WHERE state!=? AND created_at<=? ORDER BY created_at',
                (STATE_VERIFIED, now - older_than)).fetchall()
        return [_row_to_item(r) for r in rows]

    def counts(self) -> dict[str, int]:
        with self._lock:
            rows = self._db.execute('SELECT state, COUNT(*) AS n FROM outbox GROUP BY state').fetchall()
        return {r['state']: int(r['n']) for r in rows}

    def to_review_count(self) -> int:
        """Torréfactions livrées dont le grain a été créé automatiquement."""
        with self._lock:
            row = self._db.execute(
                'SELECT COUNT(*) AS n FROM outbox WHERE bean_created=1 AND review_ack=0').fetchone()
        return int(row['n']) if row is not None else 0

    def content(self, uuid: str) -> str:
        item = self.get(uuid)
        if item is None:
            raise KeyError(uuid)
        return Path(item.alog_path).read_text(encoding='utf-8')

    # ------------------------------------------------------------- entretien

    def delete_verified(self, uuids: list[str]) -> int:
        """Supprime des items CONFIRMÉS. Renvoie le nombre effacé.

        La condition `state = verified` est dans la requête SQL, pas seulement
        dans l'appelant : c'est l'invariant du module — une torréfaction dont
        l'arrivée n'est pas prouvée ne doit jamais pouvoir disparaître, y
        compris par une fausse manœuvre dans l'interface.
        """
        if not uuids:
            return 0
        placeholders = ','.join('?' * len(uuids))
        with self._lock:
            rows = self._db.execute(
                f'SELECT uuid, alog_path FROM outbox WHERE state=? AND uuid IN ({placeholders})',
                (STATE_VERIFIED, *uuids)).fetchall()
            for r in rows:
                try:
                    Path(r['alog_path']).unlink(missing_ok=True)
                except OSError as e:
                    _log.warning('suppression du .alog impossible (%s): %s', r['alog_path'], e)
            self._db.executemany('DELETE FROM outbox WHERE uuid=?',
                                 [(r['uuid'],) for r in rows])
            self._db.commit()
        return len(rows)

    def purge_verified(self, before: float) -> int:
        """Supprime les items acquittés avant `before`. N'efface JAMAIS le reste."""
        with self._lock:
            rows = self._db.execute(
                'SELECT uuid, alog_path FROM outbox WHERE state=? AND verified_at<?',
                (STATE_VERIFIED, before)).fetchall()
            for r in rows:
                try:
                    Path(r['alog_path']).unlink(missing_ok=True)
                except OSError as e:  # le fichier disparaîtra au prochain cleanup
                    _log.warning('purge du .alog impossible (%s): %s', r['alog_path'], e)
            self._db.executemany('DELETE FROM outbox WHERE uuid=?',
                                 [(r['uuid'],) for r in rows])
            self._db.commit()
        return len(rows)

    def cleanup_orphans(self) -> int:
        """Supprime les .alog sans ligne correspondante (crash entre les deux écritures)."""
        with self._lock:
            known = {Path(r['alog_path']).name
                     for r in self._db.execute('SELECT alog_path FROM outbox').fetchall()}
        removed = 0
        for path in self._dir.glob('*.alog'):
            if path.name not in known:
                try:
                    path.unlink()
                    removed += 1
                except OSError as e:
                    _log.warning('nettoyage impossible (%s): %s', path, e)
        for tmp in self._dir.glob('*.alog.tmp'):
            try:
                tmp.unlink()
            except OSError:
                pass
        return removed

    def close(self) -> None:
        with self._lock:
            self._db.close()


# -----------------------------------------------------------------------------
# Instance partagée
# -----------------------------------------------------------------------------
# getDirectory est importé DANS la fonction : ce module doit rester importable
# sans Qt, pour que la logique de file reste testable quand la suite de tests
# remplace PyQt6 par des doubles (cf. test/unitary/plus/test_login.py).

_store: 'OutboxStore|None' = None
_store_lock = threading.Lock()


def outbox_directory() -> str:
    from artisanlib.util import getDirectory
    return getDirectory(OUTBOX_DIRNAME, share=False)


def get_store() -> OutboxStore:
    """Instance partagée de la file, créée à la première demande."""
    global _store  # pylint: disable=global-statement
    with _store_lock:
        if _store is None:
            _store = OutboxStore(outbox_directory())
        return _store
