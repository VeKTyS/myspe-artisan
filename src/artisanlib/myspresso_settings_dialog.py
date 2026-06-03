#
# myspresso_settings_dialog.py
#
# Standalone Qt dialog to edit the MySpresso cloud configuration
# (API URL, Web URL, auth toggle). Values are stored in QSettings
# under the 'cloud/' prefix and take effect after the application
# is restarted.

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _make_section_header(n: str, text: str) -> QLabel:
    """SectionHeader from Claude Design — red mono number + uppercase title
    + thin warm bottom border. Uses rich text so the prefix can stay red
    while the rest of the line is navy."""
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setText(
        f'<span style="font-family:\'JetBrains Mono\',monospace;'
        f'font-size:11px;font-weight:600;color:#A8392E;">{n}</span>'
        f'&nbsp;&nbsp;'
        f'<span style="font-size:12px;font-weight:700;color:#070D1F;'
        f'letter-spacing:0.6px;">{text.upper()}</span>'
    )
    label.setStyleSheet(
        'QLabel { padding: 14px 0 8px 0;'
        ' border-bottom: 1px solid #E8E3D6; }'
    )
    return label


def _make_form_label(text: str) -> QLabel:
    """Small uppercase warm-gray form label per Claude Design's Field."""
    label = QLabel(text.upper())
    label.setStyleSheet(
        'QLabel { font-size: 10px; font-weight: 700; color: #7A736A;'
        ' letter-spacing: 0.6px; padding: 0; background: transparent; }'
    )
    return label


class MyspressoSettingsDialog(QDialog):
    """Edit MySpresso cloud configuration (URL endpoints, auth toggle)."""

    def __init__(self, parent: 'QWidget | None' = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('MySpresso Cloud Settings')
        self.setModal(True)

        self._settings = QSettings()

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

        # Form rows — each with a small uppercase formLabel above the input.
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow(_make_section_header('01', 'Endpoint'))
        form.addRow(_make_form_label('URL API'), self._api_edit)
        form.addRow(_make_form_label('URL Web'), self._web_edit)
        form.addRow(_make_section_header('02', 'Authentification'))
        form.addRow('', self._auth_check)
        form.addRow('', reset_btn)

        note = QLabel('Redémarrage requis après modification.')
        note.setProperty('role', 'muted')

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        # Tag the OK button as primary so it picks up the navy primary style.
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setProperty('role', 'primary')
            ok_btn.setText('Appliquer')
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setProperty('role', 'secondary')
            cancel_btn.setText('Annuler')
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 18)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
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
