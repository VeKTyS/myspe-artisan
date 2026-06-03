# Auto-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a background update check at startup that shows a banner when a newer version is published on GitHub, and lets the user install it silently with one click (macOS + Windows).

**Architecture:** A standalone `updater.py` module contains three classes (`UpdateChecker`, `UpdateDownloader`, `UpdateBanner`) and two functions (`run_updater_and_quit`, `_open_folder_fallback`). `main.py` wires the startup timer and inserts the banner into the existing `mainlayout`. The update installs via a platform-specific helper script written to `/tmp` after the app exits, so no files are replaced while in use.

**Tech Stack:** PyQt6 (QThread, QFrame, QProgressBar), `requests` (already a dependency), `subprocess`, `hdiutil` (macOS), NSIS `/S` flag (Windows). Tests use `pytest` + `unittest.mock`.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/artisanlib/updater.py` | All update logic: checker, downloader, banner widget, installer launcher |
| Modify | `src/artisanlib/main.py` | Add startup timer, `_start_update_check`, `_show_update_banner`; fix `checkUpdate()` URL |
| Create | `src/test/unitary/artisanlib/test_updater.py` | Unit tests for checker, downloader, script generation |

---

## Task 1: Skeleton + failing tests for `UpdateChecker`

**Files:**
- Create: `src/test/unitary/artisanlib/test_updater.py`
- Create: `src/artisanlib/updater.py` (skeleton only — empty classes so imports resolve)

- [ ] **Step 1: Create the updater skeleton**

Create `src/artisanlib/updater.py` with this content:

```python
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from PyQt6.QtCore import QSettings, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QProgressBar, QPushButton,
)

GITHUB_API_URL = 'https://api.github.com/repos/VeKTyS/myspe-artisan/releases/latest'


class UpdateChecker(QThread):
    update_available: pyqtSignal = pyqtSignal(str, str, str, int)
    # emits: (version, download_url, asset_name, asset_size)

    def run(self) -> None:
        pass  # TODO


class UpdateDownloader(QThread):
    progress: pyqtSignal = pyqtSignal(int)
    finished: pyqtSignal = pyqtSignal(str)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(self, url: str, dest_dir: str, expected_size: int = 0) -> None:
        super().__init__()
        self._url = url
        self._dest_dir = dest_dir
        self._expected_size = expected_size

    def run(self) -> None:
        pass  # TODO


class UpdateBanner(QFrame):
    def __init__(self, version: str, asset_url: str, asset_name: str,
                 asset_size: int = 0, parent=None) -> None:
        super().__init__(parent)
        pass  # TODO


def run_updater_and_quit(asset_path: str) -> None:
    pass  # TODO


def _open_folder_fallback(path: str) -> None:
    folder = os.path.dirname(path)
    if sys.platform == 'darwin':
        subprocess.Popen(['open', folder])
    elif sys.platform == 'win32':
        subprocess.Popen(['explorer', folder])
```

- [ ] **Step 2: Write failing tests for `UpdateChecker`**

Create `src/test/unitary/artisanlib/test_updater.py`:

```python
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
```

- [ ] **Step 3: Run tests — confirm they all fail for the right reasons**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/artisanlib/test_updater.py -v 2>&1 | head -60
```

Expected: all tests FAIL with `NotImplementedError` or assertion errors (the skeleton `run()` methods do nothing yet).

---

## Task 2: Implement `UpdateChecker` and `UpdateDownloader`

**Files:**
- Modify: `src/artisanlib/updater.py`

- [ ] **Step 1: Replace the `UpdateChecker.run()` stub**

In `src/artisanlib/updater.py`, replace `def run(self) -> None: pass  # TODO` inside `UpdateChecker` with:

```python
    def run(self) -> None:
        from artisanlib import __version__
        import json as _json

        settings = QSettings()
        skipped: str = settings.value('updater/skipped_version', '', type=str)

        try:
            r = requests.get(GITHUB_API_URL, timeout=(2, 4))
            if r.status_code != 200:
                return
            data = r.json()
        except Exception:
            return

        tag_name: str = data.get('tag_name', '')
        match = re.search(r'[\d.]+', tag_name)
        if not match:
            return
        latest: str = match.group(0)

        if latest <= __version__ or latest == skipped:
            return

        platform_key = 'artisan-mac' if sys.platform == 'darwin' else 'zabawa-roast-win'
        for asset in data.get('assets', []):
            name: str = asset.get('name', '')
            if platform_key in name:
                url: str = asset['browser_download_url']
                size: int = asset.get('size', 0)
                self.update_available.emit(latest, url, name, size)
                return
```

- [ ] **Step 2: Replace the `UpdateDownloader.run()` stub**

In `src/artisanlib/updater.py`, replace `def run(self) -> None: pass  # TODO` inside `UpdateDownloader` with:

