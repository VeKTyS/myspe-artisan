# MySpresso API Redirect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redirect Artisan's cloud communication layer from `artisan.plus` to a configurable MySpresso API endpoint, with authentication disabled in v1.

**Architecture:** Option A (config-only swap). Single-point change: `plus/config.py` becomes dynamic (env > QSettings > default). `plus/connection.py` short-circuits authentication when `auth_enabled=False`. `plus/controller.py` skips the login dialog. New small standalone Qt dialog exposes the configuration. UI strings rebranded "artisan.plus" → "MySpresso" in the most visible places. No abstraction layer, no `.alog` changes, zero impact on canvas/profiles/sensors/PID.

**Tech Stack:** Python 3.12+, PyQt6, pytest, ruff, mypy (existing Artisan stack — no new dependencies).

**Related docs:**
- Spec: [docs/superpowers/specs/2026-05-19-myspresso-api-redirect-design.md](../specs/2026-05-19-myspresso-api-redirect-design.md)

---

## File Structure

**Modified files:**
- [src/plus/config.py](../../../src/plus/config.py) — URL resolution functions, `auth_enabled` flag, default URLs swapped to MySpresso.
- [src/plus/connection.py](../../../src/plus/connection.py) — `authentify()` short-circuit when auth disabled; `_get_auth_headers()` helper to conditionally include `Authorization`.
- [src/plus/controller.py](../../../src/plus/controller.py) — `connect()` skips Login dialog when `auth_enabled=False`, marks the connection as live with the dummy session.
- [src/plus/login.py](../../../src/plus/login.py) — window title rebrand (`'plus'` → `'MySpresso'`).
- [src/artisanlib/main.py](../../../src/artisanlib/main.py) — rebrand of the most visible UI strings (status messages, menu items containing literal `'artisan.plus'`).

**New files:**
- `src/artisanlib/myspresso_settings_dialog.py` — small standalone QDialog exposing API URL + Web URL + auth toggle. Reads/writes QSettings under `cloud/*`.
- `src/test/unitary/test_config_resolution.py` — unit tests for `_resolve_api_base_url`, `_resolve_web_base_url`, `_resolve_auth_enabled`.
- `src/test/unitary/test_connection_noauth.py` — unit tests for `authentify()` short-circuit and `_get_auth_headers()` behaviour.

**Untouched (verify at end):**
- Everything in `src/artisanlib/` except `main.py` (and new dialog file).
- `src/plus/stock.py`, `sync.py`, `queue.py`, `schedule.py`, `notifications.py`, `roast.py`, all TypedDicts.
- Test files other than the two new ones.

---

## Task 1: Pre-flight — baseline lint, type, test green

Verify the existing repository builds and tests cleanly before touching anything. If this fails we need to know upfront.

**Files:** none modified.

- [ ] **Step 1: Confirm Python interpreter**

```bash
python3 --version
```
Expected: `Python 3.12.x` or higher.

- [ ] **Step 2: Install dev dependencies (if not already)**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pip install -r requirements-dev.txt 2>&1 | tail -5
```
Expected: no errors (or "already satisfied" lines).

- [ ] **Step 3: Run ruff on `plus/`**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check plus/
```
Expected: 0 errors, or a known baseline noise count. **Record the number** — we will compare at the end.

- [ ] **Step 4: Run existing pytest sanity suite**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/sanity/ -x -q 2>&1 | tail -10
```
Expected: all tests pass (or known baseline failures — record them).

- [ ] **Step 5: No commit (verification only).** Note the baseline numbers in a scratch file or memory.

---

## Task 2: Config — `_resolve_api_base_url()` with env > QSettings > default

Introduce the dynamic resolution function for the API base URL. Tests first.

**Files:**
- Create: `src/test/unitary/test_config_resolution.py`
- Modify: `src/plus/config.py` (lines 37-55, the URL block)

- [ ] **Step 1: Write the failing test file**

Create `src/test/unitary/test_config_resolution.py`:

```python
#
# test_config_resolution.py
#
# Unit tests for plus.config URL/flag resolution.

import os
from unittest.mock import patch, MagicMock
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
        def value(self, key, default=None, type=None):  # noqa: A002 (match Qt signature)
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


