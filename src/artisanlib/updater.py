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
    update_available = pyqtSignal(str, str, str, int)
    # emits: (version, download_url, asset_name, asset_size)

    def run(self) -> None:
        from artisanlib import __version__

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
