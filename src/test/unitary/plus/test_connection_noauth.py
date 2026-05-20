#
# test_connection_noauth.py
#
# Unit tests for plus.connection auth short-circuit behaviour.

import sys
from types import ModuleType
from typing import Any
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub heavy dependencies before importing plus.connection
# ---------------------------------------------------------------------------

class _FakeQSemaphore:
    def __init__(self, initial: int = 1) -> None:
        self._count = initial

    def acquire(self, n: int = 1) -> None:  # noqa: ARG002
        pass

    def release(self, n: int = 1) -> None:  # noqa: ARG002
        pass

    def available(self) -> int:
        return 0


_qtcore_mock = MagicMock()
_qtcore_mock.QSemaphore = _FakeQSemaphore

_artisanlib_mock = MagicMock()
_artisanlib_mock.__version__ = '2.8.4'

_artisanlib_util_mock = MagicMock()

_requests_mock = MagicMock()
_requests_exceptions_mock = MagicMock()
_requests_models_mock = MagicMock()

_dateutil_mock = MagicMock()
_dateutil_parser_mock = MagicMock()

_cryptography_fernet_mock = MagicMock()
_cryptography_mock = MagicMock()

_keyring_mock = MagicMock()

_plus_account_mock = MagicMock()
_plus_util_mock = MagicMock()

# Build a minimal plus.config stub
_config_mod = ModuleType('plus.config')
_config_mod.app_name = 'artisan.plus'  # type: ignore[attr-defined]
_config_mod.auth_url = 'https://artisan.plus/api/v1/auth'  # type: ignore[attr-defined]
_config_mod.verify_ssl = True  # type: ignore[attr-defined]
_config_mod.connect_timeout = 6  # type: ignore[attr-defined]
_config_mod.read_timeout = 6  # type: ignore[attr-defined]
_config_mod.compress_posts = True  # type: ignore[attr-defined]
_config_mod.post_compression_threshold = 500  # type: ignore[attr-defined]
_config_mod.token = None  # type: ignore[attr-defined]
_config_mod.nickname = None  # type: ignore[attr-defined]
_config_mod.connected = False  # type: ignore[attr-defined]
_config_mod.app_window = None  # type: ignore[attr-defined]
_config_mod.auth_enabled = False  # type: ignore[attr-defined]
_config_mod.account_nr = None  # type: ignore[attr-defined]

_stub_modules: dict[str, Any] = {
    'PyQt6': MagicMock(),
    'PyQt6.QtCore': _qtcore_mock,
    'PyQt5': MagicMock(),
    'PyQt5.QtCore': MagicMock(),
    'artisanlib': _artisanlib_mock,
    'artisanlib.util': _artisanlib_util_mock,
    'plus.config': _config_mod,
    'plus.account': _plus_account_mock,
    'plus.util': _plus_util_mock,
    'requests': _requests_mock,
    'requests.models': _requests_models_mock,
    'requests.exceptions': _requests_exceptions_mock,
    'dateutil': _dateutil_mock,
    'dateutil.parser': _dateutil_parser_mock,
    'cryptography': _cryptography_mock,
    'cryptography.fernet': _cryptography_fernet_mock,
    'keyring': _keyring_mock,
}

# Inject stubs, import connection, then remove stubs we injected
_stubs_injected = {k: v for k, v in _stub_modules.items() if k not in sys.modules}
sys.modules.update(_stub_modules)

try:
    from plus import connection as _connection_module
finally:
    for k in _stubs_injected:
        sys.modules.pop(k, None)

connection = _connection_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reset_config_token():
    """Reset config.token/nickname on connection.config between tests."""
    saved_token = connection.config.token
    saved_nickname = connection.config.nickname
    connection.config.token = None
    connection.config.nickname = None
    yield
    connection.config.token = saved_token
    connection.config.nickname = saved_nickname


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_authentify_returns_true_without_http_when_auth_disabled(
    monkeypatch, reset_config_token  # noqa: ARG001
):
    """When auth_enabled=False, authentify() must return True without HTTP."""
    monkeypatch.setattr(connection.config, 'auth_enabled', False)

    with patch('plus.connection.requests') as mock_requests:
        result = connection.authentify(passwd='ignored')

    assert result is True
    assert mock_requests.post.call_count == 0
    assert mock_requests.get.call_count == 0


def test_authentify_sets_dummy_token_when_auth_disabled(
    monkeypatch, reset_config_token  # noqa: ARG001
):
    """When auth_enabled=False, setToken('noauth', 'local') must be called."""
    monkeypatch.setattr(connection.config, 'auth_enabled', False)

    with patch('plus.connection.requests'):
        connection.authentify()

    assert connection.config.token == 'noauth'
    assert connection.config.nickname == 'local'


def test_authorization_header_omitted_when_auth_disabled(monkeypatch):
    """Outgoing requests must not include Authorization when auth_enabled=False."""
    # Use connection.config (the stub _config_mod) — not a re-imported plus.config
    monkeypatch.setattr(connection.config, 'auth_enabled', False)
    monkeypatch.setattr(connection.config, 'token', 'noauth')

    # Provide a real app_window so getHeaders() builds a full header dict;
    # without the auth_enabled guard the Authorization header would appear here.
    mock_aw = MagicMock()
    mock_aw.get_os.return_value = ('macOS', '14.0', 'arm64')
    mock_aw.locale_str = 'en_US'
    monkeypatch.setattr(connection.config, 'app_window', mock_aw)

    mock_response = MagicMock(status_code=200, text='{}')
    mock_response.json.return_value = {}
    with patch('plus.connection.requests.get', return_value=mock_response) as mock_get:
        connection.getData('http://test/endpoint')

    headers = mock_get.call_args.kwargs.get('headers', {})
    assert 'Authorization' not in headers, f"Authorization unexpectedly present: {headers}"


def test_authorization_header_present_when_auth_enabled(monkeypatch):
    """Sanity: Authorization header IS present when auth_enabled=True."""
    # Use connection.config (the stub _config_mod) — not a re-imported plus.config
    monkeypatch.setattr(connection.config, 'auth_enabled', True)
    monkeypatch.setattr(connection.config, 'token', 'real-token-xyz')

    # app_window must be non-None so getHeaders() builds a real header dict
    mock_aw = MagicMock()
    mock_aw.get_os.return_value = ('macOS', '14.0', 'arm64')
    mock_aw.locale_str = 'en_US'
    monkeypatch.setattr(connection.config, 'app_window', mock_aw)

    mock_response = MagicMock(status_code=200, text='{}')
    mock_response.json.return_value = {}
    with patch('plus.connection.requests.get', return_value=mock_response) as mock_get:
        connection.getData('http://test/endpoint')

    headers = mock_get.call_args.kwargs.get('headers', {})
    assert headers.get('Authorization') == 'Bearer real-token-xyz'
