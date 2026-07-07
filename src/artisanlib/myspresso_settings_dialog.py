#
# myspresso_settings_dialog.py
#
# Standalone Qt dialog to edit the MySpresso cloud configuration
# (API URL, Web URL, auth toggle). Values are stored in QSettings
# under the 'cloud/' prefix and take effect after the application
# is restarted.

from typing import TYPE_CHECKING

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from artisanlib.dialogs import ArtisanDialog
from artisanlib.styles import current_semantic_tokens

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow


class MyspressoSettingsDialog(ArtisanDialog):
    """Edit MySpresso cloud configuration (URL endpoints, auth toggle)."""

    def __init__(self, parent: 'QWidget | None', aw: 'ApplicationWindow') -> None:
        super().__init__(parent, aw)
        self.setWindowTitle('MySpresso Cloud Settings')
        self.setModal(True)

        self._settings = QSettings()

        # Colour-bearing labels kept around so _apply_theme can restyle them
        # after a light/dark switch.
        self._section_headers: list[tuple[QLabel, str, str]] = []
        self._form_labels: list[QLabel] = []

        # ── Brand header: title + subtitle (matches Claude Design DialogShell)
        title = QLabel('Réglages MySpresso')
        title.setProperty('role', 'dialogTitle')
        subtitle = QLabel(
            'Endpoints du cloud, authentification, comportement de synchronisation.'
        )
        subtitle.setProperty('role', 'dialogSubtitle')

        self._api_edit = QLineEdit(
            self._settings.value('cloud/api_base_url', '', type=str)
        )
        self._api_edit.setPlaceholderText('')

        self._web_edit = QLineEdit(
            self._settings.value('cloud/web_base_url', '', type=str)
        )
        self._web_edit.setPlaceholderText('http://localhost:3000')

        self._auth_check = QCheckBox('Activer l\'authentification')
        self._auth_check.setChecked(
            bool(self._settings.value('cloud/auth_enabled', False, type=bool))
        )

        reset_btn = QPushButton('Réinitialiser')
        reset_btn.setProperty('role', 'secondary')
        reset_btn.clicked.connect(self._reset_defaults)

        # Theme preference: system | light | dark — applied LIVE on save.
        self._theme_combo = QComboBox()
        self._theme_combo.addItem('Système (suivre macOS / Windows)', 'system')
        self._theme_combo.addItem('Clair', 'light')
        self._theme_combo.addItem('Sombre', 'dark')
        _current_mode = str(self._settings.value('MySpressoTheme', 'system'))
        _idx = self._theme_combo.findData(_current_mode)
        self._theme_combo.setCurrentIndex(_idx if _idx >= 0 else 0)

        # Form rows — each with a small uppercase formLabel above the input.
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow(self._make_section_header('01', 'Apparence'))
        form.addRow(self._make_form_label('Thème'), self._theme_combo)
        form.addRow(self._make_section_header('02', 'Endpoint'))
        form.addRow(self._make_form_label('URL API'), self._api_edit)
        form.addRow(self._make_form_label('URL Web'), self._web_edit)
        form.addRow(self._make_section_header('03', 'Authentification'))
        form.addRow('', self._auth_check)
        form.addRow('', reset_btn)

        note = QLabel('Thème appliqué immédiatement · endpoints : redémarrage requis.')
        note.setProperty('role', 'muted')

        # Reuse the ArtisanDialog standard button box (roles/shortcuts wired
        # by the base class) — only the labels are localised here.
        ok_btn = self.dialogbuttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText('Appliquer')
        cancel_btn = self.dialogbuttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText('Annuler')
        self.dialogbuttons.accepted.connect(self._save_and_accept)
        self.dialogbuttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 18)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(self.dialogbuttons)

        self._apply_theme()

    # ── Theming ─────────────────────────────────────────────────────────────
    def _make_section_header(self, n: str, text: str) -> QLabel:
        """SectionHeader from Claude Design — accent mono number + uppercase
        title + thin bottom border. Rich text so the prefix keeps the accent
        colour while the rest of the line uses the primary foreground.
        Colours are applied by _apply_theme."""
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        self._section_headers.append((label, n, text))
        return label

    def _make_form_label(self, text: str) -> QLabel:
        """Small uppercase muted form label per Claude Design's Field.
        Colours are applied by _apply_theme."""
        label = QLabel(text.upper())
        self._form_labels.append(label)
        return label

    def _apply_theme(self) -> None:
        """(Re)apply all colour-bearing styles from the current theme tokens."""
        tok = current_semantic_tokens()
        for label, n, text in self._section_headers:
            label.setText(
                f'<span style="font-family:\'JetBrains Mono\',monospace;'
                f'font-size:11px;font-weight:600;color:{tok.accent};">{n}</span>'
                f'&nbsp;&nbsp;'
                f'<span style="font-size:12px;font-weight:700;'
                f'color:{tok.fg_primary};'
                f'letter-spacing:0.6px;">{text.upper()}</span>'
            )
            label.setStyleSheet(
                'QLabel { padding: 14px 0 8px 0;'
                f' border-bottom: 1px solid {tok.border}; }}'
            )
        form_label_style = (
            'QLabel { font-size: 10px; font-weight: 700;'
            f' color: {tok.fg_muted};'
            ' letter-spacing: 0.6px; padding: 0; background: transparent; }'
        )
        for label in self._form_labels:
            label.setStyleSheet(form_label_style)

    def restyle(self) -> None:
        """Public hook: re-resolve theme tokens after a light/dark switch."""
        self._apply_theme()

    def _save_and_accept(self) -> None:
        self._settings.setValue('cloud/api_base_url', self._api_edit.text().strip())
        self._settings.setValue('cloud/web_base_url', self._web_edit.text().strip())
        self._settings.setValue('cloud/auth_enabled', self._auth_check.isChecked())
        theme = str(self._theme_combo.currentData())
        theme_changed = theme != str(self._settings.value('MySpressoTheme', 'system'))
        self._settings.setValue('MySpressoTheme', theme)
        self._settings.sync()
        if theme_changed:
            # applied live — myspressoApplyTheme re-reads the persisted
            # preference and re-renders QSS, panels, chart and LCDs
            try:
                self.aw.myspressoApplyTheme()
            except Exception as e:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).exception(e)
        self.accept()

    def _reset_defaults(self) -> None:
        self._api_edit.clear()
        self._web_edit.clear()
        self._auth_check.setChecked(False)
