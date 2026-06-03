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
        pass  # TODO


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
