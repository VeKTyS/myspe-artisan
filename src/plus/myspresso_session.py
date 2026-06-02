#
# myspresso_session.py
#
# Sends a fire-and-forget POST to /asession/start when CHARGE is pressed so
# the MySpresso webapp can display a real-time "torréfaction en cours" banner.
# The same roastUUID must later be included in the /aroast POST at DROP so the
# backend can join the two events into a single roast_log row.

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
