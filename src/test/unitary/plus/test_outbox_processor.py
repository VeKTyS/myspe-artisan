"""Tests de plus.outbox_worker — un tour de traitement de la file.

process_once() est volontairement séparée du QThread : c'est la logique
d'acquittement, celle qui décide si une torréfaction est considérée comme
arrivée. Elle doit être testable sans Qt, sans réseau et sans horloge.
"""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from plus.outbox import STATE_FAILED, STATE_PENDING, STATE_VERIFIED, OutboxStore
from plus.outbox_client import ReceiptResult, UploadResult
from plus.outbox_processor import process_once

UUID_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

OK_UPLOAD = UploadResult(ok=True, http_status=201, permanent=False, error=None,
                         server_roast_id='r1', bean_created=False, store_resolved=True)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[OutboxStore]:
    s = OutboxStore(str(tmp_path))
    s.enqueue(UUID_A, 'contenu', sync_record={'roast_id': UUID_A}, entity_slug='esperanza',
              batch_label='#42', now=0.0)
    yield s
    s.close()


def _receipt(store: OutboxStore, **over: object) -> ReceiptResult:
    item = store.get(UUID_A)
    assert item is not None
    base = {'present': True, 'content_hash': item.content_sha256, 'http_status': 200,
            'error': None, 'roast_id': 'r1', 'bean_created': False, 'store_resolved': True}
    base.update(over)
    return ReceiptResult(**base)  # type: ignore[arg-type]


def test_envoi_puis_recu_conforme_acquitte(store: OutboxStore) -> None:
    receipter = MagicMock(return_value=_receipt(store))
    assert process_once(store, uploader=MagicMock(return_value=OK_UPLOAD),
                        receipter=receipter, now=10.0) == 1
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_VERIFIED


def test_luploader_recoit_le_contenu_et_la_societe(store: OutboxStore) -> None:
    uploader = MagicMock(return_value=OK_UPLOAD)
    process_once(store, uploader=uploader, receipter=MagicMock(return_value=_receipt(store)),
                 now=10.0)
    args = uploader.call_args.args
    assert args[0] == UUID_A
    assert args[1] == 'contenu'
    assert args[3] == {'roast_id': UUID_A}
    assert args[4] == 'esperanza'


def test_recu_absent_renvoie_en_pending(store: OutboxStore) -> None:
    receipter = MagicMock(return_value=ReceiptResult(
        present=False, content_hash=None, http_status=404, error=None))
    process_once(store, uploader=MagicMock(return_value=OK_UPLOAD), receipter=receipter, now=10.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_PENDING
    assert item.attempts == 1
    assert 'reçu' in (item.last_error or '').lower()


def test_hash_divergent_renvoie_en_pending(store: OutboxStore) -> None:
    # une version antérieure est en base : il faut réenvoyer, pas acquitter
    receipter = MagicMock(return_value=_receipt(store, content_hash='0' * 64))
    process_once(store, uploader=MagicMock(return_value=OK_UPLOAD), receipter=receipter, now=10.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_PENDING


def test_serveur_sans_hash_accepte_le_recu(store: OutboxStore) -> None:
    # tolérance de transition : un roast ingéré avant la migration n'a pas de
    # hash en base, son absence ne doit pas bloquer la file indéfiniment
    receipter = MagicMock(return_value=_receipt(store, content_hash=None))
    process_once(store, uploader=MagicMock(return_value=OK_UPLOAD), receipter=receipter, now=10.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_VERIFIED


def test_panne_du_recu_nest_pas_une_absence(store: OutboxStore) -> None:
    receipter = MagicMock(return_value=ReceiptResult(
        present=False, content_hash=None, http_status=500, error='boom'))
    process_once(store, uploader=MagicMock(return_value=OK_UPLOAD), receipter=receipter, now=10.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_PENDING
    assert 'boom' in (item.last_error or '')


def test_echec_permanent_a_lupload(store: OutboxStore) -> None:
    uploader = MagicMock(return_value=UploadResult(
        ok=False, http_status=400, permanent=True, error='corps invalide'))
    receipter = MagicMock()
    process_once(store, uploader=uploader, receipter=receipter, now=10.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_FAILED
    receipter.assert_not_called()


def test_item_non_echu_est_ignore(store: OutboxStore) -> None:
    store.mark_error(UUID_A, http_status=500, error='boom', permanent=False, now=100.0)
    uploader = MagicMock()
    assert process_once(store, uploader=uploader, receipter=MagicMock(), now=101.0) == 0
    uploader.assert_not_called()


def test_item_sent_est_reverifie_sans_reenvoi(store: OutboxStore) -> None:
    receipt = _receipt(store)
    store.mark_sent(UUID_A, http_status=201, server_roast_id='r1', bean_created=False,
                    store_resolved=True, now=1.0)
    uploader = MagicMock()
    process_once(store, uploader=uploader, receipter=MagicMock(return_value=receipt), now=10.0)
    uploader.assert_not_called()
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_VERIFIED


def test_acquittement_alimente_le_cache_de_sync(store: OutboxStore) -> None:
    # le cache de sync était alimenté par plus/queue.py ; les torréfactions
    # n'empruntant plus cette route, c'est l'acquittement qui s'en charge
    seen: list[tuple[str, object]] = []
    process_once(store, uploader=MagicMock(return_value=OK_UPLOAD),
                 receipter=MagicMock(return_value=_receipt(store)), now=10.0,
                 on_verified=lambda uuid, rec: seen.append((uuid, rec)))
    assert seen == [(UUID_A, {'roast_id': UUID_A})]


def test_le_rappel_qui_echoue_ne_defait_pas_lacquittement(store: OutboxStore) -> None:
    def _boom(uuid: str, rec: object) -> None:
        raise RuntimeError('cache indisponible')

    process_once(store, uploader=MagicMock(return_value=OK_UPLOAD),
                 receipter=MagicMock(return_value=_receipt(store)), now=10.0,
                 on_verified=_boom)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_VERIFIED