def test_api_base_url_falls_back_to_qsettings(monkeypatch, fake_qsettings):
    settings, store = fake_qsettings
    store['cloud/api_base_url'] = 'http://from-settings/v1'

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_api_base_url
        assert _resolve_api_base_url() == 'http://from-settings/v1'


def test_api_base_url_falls_back_to_compiled_default(monkeypatch, fake_qsettings):
    settings, _store = fake_qsettings

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_api_base_url
        assert _resolve_api_base_url() == (
            'https://eedquprtdxpfbtkppqio.supabase.co/functions/v1/artisan-api'
        )
```

- [ ] **Step 2: Run the new tests to confirm failure**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_config_resolution.py -v 2>&1 | tail -20
```
Expected: All four tests FAIL with `ImportError` / `AttributeError: module 'plus.config' has no attribute '_resolve_api_base_url'`.

- [ ] **Step 3: Implement `_resolve_api_base_url()` in config.py**

Open `src/plus/config.py`. Replace lines 37-55 (the existing URL block) with:

```python
# Service URLs (dynamic resolution: env > QSettings > compiled default)

import os
from PyQt6.QtCore import QSettings


_DEFAULT_API_BASE_URL: Final[str] = 'https://eedquprtdxpfbtkppqio.supabase.co/functions/v1/artisan-api'
_DEFAULT_WEB_BASE_URL: Final[str] = 'http://localhost:3000'


def _resolve_api_base_url() -> str:
    env = os.environ.get('MYSPRESSO_API_URL')
    if env:
        return env.rstrip('/')
    settings = QSettings()
    stored = settings.value('cloud/api_base_url', '', type=str)
    if stored:
        return str(stored).rstrip('/')
    return _DEFAULT_API_BASE_URL


api_base_url: str = _resolve_api_base_url()
web_base_url: str = _DEFAULT_WEB_BASE_URL  # will be replaced in Task 3

shop_base_url: Final[str] = 'https://buy.artisan.plus/'  # left unchanged for now

register_url: str = web_base_url + '/register'
reset_passwd_url: str = web_base_url + '/resetPassword'
auth_url: str = api_base_url + '/accounts/users/authenticate'
stock_url: str = api_base_url + '/acoffees'
roast_url: str = api_base_url + '/aroast'
lock_schedule_url: str = api_base_url + '/aschedule/lock'
notifications_url: str = api_base_url + '/notifications'
```

Note: we drop `Final[str]` on the URLs because they are now computed dynamically. `Final` stays on the defaults.

- [ ] **Step 4: Run the tests again to confirm pass**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_config_resolution.py -v 2>&1 | tail -20
```
Expected: all 4 tests PASS.

- [ ] **Step 5: Run ruff and mypy on the modified file**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check plus/config.py test/unitary/test_config_resolution.py
mypy plus/config.py 2>&1 | tail -5
```
Expected: 0 errors (or no new errors vs baseline).

- [ ] **Step 6: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/plus/config.py src/test/unitary/test_config_resolution.py
git commit -m "feat(config): resolve api_base_url dynamically (env > QSettings > default)"
```

---

## Task 3: Config — `_resolve_web_base_url()`

Same pattern for the web URL.

**Files:**
- Modify: `src/plus/config.py`
- Modify: `src/test/unitary/test_config_resolution.py`

- [ ] **Step 1: Add failing tests for web URL resolution**

Append to `src/test/unitary/test_config_resolution.py`:

```python
def test_web_base_url_uses_env_var_first(monkeypatch, fake_qsettings):
    settings, store = fake_qsettings
    store['cloud/web_base_url'] = 'http://from-settings'
    monkeypatch.setenv('MYSPRESSO_WEB_URL', 'http://from-env')

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_web_base_url
        assert _resolve_web_base_url() == 'http://from-env'


def test_web_base_url_falls_back_to_default(monkeypatch, fake_qsettings):
    settings, _store = fake_qsettings

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_web_base_url
        assert _resolve_web_base_url() == 'http://localhost:3000'
```

- [ ] **Step 2: Run failing tests**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_config_resolution.py::test_web_base_url_uses_env_var_first test/unitary/test_config_resolution.py::test_web_base_url_falls_back_to_default -v
```
Expected: both FAIL with `ImportError`.

