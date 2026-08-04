#
# outbox_panel.py
#
# Interface de la file d'envoi : étiquette d'état du header, panneau détaillé,
# et boîte de choix de la société.
#
# Raison d'être : jusqu'ici, un échec d'envoi était TOTALEMENT silencieux. Le
# torréfacteur n'avait aucun moyen de savoir qu'une cuisson n'était pas remontée
# — il le découvrait en consultant le web des jours plus tard. L'état de la file
# doit donc être lisible d'un coup d'œil depuis le poste, sans ouvrir de menu.

import logging
import time
from typing import TYPE_CHECKING, Any, Final

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from plus.outbox import STATE_FAILED, STATE_PENDING, STATE_SENT, STATE_VERIFIED

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow

_log: Final[logging.Logger] = logging.getLogger(__name__)

_STATE_LABELS: Final[dict[str, str]] = {
    STATE_PENDING: 'en attente',
    STATE_SENT: 'envoyé, non confirmé',
    STATE_VERIFIED: 'confirmé',
    STATE_FAILED: 'échec',
}


def _format_roast_date(epoch: float | None) -> str:
    """Date et heure de la torréfaction, format court français."""
    if not epoch:
        return '—'
    try:
        return time.strftime('%d/%m/%Y %H:%M', time.localtime(epoch))
    except (ValueError, OSError, OverflowError):
        return '—'


def error_report(item: Any) -> str:
    """Rapport d'erreur copiable, destiné à être collé tel quel dans un message.

    On y met tout ce qu'il faut pour diagnostiquer sans accès au poste :
    identifiant, lot, grain, société, état, code HTTP et message complet.
    """
    lines = [
        f'Torréfaction : {item.batch_label or "—"} — {item.bean_label or "grain inconnu"}',
        f'Date : {_format_roast_date(item.roast_at)}',
        f'Société : {item.entity_slug or "—"}',
        f'Identifiant : {item.uuid}',
        f'État : {_STATE_LABELS.get(item.state, item.state)} '
        f'({item.attempts} tentative(s))',
    ]
    if item.last_http_status:
        lines.append(f'Code HTTP : {item.last_http_status}')
    lines.append(f'Erreur : {item.last_error or "aucune"}')
    return '\n'.join(lines)


def badge_text(counts: dict[str, int], to_review: int) -> str:
    """Étiquette compacte de l'état de la file.

    Les échecs passent en premier : c'est ce qui demande une action. « à
    vérifier » compte les torréfactions livrées dont le grain a été créé
    automatiquement côté serveur.
    """
    parts: list[str] = []
    failed = counts.get(STATE_FAILED, 0)
    waiting = counts.get(STATE_PENDING, 0) + counts.get(STATE_SENT, 0)
    if failed:
        parts.append(f'{failed} échec' + ('s' if failed > 1 else ''))
    if waiting:
        parts.append(f'{waiting} en attente')
    if to_review:
        parts.append(f'{to_review} à vérifier')
    return ', '.join(parts) if parts else '✓ à jour'


def ask_entity_dialog(aw: 'ApplicationWindow') -> tuple[str, str] | None:
    """Demande la société de rattachement. Renvoie (slug, libellé) ou None.

    N'apparaît que si ni le magasin ni les Propriétés ne donnent la société :
    mieux vaut une question que laisser le serveur deviner (il attribue alors la
    torréfaction au magasin fourre-tout, sans décrément de stock).
    """
    try:
        import plus.stock
        stores = plus.stock.getStores()
        entities = plus.stock.getEntities(stores)
    except Exception as e:  # pylint: disable=broad-except
        _log.exception(e)
        entities = []

    if not entities:
        QMessageBox.warning(
            aw, 'ZABAWA.plus',
            "Aucune société connue : ouvrez Propriétés de torréfaction pour "
            "choisir un magasin, puis relancez l'envoi.")
        return None

    dlg = QDialog(aw)
    dlg.setWindowTitle('Société de la torréfaction')
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel('À quelle société rattacher cette torréfaction ?'))

    chosen: dict[str, tuple[str, str]] = {}

    def _pick(slug: str, label: str) -> None:
        chosen['value'] = (slug, label)
        dlg.accept()

    import plus.stock as _stock
    for entity in entities:
        label = _stock.getEntityLabel(entity)
        slug = _stock.getEntityId(entity)
        btn = QPushButton(label)
        btn.setMinimumHeight(34)
        btn.clicked.connect(lambda _checked=False, s=slug, l=label: _pick(s, l))
        layout.addWidget(btn)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    dlg.exec()
    return chosen.get('value')


