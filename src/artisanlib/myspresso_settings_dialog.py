#
# myspresso_settings_dialog.py
#
# Standalone Qt dialog to edit the MySpresso cloud configuration
# (API URL, Web URL, auth toggle). Values are stored in QSettings
# under the 'cloud/' prefix and take effect after the application
# is restarted.

from PyQt6.QtCore import QSettings
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
        self._api_edit.setPlaceholderText(
            'https://eedquprtdxpfbtkppqio.supabase.co/functions/v1/artisan-api'
        )

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