- [ ] **Step 3: Implement in config.py**

In `src/plus/config.py`, after `_resolve_api_base_url()` (in the same block from Task 2), add:

```python
def _resolve_web_base_url() -> str:
    env = os.environ.get('MYSPRESSO_WEB_URL')
    if env:
        return env.rstrip('/')
    settings = QSettings()
    stored = settings.value('cloud/web_base_url', '', type=str)
    if stored:
        return str(stored).rstrip('/')
    return _DEFAULT_WEB_BASE_URL
```

Then change the assignment:
```python
web_base_url: str = _resolve_web_base_url()
```
(replacing the previous `web_base_url: str = _DEFAULT_WEB_BASE_URL` line).

- [ ] **Step 4: Run all config tests**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_config_resolution.py -v
```
Expected: 6 tests PASS.

- [ ] **Step 5: Lint check**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check plus/config.py
```
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/plus/config.py src/test/unitary/test_config_resolution.py
git commit -m "feat(config): resolve web_base_url dynamically"
```

---

## Task 4: Config — `auth_enabled` flag

Add the boolean flag that gates the auth bypass behaviour.

**Files:**
- Modify: `src/plus/config.py`
- Modify: `src/test/unitary/test_config_resolution.py`

- [ ] **Step 1: Add failing tests**

Append to `src/test/unitary/test_config_resolution.py`:

```python
def test_auth_enabled_defaults_to_false(monkeypatch, fake_qsettings):
    settings, _store = fake_qsettings

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_auth_enabled
        assert _resolve_auth_enabled() is False


def test_auth_enabled_true_from_env(monkeypatch, fake_qsettings):
    settings, _store = fake_qsettings
    monkeypatch.setenv('MYSPRESSO_AUTH_ENABLED', 'true')

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_auth_enabled
        assert _resolve_auth_enabled() is True


def test_auth_enabled_false_from_env_overrides_qsettings(monkeypatch, fake_qsettings):
    settings, store = fake_qsettings
    store['cloud/auth_enabled'] = True
    monkeypatch.setenv('MYSPRESSO_AUTH_ENABLED', 'false')

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_auth_enabled
        assert _resolve_auth_enabled() is False


def test_auth_enabled_from_qsettings_when_env_unset(monkeypatch, fake_qsettings):
    settings, store = fake_qsettings
    store['cloud/auth_enabled'] = True

    with patch('plus.config.QSettings', return_value=settings):
        from plus.config import _resolve_auth_enabled
        assert _resolve_auth_enabled() is True
```

- [ ] **Step 2: Run failing tests**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_config_resolution.py -k auth_enabled -v
```
Expected: 4 tests FAIL with `ImportError`.

- [ ] **Step 3: Implement in config.py**

In `src/plus/config.py`, after `_resolve_web_base_url()`, add:

```python
def _resolve_auth_enabled() -> bool:
    env = os.environ.get('MYSPRESSO_AUTH_ENABLED')
    if env is not None:
        return env.strip().lower() == 'true'
    settings = QSettings()
    stored = settings.value('cloud/auth_enabled', False, type=bool)
    return bool(stored)


auth_enabled: bool = _resolve_auth_enabled()
```

Place `auth_enabled` near the existing `connected` runtime variable (around line 141).

- [ ] **Step 4: Run all config tests**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_config_resolution.py -v
```
Expected: 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/plus/config.py src/test/unitary/test_config_resolution.py
git commit -m "feat(config): add auth_enabled flag (defaults to False)"
```

---

## Task 5: Connection — short-circuit `authentify()` when auth disabled

Make `authentify()` return immediately with a dummy session when `config.auth_enabled` is `False`. No HTTP call.

**Files:**
- Modify: `src/plus/connection.py` (the `authentify_method` closure starting at line 158)
- Create: `src/test/unitary/test_connection_noauth.py`

- [ ] **Step 1: Read the current `authentify_method` to know what to short-circuit**

```bash
sed -n '148,200p' /Users/lv/Documents/myspe-artisan/src/plus/connection.py
```

