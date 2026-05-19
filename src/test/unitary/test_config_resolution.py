#
# test_config_resolution.py
#
# Unit tests for plus.config URL/flag resolution.

from unittest.mock import patch
import pytest


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Ensure MySpresso env vars don't leak between tests."""
    for var in ('MYSPRESSO_API_URL', 'MYSPRESSO_WEB_URL', 'MYSPRESSO_AUTH_ENABLED'):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def fake_qsettings():
    """QSettings stub returning controllable values."""
    store: dict[str, object] = {}

    class FakeSettings:
        def value(self, key, default=None, type=None):  # noqa: A002,ARG002 (match Qt signature)
            return store.get(key, default if default is not None else '')

    return FakeSettings(), store


def test_api_base_url_uses_env_var_first(monkeypatch, fake_qsettings):
    settings, store = fake_qsettings
    store['cloud/api_base_url'] = 'http://from-settings/v1'
    monkeypatch.setenv('MYSPRESSO_API_URL', 'http://from-env/v1')

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_api_base_url
        assert _resolve_api_base_url() == 'http://from-env/v1'


def test_api_base_url_strips_trailing_slash_from_env(monkeypatch):
    monkeypatch.setenv('MYSPRESSO_API_URL', 'http://example.com/v1/')

    with patch('plus.config.QSettings'):
        from plus.config import _resolve_api_base_url
        assert _resolve_api_base_url() == 'http://example.com/v1'


def test_api_base_url_falls_back_to_qsettings(fake_qsettings):
    settings, store = fake_qsettings
    store['cloud/api_base_url'] = 'http://from-settings/v1'

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_api_base_url
        assert _resolve_api_base_url() == 'http://from-settings/v1'


def test_api_base_url_falls_back_to_compiled_default(fake_qsettings):
    settings, _store = fake_qsettings

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_api_base_url
        assert _resolve_api_base_url() == 'http://localhost:8000/v1'
