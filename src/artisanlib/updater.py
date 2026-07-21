from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, cast

# Windows-specific constants
if sys.platform == 'win32':
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
else:
    DETACHED_PROCESS = 0
    CREATE_NEW_PROCESS_GROUP = 0

import requests
from PyQt6.QtCore import QSettings, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QProgressBar, QPushButton,
)

from artisanlib.styles import current_semantic_tokens

GITHUB_API_URL = 'https://api.github.com/repos/VeKTyS/myspe-artisan/releases/latest'


def _version_tuple(v: str) -> tuple[int, ...]:
    """Parse a dotted version into an int tuple for numeric comparison.

    String comparison is wrong past a two-digit component ('4.10' < '4.9'
    lexicographically), which would silently stop offering updates from 4.10 on
    and even offer downgrades. Non-numeric parts degrade to 0.
    """
    parts: list[int] = []
    for p in v.split('.'):
        m = re.match(r'\d+', p)
        parts.append(int(m.group(0)) if m else 0)
    return tuple(parts)


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str, str, int)
    # emits: (version, download_url, asset_name, asset_size)
    no_update = pyqtSignal()        # already on the latest (or a dismissed one)
    check_failed = pyqtSignal(str)  # network / parsing / no-asset failure

    def __init__(self, respect_skipped: bool = True) -> None:
        super().__init__()
        # The automatic startup check honours a version the user dismissed; a
        # manual 'Check for Updates' passes False so it always re-offers it.
        self._respect_skipped = respect_skipped

    def run(self) -> None:
        from artisanlib import __version__

        settings = QSettings()
        skipped: str = settings.value('updater/skipped_version', '', type=str)

        try:
            r = requests.get(GITHUB_API_URL, timeout=(2, 4))
            if r.status_code != 200:
                self.check_failed.emit(f'HTTP {r.status_code}')
                return
            data = r.json()
        except Exception as e:  # noqa: BLE001
            self.check_failed.emit(str(e))
            return

        tag_name: str = data.get('tag_name', '')
        match = re.search(r'[\d.]+', tag_name)
        if not match:
            self.check_failed.emit('no version tag in the latest release')
            return
        latest: str = match.group(0)

        if _version_tuple(latest) <= _version_tuple(__version__):
            self.no_update.emit()
            return
        if self._respect_skipped and latest == skipped:
            self.no_update.emit()
            return

        platform_key = 'artisan-mac' if sys.platform == 'darwin' else 'zabawa-roast-win'
        for asset in data.get('assets', []):
            name: str = asset.get('name', '')
            if platform_key in name:
                url: str = asset['browser_download_url']
                size: int = asset.get('size', 0)
                self.update_available.emit(latest, url, name, size)
                return
        # A newer release exists but ships no installer for this platform.
        self.check_failed.emit('no installer for this platform in the latest release')


class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, dest_dir: str, expected_size: int = 0) -> None:
        super().__init__()
        self._url = url
        self._dest_dir = dest_dir
        self._expected_size = expected_size

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


class UpdateBanner(QFrame):
    def __init__(self, version: str, asset_url: str, asset_name: str,
                 asset_size: int = 0, parent=None, aw=None) -> None:
        super().__init__(parent)
        self._version = version
        self._asset_url = asset_url
        self._asset_name = asset_name
        self._asset_size = asset_size
        self._downloader: UpdateDownloader | None = None
        # ApplicationWindow, used to check whether a roast is being recorded so
        # the app is never quit for the update mid-roast (would lose the roast).
        self._aw = aw
        self._pending_install_path: str | None = None

        self.setFixedHeight(44)
        self.setObjectName('UpdateBanner')
        # All child selectors here so they override the global QWidget/QFrame rules
        tok = current_semantic_tokens()
        self.setStyleSheet(
            'QFrame#UpdateBanner {'
            '  background: #0F1932;'
            f'  border-bottom: 1px solid {tok.accent};'
            '}'
            'QFrame#UpdateBanner QLabel {'
            '  color: #F5F1E8;'
            '  background: transparent;'
            '  font-family: Montserrat, sans-serif;'
            '  font-size: 12px;'
            '}'
            'QFrame#UpdateBanner QPushButton#updateBtn {'
            f'  background: {tok.accent}; color: {tok.fg_on_brand}; border: none;'
            '  border-radius: 4px; padding: 0 12px;'
            '  font-family: Montserrat, sans-serif; font-size: 11px; font-weight: 600;'
            '}'
            'QFrame#UpdateBanner QPushButton#updateBtn:hover { background: #C44236; }'
            'QFrame#UpdateBanner QPushButton#dismissBtn {'
            '  color: #7A8499; background: transparent; border: none; font-size: 13px;'
            '}'
            'QFrame#UpdateBanner QPushButton#dismissBtn:hover { color: #F5F1E8; }'
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(12)

        self._label = QLabel(f'Zabawa Roast {version} est disponible')

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(160)
        self._progress.setFixedHeight(16)
        self._progress.hide()

        self._update_btn = QPushButton('Mettre à jour')
        self._update_btn.setObjectName('updateBtn')
        self._update_btn.setFixedHeight(28)
        self._update_btn.clicked.connect(self._start_download)

        self._dismiss_btn = QPushButton('✕')
        self._dismiss_btn.setObjectName('dismissBtn')
        self._dismiss_btn.setFixedSize(24, 24)
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

    def _roast_active(self) -> bool:
        """True while Artisan is sampling or recording a roast.

        Installing quits the app, so it must never happen mid-roast. flagstart
        is an active recording (the roast that would be lost); flagon is live
        sampling (machine connected) — both block the install.
        """
        qmc = getattr(self._aw, 'qmc', None)
        if qmc is None:
            return False
        return bool(getattr(qmc, 'flagstart', False) or getattr(qmc, 'flagon', False))

    def _on_download_finished(self, path: str) -> None:
        self._pending_install_path = path
        self._maybe_install_or_wait()

    def _maybe_install_or_wait(self) -> None:
        """Install now if idle, otherwise poll until the roast finishes.

        The download is already done; we only defer the quit. This makes the
        update install automatically the moment the roaster is idle instead of
        interrupting a roast in progress.
        """
        if self._pending_install_path is None:
            return
        if self._roast_active():
            self._label.setText('Mise à jour prête — installation après la torréfaction')
            self._progress.hide()
            QTimer.singleShot(3000, self._maybe_install_or_wait)
            return
        self._label.setText('Installation en cours, fermeture…')
        self._progress.hide()
        path = self._pending_install_path
        QTimer.singleShot(800, lambda: run_updater_and_quit(path))

    def _on_download_error(self, msg: str) -> None:
        self._label.setText('Échec du téléchargement.')
        self._progress.hide()
        open_btn = QPushButton('Ouvrir le dossier')
        open_btn.setObjectName('updateBtn')
        open_btn.setFixedHeight(28)
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
            f'open "{app_dir}/"*.app\n'
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
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        except OSError:
            _open_folder_fallback(asset_path)
            return

    app = QApplication.instance()
    if app is not None:
        app.quit()


def _open_folder_fallback(path: str) -> None:
    folder = os.path.dirname(path)
    if sys.platform == 'darwin':
        subprocess.Popen(['open', folder])
    elif sys.platform == 'win32':
        subprocess.Popen(['explorer', folder])