class OutboxDialog(QDialog):
    """Détail de la file : une ligne par torréfaction, avec relance manuelle."""

    COLUMNS: Final[tuple[str, ...]] = (
        'Lot', 'Torréfaction', 'Grain', 'Société', 'État', 'Tentatives', 'Dernière erreur')

    def __init__(self, aw: 'ApplicationWindow', worker: Any) -> None:
        super().__init__(aw)
        self._aw = aw
        self._worker = worker
        self.setWindowTitle("File d'envoi ZABAWA.plus")
        self.resize(820, 380)

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(self.COLUMNS), self)
        self._table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self._table.horizontalHeader()
        if header is not None:
            # La colonne d'erreur prend la place restante : c'est elle qu'on
            # vient lire quand quelque chose bloque.
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        retry_btn = QPushButton('Réessayer la sélection')
        retry_btn.clicked.connect(self._retry_selected)
        retry_all_btn = QPushButton('Tout réessayer')
        retry_all_btn.clicked.connect(self._retry_all)
        copy_btn = QPushButton("Copier l'erreur")
        copy_btn.setToolTip('Copie le détail complet de la ligne sélectionnée '
                            '(lot, grain, société, code HTTP, message).')
        copy_btn.clicked.connect(self._copy_error)
        ack_btn = QPushButton('Marquer comme vérifié')
        ack_btn.setToolTip('Retire le rappel « grain créé automatiquement » '
                           'une fois la fiche complétée côté web.')
        ack_btn.clicked.connect(self._acknowledge_selected)
        actions.addWidget(retry_btn)
        actions.addWidget(retry_all_btn)
        actions.addWidget(copy_btn)
        actions.addWidget(ack_btn)
        actions.addStretch()
        close_btn = QPushButton('Fermer')
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        self.refresh()
        try:
            worker.changed.connect(self.refresh)
        except Exception:  # pylint: disable=broad-except
            pass

    def refresh(self) -> None:
        items = self._worker.store.all_items()
        self._table.setRowCount(len(items))
        for row, item in enumerate(items):
            state = _STATE_LABELS.get(item.state, item.state)
            if item.state == STATE_VERIFIED and item.bean_created and not item.review_ack:
                state += ' — grain créé, à vérifier'
            values = (item.batch_label or '—', _format_roast_date(item.roast_at),
                      item.bean_label or '—', item.entity_slug or '—', state,
                      str(item.attempts), item.last_error or '')
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.uuid)
                # Message d'erreur complet en infobulle : la colonne le tronque
                # visuellement, or c'est souvent la fin qui porte la cause.
                if col == 6 and value:
                    cell.setToolTip(value)
                self._table.setItem(row, col, cell)

    def _selected_uuids(self) -> list[str]:
        uuids: list[str] = []
        for index in self._table.selectionModel().selectedRows() if self._table.selectionModel() else []:
            cell = self._table.item(index.row(), 0)
            if cell is not None:
                uuid = cell.data(Qt.ItemDataRole.UserRole)
                if uuid:
                    uuids.append(str(uuid))
        return uuids

    def _retry_selected(self) -> None:
        store = self._worker.store
        for uuid in self._selected_uuids():
            store.retry(uuid, now=time.time())
        self._worker.wake()
        self.refresh()

    def _retry_all(self) -> None:
        store = self._worker.store
        for item in store.all_items():
            if item.state != STATE_VERIFIED:
                store.retry(item.uuid, now=time.time())
        self._worker.wake()
        self.refresh()

    def _copy_error(self) -> None:
        """Copie le rapport des lignes sélectionnées dans le presse-papier.

        Sans sélection, on prend toutes les lignes en erreur : c'est le geste
        attendu quand on veut simplement transmettre « ce qui ne passe pas ».
        """
        store = self._worker.store
        uuids = self._selected_uuids()
        items = [i for i in store.all_items() if i.uuid in uuids] if uuids else [
            i for i in store.all_items() if i.last_error]
        if not items:
            QMessageBox.information(self, 'ZABAWA.plus', 'Aucune erreur à copier.')
            return
        text = '\n\n'.join(error_report(i) for i in items)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        QMessageBox.information(
            self, 'ZABAWA.plus',
            f'{len(items)} erreur(s) copiée(s) — collez-les où vous voulez.')

    def _acknowledge_selected(self) -> None:
        store = self._worker.store
        for uuid in self._selected_uuids():
            store.acknowledge_review(uuid)
        self.refresh()
        try:
            self._aw._refresh_outbox_badge()  # pylint: disable=protected-access
        except Exception:  # pylint: disable=broad-except
            pass


def open_outbox_dialog(aw: 'ApplicationWindow') -> None:
    worker = getattr(aw, 'outbox_worker', None)
    if worker is None:
        QMessageBox.information(aw, 'ZABAWA.plus', "La file d'envoi n'est pas démarrée.")
        return
    OutboxDialog(aw, worker).exec()
