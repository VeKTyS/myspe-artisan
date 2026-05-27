"""
Stylesheet loader for the MySpresso Artisan fork.

Reads `myspresso.qss` from this package directory and applies it to a
QApplication. Toggles light/dark via the `theme` dynamic property —
the QSS uses `[theme="dark"]` attribute selectors to override colours.

Usage (at app startup, AFTER QApplication is constructed):

    from artisanlib.styles import apply_myspresso_stylesheet
    apply_myspresso_stylesheet(app)

Re-call to refresh when the system colour scheme changes.

To disable the MySpresso stylesheet (e.g., to fall back to upstream
look during debugging), set the environment variable
MYSPRESSO_STYLE_DISABLED=true before launching.
"""

from __future__ import annotations

import logging
import os
import pathlib

from PyQt6.QtWidgets import QApplication

_log = logging.getLogger(__name__)

_QSS_PATH = pathlib.Path(__file__).parent / 'myspresso.qss'
_FONTS_DIR = pathlib.Path(__file__).parent.parent.parent / 'fonts'

_FONT_FILES = (
    # Montserrat — variable-weight TTF is preferred; static weights also
    # accepted for installs that don't have the variable file.
    'Montserrat-Variable.ttf',
    'Montserrat-Regular.ttf',
    'Montserrat-Medium.ttf',
    'Montserrat-SemiBold.ttf',
    'Montserrat-Bold.ttf',
    # JetBrains Mono — used for tabular numerals (timer / temps / values).
    'JetBrainsMono-Regular.ttf',
    'JetBrainsMono-Medium.ttf',
    'JetBrainsMono-Bold.ttf',
)


def load_bundled_fonts() -> None:
    """Register the bundled Montserrat + JetBrains Mono TTFs with Qt.

    The QSS references "Montserrat" and "JetBrains Mono" by family name;
    `QFontDatabase.addApplicationFont()` makes them available globally
    so QSS / setFont() can resolve them without OS-wide installation.

    Safe to call multiple times — Qt deduplicates registrations.
    Silently no-ops if the fonts directory or any file is missing.
    """
    try:
        from PyQt6.QtGui import QFontDatabase
    except ImportError:
        return
    if not _FONTS_DIR.is_dir():
        _log.debug('fonts dir not found: %s', _FONTS_DIR)
        return
    for name in _FONT_FILES:
        path = _FONTS_DIR / name
        if not path.is_file():
            # Demoted to debug — most builds will only ship a subset of these
            # variants (e.g. only the variable font) and the missing-file
            # noise drowned out real warnings.
            _log.debug('font not bundled (skipping): %s', path.name)
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            _log.warning('failed to register font: %s', path)


def is_style_disabled() -> bool:
    """True when MYSPRESSO_STYLE_DISABLED=true is set (escape hatch)."""
    return os.environ.get('MYSPRESSO_STYLE_DISABLED', '').strip().lower() == 'true'


_ICONS_DIR = pathlib.Path(__file__).parent.parent.parent / 'icons' / 'myspresso'


def load_qss() -> str:
    """Return the QSS string. Empty string if the file cannot be read.

    Substitutes the relative ``"../icons/myspresso/X"`` references with the
    absolute paths so Qt's ``url()`` resolver works regardless of the app's
    current working directory.
    """
    try:
        qss = _QSS_PATH.read_text(encoding='utf-8')
    except OSError as exc:
        _log.warning('failed to load %s: %s', _QSS_PATH, exc)
        return ''
    # Rewrite "../icons/myspresso/X" → absolute path so url() resolves.
    if _ICONS_DIR.is_dir():
        qss = qss.replace('"../icons/myspresso/', f'"{_ICONS_DIR.as_posix()}/')
    return qss


def is_dark_mode(app: QApplication) -> bool:
    """Detect whether the system colour scheme is dark.

    Falls back to False if the running Qt version doesn't expose
    `styleHints().colorScheme()` (pre-6.5).
    """
    try:
        from PyQt6.QtCore import Qt
        scheme = app.styleHints().colorScheme()
        return bool(scheme == Qt.ColorScheme.Dark)
    except (AttributeError, ImportError):
        return False


def apply_myspresso_stylesheet(app: QApplication) -> None:
    """Load the MySpresso QSS and apply it to `app`.

    Sets `theme` to `"dark"` or `"light"` on the application so the QSS
    dark-mode rules engage automatically. Safe to call multiple times
    (re-polishes any widgets already constructed).

    No-op when MYSPRESSO_STYLE_DISABLED=true.
    """
    if is_style_disabled():
        _log.info('MYSPRESSO_STYLE_DISABLED=true — skipping stylesheet')
        return
    load_bundled_fonts()
    qss = load_qss()
    if not qss:
        return
    theme = 'dark' if is_dark_mode(app) else 'light'
    app.setProperty('theme', theme)
    app.setStyleSheet(qss)
    style = app.style()
    if style is not None:
        for w in app.allWidgets():
            style.unpolish(w)
            style.polish(w)
    _log.info('applied MySpresso stylesheet (theme=%s, size=%d)', theme, len(qss))
