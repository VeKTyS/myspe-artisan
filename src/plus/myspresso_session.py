#
# myspresso_session.py
#
# Fire-and-forget lifecycle for the MySpresso webapp "torréfaction en cours"
# banner, using the login-free artisan_service_token:
#   send_session_start() -> POST /asession/start at CHARGE (status='in_progress')
#   send_session_end()   -> POST /aroast (status='done')  at OFF / DROP
# Both carry the same roastUUID so the backend upserts a single roast_logs row.
# The end signal guarantees the banner clears even when the full roast record
# is never uploaded (no plus login, or roast stopped before DROP).

import datetime
import logging
import threading
from typing import Final

import requests

from plus import config

_log: Final[logging.Logger] = logging.getLogger(__name__)


def _send_status(msg: str) -> None:
    """Push a message to the Artisan status bar from any thread."""
    try:
        aw = config.app_window
        if aw is not None:
            aw.sendmessage(msg)
    except Exception:  # pylint: disable=broad-except
        pass


def send_session_start(
    roast_uuid: str,
    machine: str,
    coffee: str,
    batch_size_kg: float,
) -> None:
    """POST /asession/start in a daemon thread — never blocks the GUI."""

    def _post() -> None:
        try:
            url = config.session_url
            if not url:
                _log.warning('session_url not configured — skipping asession/start')
                return
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config.artisan_service_token}',
                'apikey': config.SUPABASE_ANON_KEY,
            }
            # Artisan stores roastUUID as hex without dashes; the API expects
            # standard UUID format (8-4-4-4-12).
            import uuid as _uuid_mod
            try:
                formatted_uuid = str(_uuid_mod.UUID(roast_uuid))
            except (ValueError, AttributeError):
                formatted_uuid = roast_uuid
            data = {
                'id': formatted_uuid,
                'machine': machine or '',
                'coffee': coffee or '',
                'batch_size_kg': round(float(batch_size_kg), 3),
                'date': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            r = requests.post(
                url,
                json=data,
                headers=headers,
                verify=config.verify_ssl,
                timeout=(config.connect_timeout, 10),
            )
            try:
                body = r.text[:200]
            except Exception:  # pylint: disable=broad-except
                body = ''
            _log.info('asession/start -> HTTP %s  body: %s', r.status_code, body)
            if r.status_code in (200, 201):
                _send_status('✓ Torréfaction en cours envoyée sur MySpresso')
            else:
                _send_status(f'⚠ MySpresso session start: HTTP {r.status_code} — {body}')
        except Exception as e:  # pylint: disable=broad-except
            _log.exception('asession/start failed: %s', e)
            _send_status('⚠ MySpresso : échec de l\'envoi de la session')

    threading.Thread(target=_post, daemon=True, name='myspresso-session-start').start()


def send_session_end(roast_uuid: str) -> None:
    """POST /aroast with a minimal ``status='done'`` record to clear the
    "torréfaction en cours" banner — the login-free mirror of
    :func:`send_session_start`.

    Fired when the roaster stops the roast (OFF) or marks DROP, so the banner
    disappears even when no full roast record is uploaded (roaster not logged
    into a plus account, or roast aborted before DROP). Uses the same
    ``artisan_service_token`` as the session start, so it works without a login.

    Backend contract (Edge Function ``artisan-api``, POST /v1/aroast — the same
    route that upserts ``status: 'done'``, index.ts:366): this minimal payload
    MUST be accepted as an idempotent partial upsert keyed on ``id``/``roast_id``
    and MUST NOT null out columns already written by /asession/start or by a
    later full /aroast for the same id. It only flips the roast to ``done``.
    """

    def _post() -> None:
        try:
            url = config.roast_url
            if not url:
                _log.warning('roast_url not configured — skipping asession end')
                return
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config.artisan_service_token}',
                'apikey': config.SUPABASE_ANON_KEY,
            }
            # Artisan stores roastUUID as hex without dashes; the API expects
            # standard UUID format (8-4-4-4-12), same normalisation as start.
            import uuid as _uuid_mod
            try:
                formatted_uuid = str(_uuid_mod.UUID(roast_uuid))
            except (ValueError, AttributeError):
                formatted_uuid = roast_uuid
            data = {
                'id': formatted_uuid,
                'roast_id': formatted_uuid,
                'status': 'done',
                'date': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            r = requests.post(
                url,
                json=data,
                headers=headers,
                verify=config.verify_ssl,
                timeout=(config.connect_timeout, 10),
            )
            try:
                body = r.text[:200]
            except Exception:  # pylint: disable=broad-except
                body = ''
            _log.info('asession end (/aroast done) -> HTTP %s  body: %s', r.status_code, body)
            if r.status_code in (200, 201):
                _send_status('✓ Torréfaction terminée envoyée sur MySpresso')
            else:
                _send_status(f'⚠ MySpresso session end: HTTP {r.status_code} — {body}')
        except Exception as e:  # pylint: disable=broad-except
            _log.exception('asession end failed: %s', e)
            _send_status('⚠ MySpresso : échec de l\'envoi de la fin de session')

    threading.Thread(target=_post, daemon=True, name='myspresso-session-end').start()
