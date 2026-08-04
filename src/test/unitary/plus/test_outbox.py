"""Tests de plus.outbox — persistance et machine à états de la file d'envoi.

Invariant central : AUCUN état ne supprime un item non livré. C'est la
correction directe du défaut de plus/queue.py, où task_done() était appelé
inconditionnellement après épuisement des tentatives — une torréfaction envoyée
pendant une coupure réseau disparaissait sans message.
"""

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from plus.outbox import (
    MAX_ATTEMPTS,
    STATE_FAILED,
    STATE_PENDING,
    STATE_SENT,
    STATE_VERIFIED,
    OutboxStore,
)

UUID_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
UUID_B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'


@pytest.fixture
def store(tmp_path: Path) -> Iterator[OutboxStore]:
    s = OutboxStore(str(tmp_path))
    yield s
    s.close()


def test_enqueue_persiste_contenu_et_hash(store: OutboxStore) -> None:
    item = store.enqueue(UUID_A, "{'title': 'essai'}", sync_record={'roast_id': UUID_A},
                         entity_slug='esperanza', batch_label='#42', now=1000.0)
    assert item.state == STATE_PENDING
    assert item.content_sha256 == hashlib.sha256("{'title': 'essai'}".encode('utf-8')).hexdigest()
    assert Path(item.alog_path).read_text(encoding='utf-8') == "{'title': 'essai'}"
    assert store.content(UUID_A) == "{'title': 'essai'}"
    assert item.entity_slug == 'esperanza'
    assert item.batch_label == '#42'
    assert item.sync_record == {'roast_id': UUID_A}


def test_reenfilement_remplace_le_contenu_et_repasse_en_pending(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=1000.0)
    store.mark_sent(UUID_A, http_status=200, server_roast_id='r1', bean_created=False,
                    store_resolved=True, now=1001.0)
    item = store.enqueue(UUID_A, 'v2', sync_record=None, entity_slug='myspresso',
                         batch_label='#43', now=1002.0)
    assert item.state == STATE_PENDING
    assert item.attempts == 0
    assert store.content(UUID_A) == 'v2'
    # une seule ligne par torréfaction : c'est la dernière version qui compte
    assert len(store.all_items()) == 1


def test_due_items_respecte_le_backoff(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=1000.0)
    store.mark_error(UUID_A, http_status=500, error='boom', permanent=False, now=1000.0)
    assert store.due_items(now=1010.0) == []
    assert [i.uuid for i in store.due_items(now=1031.0)] == [UUID_A]


def test_backoff_croissant_et_plafonne(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    delays = []
    for _ in range(8):
        before = store.get(UUID_A)
        assert before is not None
        store.mark_error(UUID_A, http_status=500, error='boom', permanent=False, now=0.0)
        after = store.get(UUID_A)
        assert after is not None
        delays.append(after.next_attempt_at)
        assert after.attempts == before.attempts + 1
    assert delays[0] == 30
    assert delays == sorted(delays)
    assert delays[-1] == 3600


def test_failed_apres_max_attempts_mais_jamais_supprime(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    for _ in range(MAX_ATTEMPTS):
        store.mark_error(UUID_A, http_status=500, error='boom', permanent=False, now=0.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_FAILED
    assert item.last_error == 'boom'
    # le contenu reste récupérable : un échec n'est pas une perte
    assert store.content(UUID_A) == 'v1'


def test_erreur_permanente_echoue_immediatement(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.mark_error(UUID_A, http_status=400, error='corps invalide', permanent=True, now=0.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_FAILED
    assert item.attempts == 1


def test_retry_manuel_relance_un_item_en_echec(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.mark_error(UUID_A, http_status=400, error='x', permanent=True, now=0.0)
    store.retry(UUID_A, now=50.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_PENDING
    assert item.attempts == 0
    assert [i.uuid for i in store.due_items(now=50.0)] == [UUID_A]


def test_cycle_nominal_jusqua_verified(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.mark_sent(UUID_A, http_status=201, server_roast_id='r1', bean_created=True,
                    store_resolved=True, now=1.0)
    sent = store.get(UUID_A)
    assert sent is not None
    assert sent.state == STATE_SENT
    store.mark_verified(UUID_A, now=2.0)
    item = store.get(UUID_A)
    assert item is not None
    assert item.state == STATE_VERIFIED
    assert item.bean_created is True
    assert item.verified_at == 2.0
    assert item.server_roast_id == 'r1'


def test_counts_par_etat(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.enqueue(UUID_B, 'v2', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.mark_error(UUID_B, http_status=400, error='x', permanent=True, now=0.0)
    assert store.counts() == {STATE_PENDING: 1, STATE_FAILED: 1}


def test_to_review_compte_les_grains_crees(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.mark_sent(UUID_A, http_status=201, server_roast_id='r1', bean_created=True,
                    store_resolved=True, now=1.0)
    store.mark_verified(UUID_A, now=1.0)
    assert store.to_review_count() == 1
    store.acknowledge_review(UUID_A)
    assert store.to_review_count() == 0


def test_reouverture_conserve_les_items(tmp_path: Path) -> None:
    s1 = OutboxStore(str(tmp_path))
    s1.enqueue(UUID_A, 'v1', sync_record={'roast_id': UUID_A}, entity_slug='esperanza',
               batch_label='#42', now=0.0)
    s1.close()
    s2 = OutboxStore(str(tmp_path))
    items = s2.all_items()
    assert [i.uuid for i in items] == [UUID_A]
    assert items[0].sync_record == {'roast_id': UUID_A}
    assert s2.content(UUID_A) == 'v1'
    s2.close()


def test_purge_ne_touche_que_les_verified_anciens(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.mark_sent(UUID_A, http_status=201, server_roast_id=None, bean_created=False,
                    store_resolved=True, now=1.0)
    store.mark_verified(UUID_A, now=1.0)
    assert store.purge_verified(before=0.5) == 0
    assert store.purge_verified(before=2.0) == 1
    assert store.all_items() == []


def test_purge_epargne_les_items_non_livres(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.mark_error(UUID_A, http_status=400, error='x', permanent=True, now=0.0)
    assert store.purge_verified(before=1e12) == 0
    assert len(store.all_items()) == 1


def test_cleanup_orphans_supprime_les_fichiers_sans_ligne(store: OutboxStore, tmp_path: Path) -> None:
    orphan = tmp_path / 'cccccccc-cccc-4ccc-8ccc-cccccccccccc.alog'
    orphan.write_text('perdu', encoding='utf-8')
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    assert store.cleanup_orphans() == 1
    assert not orphan.exists()
    assert store.content(UUID_A) == 'v1'


def test_stale_items_signale_les_envois_qui_trainent(store: OutboxStore) -> None:
    store.enqueue(UUID_A, 'v1', sync_record=None, entity_slug=None, batch_label=None, now=0.0)
    store.enqueue(UUID_B, 'v2', sync_record=None, entity_slug=None, batch_label=None, now=100000.0)
    stale = store.stale_items(older_than=86400.0, now=100000.0)
    assert [i.uuid for i in stale] == [UUID_A]