```python
    def run(self) -> None:
        filename = self._url.split('/')[-1]
        dest_path = os.path.join(self._dest_dir, filename)

        try:
            r = requests.get(self._url, stream=True, timeout=(5, 120))
            total = self._expected_size or int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded * 100 / total))
            # Integrity check: verify file size matches the expected asset size
            if self._expected_size and os.path.getsize(dest_path) != self._expected_size:
                self.error.emit(
                    f'File size mismatch: expected {self._expected_size},'
                    f' got {os.path.getsize(dest_path)}'
                )
                return
            self.finished.emit(dest_path)
        except Exception as exc:
            self.error.emit(str(exc))
```

- [ ] **Step 3: Run the checker + downloader tests — they should pass**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/artisanlib/test_updater.py -k "checker or downloader" -v
```

Expected output: all 8 checker/downloader tests PASS.

- [ ] **Step 4: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/artisanlib/updater.py src/test/unitary/artisanlib/test_updater.py
git commit -m "feat(updater): add UpdateChecker and UpdateDownloader threads with tests"
```

---

## Task 3: Implement `run_updater_and_quit` + `UpdateBanner`

**Files:**
- Modify: `src/artisanlib/updater.py`

- [ ] **Step 1: Implement `run_updater_and_quit`**

Replace `def run_updater_and_quit(asset_path: str) -> None: pass  # TODO` with:

```python
def run_updater_and_quit(asset_path: str) -> None:
    pid = os.getpid()

    if sys.platform == 'darwin':
        exe = Path(sys.executable)
        # Inside a .app bundle: <bundle>.app/Contents/MacOS/<binary>
        app_bundle = exe.parent.parent.parent
        if not str(app_bundle).endswith('.app'):
            _open_folder_fallback(asset_path)
            return
        app_dir = str(app_bundle.parent)
        app_name = app_bundle.name  # e.g. "Zabawa Roast.app"

        script_path = os.path.join(tempfile.gettempdir(), f'zr_updater_{pid}.sh')
        script = (
            '#!/bin/bash\n'
            'sleep 2\n'
            f'hdiutil attach -nobrowse -quiet "{asset_path}"'
            f' -mountpoint /tmp/zr_update_{pid}\n'
            f'rsync -a --delete "/tmp/zr_update_{pid}/"*.app "{app_dir}/"\n'
            f'hdiutil detach /tmp/zr_update_{pid} -quiet\n'
            f'open "{app_dir}/{app_name}"\n'
            'rm -- "$0"\n'
        )
        with open(script_path, 'w') as f:
            f.write(script)
        os.chmod(script_path, stat.S_IRWXU)
        try:
            subprocess.Popen(
                ['/bin/bash', script_path],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            _open_folder_fallback(asset_path)
            return

    elif sys.platform == 'win32':
        exe = Path(sys.executable)
        app_exe = str(exe) if exe.suffix == '.exe' else str(exe.parent / 'Zabawa Roast.exe')

        script_path = os.path.join(tempfile.gettempdir(), f'zr_updater_{pid}.bat')
        script = (
            '@echo off\n'
            'timeout /t 2 /nobreak >nul\n'
            f'"{asset_path}" /S\n'
            f'start "" "{app_exe}"\n'
            'del "%~f0"\n'
        )
        with open(script_path, 'w') as f:
            f.write(script)
        try:
            subprocess.Popen(
                ['cmd.exe', '/c', script_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        except OSError:
            _open_folder_fallback(asset_path)
            return

    QApplication.instance().quit()
```

- [ ] **Step 2: Run the script-generation tests — they should pass**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/artisanlib/test_updater.py -k "updater" -v
```

Expected: all 3 `run_updater_and_quit` tests PASS.

- [ ] **Step 3: Implement `UpdateBanner`**

Replace `def __init__(self, ...) -> None: super().__init__(parent) pass  # TODO` inside `UpdateBanner` with:

```python
    def __init__(self, version: str, asset_url: str, asset_name: str,
                 asset_size: int = 0, parent=None) -> None:
        super().__init__(parent)
        self._version = version
        self._asset_url = asset_url
        self._asset_name = asset_name
        self._asset_size = asset_size
        self._downloader: UpdateDownloader | None = None

        self.setFixedHeight(44)
        self.setObjectName('UpdateBanner')
        self.setStyleSheet(
            'QFrame#UpdateBanner {'
            '  background: #0F1932;'
            '  border-bottom: 1px solid #A8392E;'
            '}'
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(12)

        self._label = QLabel(f'Zabawa Roast {version} est disponible')
        self._label.setStyleSheet(
            'color: #F5F1E8; font-family: Montserrat, sans-serif; font-size: 12px;'
        )

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(160)
        self._progress.setFixedHeight(16)
        self._progress.hide()

        self._update_btn = QPushButton('Mettre à jour')
        self._update_btn.setFixedHeight(28)
        self._update_btn.setStyleSheet(
            'QPushButton {'
            '  background: #A8392E; color: white; border: none;'
            '  border-radius: 4px; padding: 0 12px;'
            '  font-family: Montserrat, sans-serif; font-size: 11px; font-weight: 600;'
            '}'
            'QPushButton:hover { background: #C44236; }'
        )
        self._update_btn.clicked.connect(self._start_download)

        self._dismiss_btn = QPushButton('✕')
        self._dismiss_btn.setFixedSize(24, 24)
        self._dismiss_btn.setStyleSheet(
            'QPushButton { color: #7A8499; background: transparent; border: none; font-size: 13px; }'
            'QPushButton:hover { color: #F5F1E8; }'
        )
        self._dismiss_btn.clicked.connect(self._dismiss)

        layout.addWidget(self._label)
        layout.addStretch()
        layout.addWidget(self._progress)
        layout.addWidget(self._update_btn)
        layout.addWidget(self._dismiss_btn)

    def _start_download(self) -> None:
        from PyQt6.QtCore import QDir
        self._update_btn.hide()
        self._progress.show()
        self._label.setText('Téléchargement en cours...')
        self._dismiss_btn.setEnabled(False)

        self._downloader = UpdateDownloader(
            self._asset_url,
            QDir.tempPath(),
            self._asset_size,
        )
        self._downloader.progress.connect(self._progress.setValue)
        self._downloader.finished.connect(self._on_download_finished)
        self._downloader.error.connect(self._on_download_error)
        self._downloader.start()

    def _on_download_finished(self, path: str) -> None:
        self._label.setText('Installation en cours, fermeture…')
        self._progress.hide()
        QTimer.singleShot(800, lambda: run_updater_and_quit(path))

    def _on_download_error(self, msg: str) -> None:
        self._label.setText('Échec du téléchargement.')
        self._progress.hide()
        open_btn = QPushButton('Ouvrir le dossier')
        open_btn.setFixedHeight(28)
        open_btn.setStyleSheet(self._update_btn.styleSheet())
        # _downloader is always set before this slot can fire
        fallback_path = os.path.join(self._downloader._dest_dir, self._asset_name)  # type: ignore[union-attr]
        open_btn.clicked.connect(lambda: _open_folder_fallback(fallback_path))
        cast_layout = self.layout()
        if cast_layout is not None:
            cast_layout.insertWidget(2, open_btn)
        self._dismiss_btn.setEnabled(True)

    def _dismiss(self) -> None:
        settings = QSettings()
        settings.setValue('updater/skipped_version', self._version)
        self.hide()
        self.deleteLater()
```

- [ ] **Step 4: Run the full test suite for updater.py**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/artisanlib/test_updater.py -v
```

Expected: all tests PASS (banner has no unit tests — it's a pure Qt widget verified manually in Task 5).

- [ ] **Step 5: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/artisanlib/updater.py
git commit -m "feat(updater): add UpdateBanner widget and run_updater_and_quit helper"
```

---

## Task 4: Wire into `main.py`

**Files:**
- Modify: `src/artisanlib/main.py`

- [ ] **Step 1: Add `'update_checker'` to `__slots__` and initialize it in `__init__`**

In `src/artisanlib/main.py`, find the `__slots__` list (around line 1482). It ends with:
```python
        'myspresso_header', 'myspresso_hero', 'myspresso_eventlog', 'myspresso_stats' ]
```

Change that line to:
```python
        'myspresso_header', 'myspresso_hero', 'myspresso_eventlog', 'myspresso_stats',
        'update_checker' ]
```

Then, near the top of `__init__` (around line 1560, after `self.locale_str:str = locale`), add:
```python
        from artisanlib.updater import UpdateChecker as _UC
        self.update_checker: _UC | None = None
```

This ensures the attribute always exists in `__slots__` before any cleanup code could access it.

- [ ] **Step 2: Fix the `checkUpdate()` GitHub URL**

In `src/artisanlib/main.py`, around line 24875, find:
```python
            r = requests.get('https://api.github.com/repos/artisan-roaster-scope/artisan/releases/latest', timeout=(2,4))
```

Replace with:
```python
            r = requests.get('https://api.github.com/repos/VeKTyS/myspe-artisan/releases/latest', timeout=(2,4))
```

- [ ] **Step 3: Add `_start_update_check` and `_show_update_banner` methods**

In `src/artisanlib/main.py`, after the `_openMyspressoSettings` method (around line 3025), add these two methods. Insert them directly after the closing `dlg.exec()` line of `_openMyspressoSettings`:

```python
    def _start_update_check(self) -> None:
        from artisanlib.updater import UpdateChecker
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self._show_update_banner)
        self.update_checker.start()

    def _show_update_banner(self, version: str, url: str, name: str, size: int) -> None:
        from artisanlib.updater import UpdateBanner
        banner = UpdateBanner(version, url, name, size, self.main_widget)
        layout = self.main_widget.layout()
        if layout is not None:
            insert_pos = 1 if self.myspresso_header is not None else 0
            layout.insertWidget(insert_pos, banner)
```

- [ ] **Step 4: Add the startup timer at the end of `__init__`**

In `src/artisanlib/main.py`, find the last lines of `__init__` (around line 4433):

```python
        self.zoomInShortcut = QShortcut(QKeySequence.StandardKey.ZoomIn, self)
        self.zoomInShortcut.activated.connect(self.zoomIn)
        self.zoomOutShortcut = QShortcut(QKeySequence.StandardKey.ZoomOut, self)
        self.zoomOutShortcut.activated.connect(self.zoomOut)
```

Add this line immediately before `self.zoomInShortcut`:

```python
        QTimer.singleShot(5000, self._start_update_check)
```

So the end of `__init__` becomes:

```python
        QTimer.singleShot(5000, self._start_update_check)

        self.zoomInShortcut = QShortcut(QKeySequence.StandardKey.ZoomIn, self)
        self.zoomInShortcut.activated.connect(self.zoomIn)
        self.zoomOutShortcut = QShortcut(QKeySequence.StandardKey.ZoomOut, self)
        self.zoomOutShortcut.activated.connect(self.zoomOut)
```

- [ ] **Step 5: Run the full test suite to check nothing regressed**

```bash
cd /Users/lv/Documents/myspe-artisan/src
pytest test/unitary/ -v 2>&1 | tail -20
```

Expected: all tests PASS. If any test fails, investigate before committing.

- [ ] **Step 6: Commit**

```bash
cd /Users/lv/Documents/myspe-artisan
git add src/artisanlib/main.py
git commit -m "feat(updater): wire auto-update check into ApplicationWindow startup"
```

---

## Task 5: Manual verification

**No code changes — this is verification only.**

- [ ] **Step 1: Verify the banner appears (simulate a newer version)**

Temporarily edit `src/artisanlib/__init__.py`, change:
```python
__version__ = '4.0.3'
```
to:
```python
__version__ = '0.0.1'
```
This makes any published release appear "newer". Launch the app and wait 5 seconds.

Expected: a dark navy banner appears at the top of the window with text "Zabawa Roast X.Y.Z est disponible" and buttons "Mettre à jour" / "✕".

- [ ] **Step 2: Verify dismiss saves to QSettings**

Click ✕ on the banner. Relaunch the app (still with `__version__ = '0.0.1'`).

Expected: the banner does NOT reappear (the dismissed version is stored in QSettings `updater/skipped_version`).

- [ ] **Step 3: Verify download progress**

With banner visible, click "Mettre à jour". Watch the progress bar fill.

Expected: progress bar visible, label changes to "Téléchargement en cours...", then "Installation en cours, fermeture…", then app exits.

- [ ] **Step 4: Verify helper script was written**

After the app exits (before the helper script runs — you have ~2 seconds), check `/tmp/` for `zr_updater_<pid>.sh` (macOS) or `zr_updater_<pid>.bat` (Windows).

Expected: file exists with correct content (`hdiutil attach`, `rsync` on macOS; `/S` flag on Windows).

- [ ] **Step 5: Restore `__version__`**

```python
__version__ = '4.0.3'
```

- [ ] **Step 6: Verify the existing Help → Check for Updates still works**

Open Help menu → Check for Updates. Expected: dialog shows update status from `VeKTyS/myspe-artisan` (not `artisan-roaster-scope`).

- [ ] **Step 7: Final commit (if any cleanup needed)**

```bash
cd /Users/lv/Documents/myspe-artisan
git add -p  # review any leftover changes
git commit -m "fix(updater): post-verification cleanup"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
|---|---|
| Background check at startup (5s delay) | Task 4 Step 4 |
| Checks `VeKTyS/myspe-artisan` API | Task 2, Task 4 Step 2 |
| Emits only when version is newer | Task 2 (tests cover equal + older + newer) |
| "Ignore this version" via QSettings | Task 3 Step 3 (`_dismiss`), Task 2 test |
| Download with progress | Task 3 Step 3 (`_start_download`, `UpdateDownloader`) |
| macOS: DMG → hdiutil + rsync + relaunch | Task 3 Step 1 |
| Windows: NSIS `/S` + relaunch | Task 3 Step 1 |
| Fallback: open folder on failure | Task 3 Step 1 (`_open_folder_fallback`) |
| Network errors silently ignored | Task 2 (checker + downloader tests) |
| Banner inserted above main content | Task 4 Step 3 |
| Existing `checkUpdate()` URL fixed | Task 4 Step 2 |