You should see the function signature `def authentify_method(passwd:str|None = None, keychain_success:bool = False, clear_password_cache:bool = False) -> bool:` and the start of the body.

- [ ] **Step 2: Write the failing test**

Create `src/test/unitary/test_connection_noauth.py`:

```python
#
# test_connection_noauth.py
#
# Unit tests for plus.connection auth short-circuit behaviour.

from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def reset_config_token():
    """Reset config.token between tests."""
    from plus import config
    saved_token = config.token
    saved_nickname = config.nickname
    config.token = None
    config.nickname = None
    yield
    config.token = saved_token
    config.nickname = saved_nickname


def test_authentify_returns_true_without_http_when_auth_disabled(
    monkeypatch, reset_config_token
):
    """When auth_enabled=False, authentify() must return True without HTTP."""
    from plus import config, connection
    monkeypatch.setattr(config, 'auth_enabled', False)

    with patch('plus.connection.requests') as mock_requests:
        result = connection.authentify(passwd='ignored')

    assert result is True
    assert mock_requests.post.call_count == 0
    assert mock_requests.get.call_count == 0


def test_authentify_sets_dummy_token_when_auth_disabled(
    monkeypatch, reset_config_token
):
    from plus import config, connection
    monkeypatch.setattr(config, 'auth_enabled', False)

    with patch('plus.connection.requests'):
        connection.authentify()

    assert config.token == 'noauth'
    assert config.nickname == 'local'
```

- [ ] **Step 3: Run failing tests**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_connection_noauth.py -v 2>&1 | tail -15
```
Expected: both FAIL (likely with HTTP call counts > 0 or `config.token` is `None`).

- [ ] **Step 4: Implement the short-circuit**

In `src/plus/connection.py`, find the `authentify_method` function (around line 158). Insert at the very top of its body, right after the docstring/log line:

```python
def authentify_method(passwd:str|None = None, keychain_success:bool = False, clear_password_cache:bool = False) -> bool:
    _log.debug('authentify(_,%s)', keychain_success)
    # MySpresso fork: skip authentication when disabled
    if not config.auth_enabled:
        _log.debug('authentify: auth_enabled=False, skipping HTTP and using dummy session')
        setToken('noauth', 'local')
        return True
    # ...original body continues here
```

(Place after the `_log.debug` line so the existing flow runs only when auth is enabled.)

- [ ] **Step 5: Run failing tests again**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_connection_noauth.py -v
```
Expected: both PASS.

- [ ] **Step 6: Lint + type check**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check plus/connection.py test/unitary/test_connection_noauth.py
```
Expected: 0 new errors.

- [ ] **Step 7: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/plus/connection.py src/test/unitary/test_connection_noauth.py
git commit -m "feat(connection): short-circuit authentify when auth_enabled=False"
```

---

## Task 6: Connection — omit `Authorization` header when auth disabled

When `auth_enabled=False`, `sendData()` and `getData()` must omit the `Authorization` header from outgoing requests.

**Files:**
- Modify: `src/plus/connection.py` (the header-building section inside `sendData` and `getData`)
- Modify: `src/test/unitary/test_connection_noauth.py`

- [ ] **Step 1: Locate the centralised header builder**

The header construction is centralised in `getHeaders()` at line 357 of `connection.py`. The current Authorization injection sits at lines 374-377:

```python
if authorized:
    token = getToken()
    if token is not None:
        headers['Authorization'] = f'Bearer {token}'
```

A second check sits in `getData()` around line 469:

```python
if authorized and 'Authorization' not in headers:
    _log.debug('no access token')
    if not authentify():
        return None
```

Both spots must be updated to respect `config.auth_enabled`.

- [ ] **Step 2: Add failing test**

Append to `src/test/unitary/test_connection_noauth.py`:

