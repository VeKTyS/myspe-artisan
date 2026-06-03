from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# UpdateChecker
# ---------------------------------------------------------------------------

def _make_response(tag: str, assets: list[dict]) -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {'tag_name': tag, 'assets': assets}
    return r


def test_checker_emits_when_newer_version_available_on_mac():
    from artisanlib.updater import UpdateChecker

    mock_resp = _make_response('v9.9.9', [
        {'name': 'artisan-mac-9.9.9.dmg',
         'browser_download_url': 'https://example.com/artisan-mac-9.9.9.dmg',
         'size': 12345},
    ])
    emitted: list[tuple] = []

    with patch('artisanlib.updater.requests') as mock_req, \
         patch('artisanlib.updater.sys') as mock_sys, \
         patch('artisanlib.updater.QSettings') as mock_qs:
        mock_req.get.return_value = mock_resp
        mock_sys.platform = 'darwin'
        mock_qs.return_value.value.return_value = ''

        checker = UpdateChecker()
        checker.update_available.connect(lambda v, u, n, s: emitted.append((v, u, n, s)))
        checker.run()

    assert len(emitted) == 1
    version, url, name, size = emitted[0]
    assert version == '9.9.9'
    assert 'artisan-mac-9.9.9.dmg' in url
    assert name == 'artisan-mac-9.9.9.dmg'
    assert size == 12345


def test_checker_emits_when_newer_version_available_on_windows():
    from artisanlib.updater import UpdateChecker

    mock_resp = _make_response('v9.9.9', [
        {'name': 'zabawa-roast-win-9.9.9.exe',
         'browser_download_url': 'https://example.com/zabawa-roast-win-9.9.9.exe',
         'size': 55000},
    ])
    emitted: list[tuple] = []

    with patch('artisanlib.updater.requests') as mock_req, \
         patch('artisanlib.updater.sys') as mock_sys, \
         patch('artisanlib.updater.QSettings') as mock_qs:
        mock_req.get.return_value = mock_resp
        mock_sys.platform = 'win32'
        mock_qs.return_value.value.return_value = ''

        checker = UpdateChecker()
        checker.update_available.connect(lambda v, u, n, s: emitted.append((v, u, n, s)))
        checker.run()

    assert len(emitted) == 1
    assert emitted[0][2] == 'zabawa-roast-win-9.9.9.exe'


def test_checker_silent_when_already_on_latest():
    from artisanlib import __version__
    from artisanlib.updater import UpdateChecker

    mock_resp = _make_response(f'v{__version__}', [])
    emitted: list[tuple] = []

    with patch('artisanlib.updater.requests') as mock_req, \
         patch('artisanlib.updater.QSettings') as mock_qs:
        mock_req.get.return_value = mock_resp
        mock_qs.return_value.value.return_value = ''

        checker = UpdateChecker()
        checker.update_available.connect(lambda *a: emitted.append(a))
        checker.run()

    assert emitted == []


def test_checker_respects_skipped_version():
    from artisanlib.updater import UpdateChecker

    mock_resp = _make_response('v9.9.9', [
        {'name': 'artisan-mac-9.9.9.dmg',
         'browser_download_url': 'https://example.com/artisan-mac-9.9.9.dmg',
         'size': 0},
    ])
    emitted: list[tuple] = []

    with patch('artisanlib.updater.requests') as mock_req, \
         patch('artisanlib.updater.sys') as mock_sys, \
         patch('artisanlib.updater.QSettings') as mock_qs:
        mock_req.get.return_value = mock_resp
        mock_sys.platform = 'darwin'
        mock_qs.return_value.value.return_value = '9.9.9'  # already dismissed

        checker = UpdateChecker()
        checker.update_available.connect(lambda *a: emitted.append(a))
        checker.run()

    assert emitted == []


def test_checker_swallows_network_error():
    from artisanlib.updater import UpdateChecker

    emitted: list[tuple] = []

    with patch('artisanlib.updater.requests') as mock_req, \
         patch('artisanlib.updater.QSettings'):
        mock_req.get.side_effect = ConnectionError('no network')

        checker = UpdateChecker()
        checker.update_available.connect(lambda *a: emitted.append(a))
        checker.run()

    assert emitted == []


def test_checker_swallows_bad_json():
    from artisanlib.updater import UpdateChecker
    import json

    emitted: list[tuple] = []

    with patch('artisanlib.updater.requests') as mock_req, \
         patch('artisanlib.updater.QSettings'):
        bad = MagicMock()
        bad.status_code = 200
        bad.json.side_effect = json.JSONDecodeError('', '', 0)
        mock_req.get.return_value = bad

        checker = UpdateChecker()
        checker.update_available.connect(lambda *a: emitted.append(a))
        checker.run()

    assert emitted == []


# ---------------------------------------------------------------------------
# UpdateDownloader
# ---------------------------------------------------------------------------

def test_downloader_streams_file_and_reports_progress(tmp_path):
    from artisanlib.updater import UpdateDownloader

    chunk = b'x' * 1000
    mock_resp = MagicMock()
    mock_resp.headers = {'content-length': '2000'}
    mock_resp.iter_content.return_value = [chunk, chunk]

    progress_vals: list[int] = []
    finished_path: list[str] = []

    with patch('artisanlib.updater.requests') as mock_req:
        mock_req.get.return_value = mock_resp

        dl = UpdateDownloader(
            'https://example.com/update.dmg',
            str(tmp_path),
            expected_size=2000,
        )
        dl.progress.connect(progress_vals.append)
        dl.finished.connect(finished_path.append)
        dl.run()

    assert finished_path == [str(tmp_path / 'update.dmg')]
    assert os.path.exists(finished_path[0])
    assert 100 in progress_vals


