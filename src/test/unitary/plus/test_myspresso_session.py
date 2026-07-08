"""Unit tests for plus.myspresso_session — the zabawa.plus "torréfaction en
cours" banner lifecycle (session start at CHARGE, session end at OFF/DROP).

Focus: the login-free end signal (send_session_end) that clears the banner even
when no full roast record is uploaded. It must POST the normalised roastUUID with
status='done' and the service token to config.roast_url (/aroast).
"""

import uuid as _uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from plus import myspresso_session


class _SyncThread:
    """Drop-in for threading.Thread that runs the target synchronously so the
    fire-and-forget POST is observable within the test."""

    def __init__(self, target: Any = None, daemon: Any = None, name: Any = None) -> None:
        self._target = target

    def start(self) -> None:
        if self._target is not None:
            self._target()


@pytest.fixture(autouse=True)
def _sync_threads() -> Any:
    with patch.object(myspresso_session.threading, 'Thread', _SyncThread):
        yield


@pytest.fixture
def _cfg() -> Any:
    with patch.object(myspresso_session, 'config') as cfg:
        cfg.roast_url = 'https://api.example/v1/aroast'
        cfg.session_url = 'https://api.example/v1/asession/start'
        cfg.artisan_service_token = 'svc-token'  # noqa: S105
        cfg.SUPABASE_ANON_KEY = 'anon-key'  # noqa: S105
        cfg.verify_ssl = True
        cfg.connect_timeout = 5
        cfg.app_window = None
        yield cfg


HEX_UUID = _uuid.uuid4().hex
DASHED_UUID = str(_uuid.UUID(HEX_UUID))


def test_send_session_end_posts_done_status(_cfg: Any) -> None:
    resp = MagicMock(status_code=200, text='ok')
    with patch.object(myspresso_session.requests, 'post', return_value=resp) as post:
        myspresso_session.send_session_end(HEX_UUID)

    post.assert_called_once()
    _, kwargs = post.call_args
    assert post.call_args[0][0] == 'https://api.example/v1/aroast'
    body = kwargs['json']
    assert body['status'] == 'done'
    # roastUUID normalised from 32-char hex to canonical RFC 4122 form
    assert body['id'] == DASHED_UUID
    assert body['roast_id'] == DASHED_UUID
    assert 'date' in body
    assert kwargs['headers']['Authorization'] == 'Bearer svc-token'
    assert kwargs['headers']['apikey'] == 'anon-key'


def test_send_session_end_no_url_is_noop(_cfg: Any) -> None:
    _cfg.roast_url = ''
    with patch.object(myspresso_session.requests, 'post') as post:
        myspresso_session.send_session_end(HEX_UUID)
    post.assert_not_called()


def test_send_session_end_swallows_network_errors(_cfg: Any) -> None:
    with patch.object(myspresso_session.requests, 'post', side_effect=OSError('boom')):
        # must never raise — the GUI thread that stops the roast can't be broken
        myspresso_session.send_session_end(HEX_UUID)
