#!/usr/bin/env python3
"""
MySpresso API endpoint smoke test.

Pings each of the 5 endpoints Artisan expects on the MySpresso backend and
prints status + first 300 chars of the body. Useful for verifying the
backend agent's progress without launching the full Artisan GUI.

Usage:
    cd /Users/lv/Documents/myspe-artisan/src
    /Users/lv/Documents/myspe-artisan/.venv/bin/python ../scripts/smoke_test_endpoints.py

Optional override:
    MYSPRESSO_API_URL=https://custom-host/v1 python ../scripts/smoke_test_endpoints.py
"""

import datetime
import pathlib
import sys
import uuid

# Make src/ importable so `from plus import ...` works from any cwd.
_SRC = pathlib.Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(_SRC))

from PyQt6.QtCore import QCoreApplication  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

# QApplication must be alive (referenced) and named BEFORE importing plus.* —
# the `plus.account` module's cache path resolution requires it at import time.
_app = QApplication(sys.argv)
QCoreApplication.setApplicationName('Artisan')
QCoreApplication.setOrganizationName('Artisan-Scope')

from plus import config, connection  # noqa: E402


def hit(label: str, url: str, *, expect: str) -> None:
    print(f'\n=== {label} ===')
    print(f'GET {url}')
    print(f'expect: {expect}')
    try:
        r = connection.getData(url)
    except Exception as e:  # noqa: BLE001
        print(f'  ERROR: {type(e).__name__}: {str(e)[:200]}')
        return
    if r is None:
        print('  -> None (auth or connection issue)')
        return
    print(f'  status: {r.status_code}')
    body = r.text[:300] if r.text else '(empty)'
    print(f'  body: {body}')


def main() -> None:
    print(f'api_base_url = {config.api_base_url}')
    print(f'auth_enabled = {config.auth_enabled}')

    connection.authentify()
    print(f'session: token={config.token!r} nickname={config.nickname!r}')

    today = datetime.date.today().isoformat()
    epoch_ms = int(datetime.datetime.now().timestamp() * 1000)
    sample_uuid = str(uuid.uuid4())

    hit(
        'Stock',
        f'{config.stock_url}?today={today}',
        expect='200 with {coffees, blends, schedule, ...} OR 204 if lsrt unchanged',
    )

    hit(
        'Pull roast (unknown UUID is fine)',
        f'{config.roast_url}/{sample_uuid}?modified_at={epoch_ms}',
        expect='404 (uuid does not exist) or 204',
    )

    hit(
        'Notifications',
        f'{config.notifications_url}?machine=test',
        expect='200 with {notifications: [...]}',
    )

    # POST endpoints aren't exercised here because they would persist data;
    # use a proper integration test from the backend repo instead.
    print('\n(POST /aroast and POST /aschedule/lock not exercised — would write data.)')


if __name__ == '__main__':
    main()