```python
def test_authorization_header_omitted_when_auth_disabled(monkeypatch):
    """Outgoing requests must not include Authorization when auth_enabled=False."""
    from plus import config, connection
    monkeypatch.setattr(config, 'auth_enabled', False)
    monkeypatch.setattr(config, 'token', 'noauth')

    mock_response = MagicMock(status_code=200, text='{}')
    mock_response.json.return_value = {}
    with patch('plus.connection.requests.get', return_value=mock_response) as mock_get:
        connection.getData('http://test/endpoint')

    headers = mock_get.call_args.kwargs.get('headers', {})
    assert 'Authorization' not in headers, f"Authorization unexpectedly present: {headers}"


def test_authorization_header_present_when_auth_enabled(monkeypatch):
    """Sanity: Authorization header IS present when auth_enabled=True."""
    from plus import config, connection
    monkeypatch.setattr(config, 'auth_enabled', True)
    monkeypatch.setattr(config, 'token', 'real-token-xyz')

    mock_response = MagicMock(status_code=200, text='{}')
    mock_response.json.return_value = {}
    with patch('plus.connection.requests.get', return_value=mock_response) as mock_get:
        connection.getData('http://test/endpoint')

    headers = mock_get.call_args.kwargs.get('headers', {})
    assert headers.get('Authorization') == 'Bearer real-token-xyz'
```

- [ ] **Step 3: Run failing tests**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_connection_noauth.py::test_authorization_header_omitted_when_auth_disabled test/unitary/test_connection_noauth.py::test_authorization_header_present_when_auth_enabled -v
```
Expected: first FAILS (header present when it shouldn't be); second passes or fails depending on existing impl.

- [ ] **Step 4: Implement conditional header omission**

In `src/plus/connection.py`, update `getHeaders()` around line 374:

```python
if authorized and config.auth_enabled:
    token = getToken()
    if token is not None:
        headers['Authorization'] = f'Bearer {token}'
```

(Added `and config.auth_enabled` to the condition.)

Then update `getData()` around line 469 to avoid the redundant `authentify()` recall when auth is disabled:

```python
if authorized and config.auth_enabled and 'Authorization' not in headers:
    _log.debug('no access token')
    if not authentify():
        return None
```

There is a similar pattern in `sendData()` (around lines 432-440 — `if authorized and r.status_code == 401`). Inspect it and apply the same `config.auth_enabled` guard if it would attempt a re-auth on 401 — when auth is disabled, a 401 should not trigger re-auth. Wrap that block:

```python
if authorized and config.auth_enabled and r.status_code == 401:
    # ... existing re-auth logic ...
```

(Run `grep -n "401" /Users/lv/Documents/myspe-artisan/src/plus/connection.py` to confirm the exact line numbers before editing.)

- [ ] **Step 5: Run tests**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_connection_noauth.py -v
```
Expected: all 4 tests in the file PASS.

- [ ] **Step 6: Lint**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check plus/connection.py
```
Expected: 0 new errors.

- [ ] **Step 7: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/plus/connection.py src/test/unitary/test_connection_noauth.py
git commit -m "feat(connection): omit Authorization header when auth_enabled=False"
```

---

## Task 7: Controller — skip Login dialog when auth disabled

When `auth_enabled=False`, `plus.controller.connect()` must skip the Login dialog and go straight to `authentify()` (which will short-circuit thanks to Task 5).

**Files:**
- Modify: `src/plus/controller.py` (the `connect()` function, around line 130)

- [ ] **Step 1: Re-read the relevant block**

```bash
sed -n '130,200p' /Users/lv/Documents/myspe-artisan/src/plus/controller.py
```
You should see the `if interactive and (...):` block that triggers `plus.login.plus_login(...)`.

- [ ] **Step 2: Modify the `connect()` function**

In `src/plus/controller.py`, find the block starting around line 170:
```python
                if interactive and (
                    aw.plus_account is None
                    or config_passwd is None
                ):  # @UndefinedVariable
                    # ask user for credentials
                    import plus.login
                    ...
```

Replace the `if interactive and (...)` condition with:
```python
                if (
                    config.auth_enabled
                    and interactive
                    and (
                        aw.plus_account is None
                        or config_passwd is None
                    )
                ):  # @UndefinedVariable
                    # ask user for credentials
                    import plus.login
                    ...
```

Then, immediately after the `if (...) else` chain that handles the dialog result, add a fallback that sets a synthetic account when `auth_enabled=False`. Inside the existing `if aw is not None:` block, before the `if aw.plus_account is None:` check (around line 236), insert:

```python
                # MySpresso fork: when auth disabled, treat the user as already authenticated
                if not config.auth_enabled and aw.plus_account is None:
                    aw.plus_account = 'local'
                    aw.plus_email = None
                    config_passwd = None
```

- [ ] **Step 3: Smoke check — import the module**

```bash
cd /Users/lv/Documents/myspe-artisan/src
python -c "from plus import controller; print('controller imports OK')"
```
Expected: `controller imports OK`. (If it errors, fix the syntax.)

- [ ] **Step 4: Lint**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check plus/controller.py
```
Expected: 0 new errors.

- [ ] **Step 5: Manual GUI smoke test**

```bash
cd /Users/lv/Documents/myspe-artisan/src
MYSPRESSO_AUTH_ENABLED=false MYSPRESSO_API_URL=http://localhost:8000/v1 python artisan.py
```
Expected: Artisan launches without the Login dialog opening. (The app may show a "connection error" since localhost:8000 isn't running — that's fine, we only care that no login was prompted.) Close the app.

- [ ] **Step 6: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/plus/controller.py
git commit -m "feat(controller): bypass Login dialog when auth_enabled=False"
```

---

## Task 8: Settings dialog — new standalone QDialog

A small dialog to edit the API URL, Web URL, and auth toggle. Reads/writes `cloud/*` QSettings keys.

**Files:**
- Create: `src/artisanlib/myspresso_settings_dialog.py`

- [ ] **Step 1: Create the dialog file**

Create `src/artisanlib/myspresso_settings_dialog.py`:

```python
#
# myspresso_settings_dialog.py
#
# Standalone Qt dialog to edit the MySpresso cloud configuration
# (API URL, Web URL, auth toggle). Values are stored in QSettings
# under the 'cloud/' prefix and take effect after the application
# is restarted.

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QCheckBox, QPushButton, QVBoxLayout, QWidget,
)


class MyspressoSettingsDialog(QDialog):
    """Edit MySpresso cloud configuration (URL endpoints, auth toggle)."""

    def __init__(self, parent: 'QWidget | None' = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('MySpresso Cloud Settings')
        self.setModal(True)

        self._settings = QSettings()

        self._api_edit = QLineEdit(
            self._settings.value('cloud/api_base_url', '', type=str)
        )
        self._api_edit.setPlaceholderText('http://localhost:8000/v1')

        self._web_edit = QLineEdit(
            self._settings.value('cloud/web_base_url', '', type=str)
        )
        self._web_edit.setPlaceholderText('http://localhost:3000')

        self._auth_check = QCheckBox('Enable authentication')
        self._auth_check.setChecked(
            bool(self._settings.value('cloud/auth_enabled', False, type=bool))
        )

        reset_btn = QPushButton('Reset to defaults')
        reset_btn.clicked.connect(self._reset_defaults)

        form = QFormLayout()
        form.addRow('API endpoint:', self._api_edit)
        form.addRow('Web endpoint:', self._web_edit)
        form.addRow('', self._auth_check)
        form.addRow('', reset_btn)

        note = QLabel('Restart required after changes.')
        note.setStyleSheet('color: gray; font-style: italic;')

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _save_and_accept(self) -> None:
        self._settings.setValue('cloud/api_base_url', self._api_edit.text().strip())
        self._settings.setValue('cloud/web_base_url', self._web_edit.text().strip())
        self._settings.setValue('cloud/auth_enabled', self._auth_check.isChecked())
        self._settings.sync()
        self.accept()

    def _reset_defaults(self) -> None:
        self._api_edit.clear()
        self._web_edit.clear()
        self._auth_check.setChecked(False)
```

- [ ] **Step 2: Smoke import**

```bash
cd /Users/lv/Documents/myspe-artisan/src
python -c "from artisanlib.myspresso_settings_dialog import MyspressoSettingsDialog; print('dialog imports OK')"
```
Expected: `dialog imports OK`.

- [ ] **Step 3: Lint + type check**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check artisanlib/myspresso_settings_dialog.py
mypy artisanlib/myspresso_settings_dialog.py 2>&1 | tail -5
```
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/artisanlib/myspresso_settings_dialog.py
git commit -m "feat(ui): add MySpresso cloud settings dialog"
```

---