def test_downloader_emits_error_on_size_mismatch(tmp_path):
    from artisanlib.updater import UpdateDownloader

    chunk = b'x' * 500  # only 500 bytes
    mock_resp = MagicMock()
    mock_resp.headers = {'content-length': '500'}
    mock_resp.iter_content.return_value = [chunk]

    errors: list[str] = []
    finished: list[str] = []

    with patch('artisanlib.updater.requests') as mock_req:
        mock_req.get.return_value = mock_resp

        dl = UpdateDownloader(
            'https://example.com/update.dmg',
            str(tmp_path),
            expected_size=1000,  # mismatch: expected 1000, got 500
        )
        dl.error.connect(errors.append)
        dl.finished.connect(finished.append)
        dl.run()

    assert finished == []
    assert len(errors) == 1
    assert 'mismatch' in errors[0]


def test_downloader_emits_error_on_failure(tmp_path):
    from artisanlib.updater import UpdateDownloader

    errors: list[str] = []

    with patch('artisanlib.updater.requests') as mock_req:
        mock_req.get.side_effect = ConnectionError('timeout')

        dl = UpdateDownloader('https://example.com/update.dmg', str(tmp_path))
        dl.error.connect(errors.append)
        dl.run()

    assert len(errors) == 1
    assert 'timeout' in errors[0]


# ---------------------------------------------------------------------------
# run_updater_and_quit — script generation
# ---------------------------------------------------------------------------

def test_run_updater_macos_writes_and_launches_sh_script(tmp_path, monkeypatch):
    from artisanlib.updater import run_updater_and_quit

    fake_exe = tmp_path / 'Zabawa Roast.app' / 'Contents' / 'MacOS' / 'Zabawa Roast'
    fake_exe.parent.mkdir(parents=True)
    fake_exe.touch()

    monkeypatch.setattr('artisanlib.updater.sys.platform', 'darwin')
    monkeypatch.setattr('artisanlib.updater.sys.executable', str(fake_exe))
    monkeypatch.setattr('artisanlib.updater.tempfile.gettempdir', lambda: str(tmp_path))

    launched: list[list] = []
    monkeypatch.setattr('artisanlib.updater.subprocess.Popen',
                        lambda cmd, **kw: launched.append(list(cmd)))

    mock_app = MagicMock()
    monkeypatch.setattr('artisanlib.updater.QApplication.instance', lambda: mock_app)

    run_updater_and_quit('/tmp/update.dmg')

    assert len(launched) == 1
    assert launched[0][0] == '/bin/bash'
    script_path = launched[0][1]
    assert os.path.exists(script_path)
    content = Path(script_path).read_text()
    assert 'hdiutil attach' in content
    assert '/tmp/update.dmg' in content
    assert 'rsync' in content
    assert mock_app.quit.called


def test_run_updater_windows_writes_and_launches_bat_script(tmp_path, monkeypatch):
    from artisanlib.updater import run_updater_and_quit

    fake_exe = tmp_path / 'Zabawa Roast.exe'
    fake_exe.touch()

    monkeypatch.setattr('artisanlib.updater.sys.platform', 'win32')
    monkeypatch.setattr('artisanlib.updater.sys.executable', str(fake_exe))
    monkeypatch.setattr('artisanlib.updater.tempfile.gettempdir', lambda: str(tmp_path))

    launched: list[list] = []
    monkeypatch.setattr('artisanlib.updater.subprocess.Popen',
                        lambda cmd, **kw: launched.append(list(cmd)))

    mock_app = MagicMock()
    monkeypatch.setattr('artisanlib.updater.QApplication.instance', lambda: mock_app)

    run_updater_and_quit('C:\\tmp\\update.exe')

    assert len(launched) == 1
    assert 'cmd.exe' in launched[0][0]
    script_path = launched[0][2]
    assert script_path.endswith('.bat')
    content = Path(script_path).read_text()
    assert '/S' in content
    assert 'C:\\tmp\\update.exe' in content
    assert mock_app.quit.called


def test_run_updater_falls_back_when_not_in_app_bundle(tmp_path, monkeypatch):
    from artisanlib.updater import run_updater_and_quit

    # sys.executable is NOT inside a .app bundle
    fake_exe = tmp_path / 'Zabawa Roast'
    fake_exe.touch()

    monkeypatch.setattr('artisanlib.updater.sys.platform', 'darwin')
    monkeypatch.setattr('artisanlib.updater.sys.executable', str(fake_exe))

    fallback_called: list[str] = []
    monkeypatch.setattr('artisanlib.updater._open_folder_fallback', fallback_called.append)

    mock_app = MagicMock()
    monkeypatch.setattr('artisanlib.updater.QApplication.instance', lambda: mock_app)

    run_updater_and_quit('/tmp/update.dmg')

    assert fallback_called == ['/tmp/update.dmg']
    assert not mock_app.quit.called  # fallback path does not quit