## Task 9: Wire settings dialog to the main menu

Add a menu entry that opens the new dialog.

**Files:**
- Modify: `src/artisanlib/main.py` (find the existing "Help" or top-level menu setup; add a new "MySpresso → Settings…" entry, or under an existing menu).

- [ ] **Step 1: Locate where menus are constructed**

```bash
grep -n "self.helpMenu\|self.menuBar\|addMenu\(.*Help" /Users/lv/Documents/myspe-artisan/src/artisanlib/main.py | head -10
```
Identify the most appropriate menu to host the new entry (typically the Help menu or a Plus/Cloud submenu if one exists).

- [ ] **Step 2: Add the menu action**

In `src/artisanlib/main.py`, in the menu construction code (likely inside `ApplicationWindow.__init__` or a `setupMenu` method), add an action. Example (adjust path to match the codebase style):

```python
# MySpresso settings entry (added by fork)
self.myspressoSettingsAction = QAction(
    QApplication.translate('Menu', 'MySpresso Settings…'),
    self,
)
self.myspressoSettingsAction.triggered.connect(self._openMyspressoSettings)
# Add to whichever menu makes sense (Help is a safe default):
self.helpMenu.addAction(self.myspressoSettingsAction)
```

Then add the slot method inside the same class:

```python
def _openMyspressoSettings(self) -> None:
    from artisanlib.myspresso_settings_dialog import MyspressoSettingsDialog
    dlg = MyspressoSettingsDialog(self)
    dlg.exec()
```

(Place the slot somewhere near other small dialog-opening slots; if unsure, add it after the existing `__init__` method.)

- [ ] **Step 3: Smoke import**

```bash
cd /Users/lv/Documents/myspe-artisan/src
python -c "import artisanlib.main" 2>&1 | tail -5
```
Expected: no errors.

- [ ] **Step 4: Manual GUI test**

```bash
cd /Users/lv/Documents/myspe-artisan/src
python artisan.py
```
Open the Help menu (or wherever the entry was added), click "MySpresso Settings…". Verify the dialog opens with three editable fields and a Reset button. Type a test URL, OK, reopen — verify it persisted (QSettings).

Reset by clearing the field manually or via Reset button; close.

- [ ] **Step 5: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/artisanlib/main.py
git commit -m "feat(ui): add MySpresso Settings menu entry"
```

---

## Task 10: Cosmetic rebranding pass

Rebrand the most visible user-facing strings from "artisan.plus" to "MySpresso". **Scope is intentionally narrow**: only what the user sees in primary UI elements. Comments, internal variable names, and translation files are out of scope.

**Files:**
- Modify: `src/plus/login.py` (window title)
- Modify: `src/artisanlib/main.py` (visible labels/menus that contain literal `'artisan.plus'`)

- [ ] **Step 1: Inventory the visible occurrences**

```bash
cd /Users/lv/Documents/myspe-artisan/src
grep -n "'artisan.plus'\|\"artisan.plus\"" plus/login.py artisanlib/main.py | head -20
```
Record the lines. Skip lines that are clearly comments (start with `#`) or programmatic identifiers (e.g., `to = 'logfile@artisan.plus'` is a hard-coded email — leave it for now and document in the spec's "decisions ouvertes").

- [ ] **Step 2: Rebrand login window title**

In `src/plus/login.py` line 214 (search for `setWindowTitle('plus')`):
```python
ld.setWindowTitle('MySpresso')
```
(replacing `'plus'`).

- [ ] **Step 3: Rebrand visible occurrences in main.py**

For each line found in Step 1 that is a **UI string** (passed to `QApplication.translate(...)`, `setText(...)`, `setTitle(...)`, or status messages), replace `"artisan.plus"` with `"MySpresso"`.

Do **not** replace:
- Comments (`# artisan.plus ...`)
- The `config.app_name = 'artisan.plus'` constant (used for keyring keying — changing it would lose any existing keychain entries)
- URLs containing `artisan.plus` (those are handled by config resolution)
- Internal symbol names (`plus_account`, `plus_email`, etc.)

- [ ] **Step 4: Smoke import**

```bash
cd /Users/lv/Documents/myspe-artisan/src
python -c "from plus import login; import artisanlib.main" 2>&1 | tail -5
```
Expected: no errors.

- [ ] **Step 5: Manual GUI verification**

```bash
cd /Users/lv/Documents/myspe-artisan/src
MYSPRESSO_AUTH_ENABLED=true python artisan.py
```
Trigger the login dialog (Help → Connect, or whichever menu invokes login). Verify:
- Dialog title shows "MySpresso" (not "plus").
- No leftover "artisan.plus" labels in the dialog itself.

Close the app.

- [ ] **Step 6: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/plus/login.py src/artisanlib/main.py
git commit -m "chore(ui): rebrand visible 'artisan.plus' strings to 'MySpresso'"
```

---

## Task 11: Final verification

End-to-end check that everything still works and nothing regressed.

**Files:** none modified.

- [ ] **Step 1: Run the full unit test suite for our new code**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/test_config_resolution.py test/unitary/test_connection_noauth.py -v
```
Expected: all 12 tests PASS (6 config + 4 auth_enabled + 4 connection — verify counts match what you wrote).

- [ ] **Step 2: Run the existing sanity suite**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/sanity/ -x -q 2>&1 | tail -10
```
Expected: same result as the baseline recorded in Task 1.

- [ ] **Step 3: Run ruff on the full plus/ and on new files**

```bash
cd /Users/lv/Documents/myspe-artisan/src
ruff check plus/ artisanlib/myspresso_settings_dialog.py test/unitary/test_config_resolution.py test/unitary/test_connection_noauth.py 2>&1 | tail -10
```
Expected: no new errors vs the Task 1 baseline.

- [ ] **Step 4: Run mypy on touched files**

```bash
cd /Users/lv/Documents/myspe-artisan/src
mypy plus/config.py plus/connection.py plus/controller.py artisanlib/myspresso_settings_dialog.py 2>&1 | tail -10
```
Expected: no new errors.

- [ ] **Step 5: Network smoke test**

Start a mock server in one terminal:

```bash
python3 -m http.server 8000
```
(This will respond 200 to GET / and 404 to any other path — sufficient to confirm Artisan is hitting localhost:8000.)

In another terminal:

```bash
cd /Users/lv/Documents/myspe-artisan/src
MYSPRESSO_AUTH_ENABLED=false MYSPRESSO_API_URL=http://localhost:8000/v1 python artisan.py
```

In Artisan, attempt to connect to the cloud (Help → Connect or the toolbar plus icon). Watch the http.server logs: you should see GET/POST requests arriving at `http://localhost:8000/...`. **No** requests should appear targeting `artisan.plus`.

(Use `lsof -i :8000` or `tcpdump -i lo0 port 443` to confirm no traffic leaves to `artisan.plus`.)

- [ ] **Step 6: Final git log review**

```bash
cd /Users/lv/Documents/myspe-artisan
git log --oneline -15
```
Expected: a clean sequence of commits, each with a focused scope.

- [ ] **Step 7: No final commit (verification only).** Report completion to the user.

---

## Acceptance criteria (from spec)

When all tasks are complete:

- [x] The fork no longer contacts `artisan.plus` (verified by network capture in Task 11 Step 5).
- [x] All cloud features (login bypass, stock fetch, blend picker, schedule, push roast, sync delta, lock schedule, notifications) operational against the new endpoint.
- [x] Endpoint configurable without recompilation (env + UI).
- [x] No regression on the rest of the app (verified by Tasks 1 & 11 baseline comparison).
- [x] `ruff` and `mypy` strict remain green (Task 11).
- [x] Unit tests for config resolution and connection auth bypass exist and pass.

## Out of scope (deferred, intentionally)

- Translation files (`.ts`/`.qm`) — strings will be partially mixed until next translation campaign.
- The `config.app_name = 'artisan.plus'` constant (kept for keyring backward compatibility).
- `shop_base_url`, the `mailto:logfile@artisan.plus` hard-coded address — covered in a future RFC.
- Icon replacement for the plus status indicator.
- PyInstaller / AppVeyor packaging configuration updates.
- Future re-introduction of authentication once the MySpresso backend supports it (will only require flipping `MYSPRESSO_AUTH_ENABLED=true`).
