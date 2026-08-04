"""Tests de plus.outbox_client — contrat HTTP avec upload-roast et le reçu.

Trois points sont vérifiés ici parce qu'ils décident du rattachement côté
serveur : le slug de société part bien en query param, createMissingBean est
bien demandé, et le hash de contenu accompagne l'envoi (sans lui, aucun
acquittement n'est possible).
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from plus import outbox_client

UUID_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'


def _response(status: int, payload: Any = None, text: str = '') -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = text or (json.dumps(payload) if payload is not None else '')
    r.json.return_value = payload if payload is not None else {}
    return r


def test_upload_envoie_slug_hash_et_create_missing_bean() -> None:
    poster = MagicMock(return_value=_response(201, {'status': 'created', 'roastId': 'r1',
                                                    'beanCreated': True, 'storeResolved': True}))
    res = outbox_client.upload(UUID_A, "{'a': 1}", 'abc123', {'roast_id': UUID_A},
                               'esperanza', poster=poster)
    url = poster.call_args.args[0]
    body = json.loads(poster.call_args.kwargs['data'].decode('utf-8'))
    assert 'entrepriseSlug=esperanza' in url
    assert 'createMissingBean=true' in url
    assert 'strategy=overwrite' in url
    assert body['id'] == UUID_A
    assert body['alogContent'] == "{'a': 1}"
    assert body['contentSha256'] == 'abc123'
    assert body['syncRecord'] == {'roast_id': UUID_A}
    assert body['source'] == 'desktop-outbox'
    assert res.ok is True
    assert res.bean_created is True
    assert res.store_resolved is True
    assert res.server_roast_id == 'r1'


def test_upload_sans_societe_nenvoie_pas_le_param() -> None:
    poster = MagicMock(return_value=_response(201, {'status': 'created'}))
    outbox_client.upload(UUID_A, '{}', 'abc', None, None, poster=poster)
    assert 'entrepriseSlug' not in poster.call_args.args[0]
    body = json.loads(poster.call_args.kwargs['data'].decode('utf-8'))
    assert 'syncRecord' not in body


def test_upload_nenvoie_pas_de_corps_gzip() -> None:
    # upload-roast ne décompresse pas : un corps gzippé y devient « Invalid JSON body »
    poster = MagicMock(return_value=_response(201, {'status': 'created'}))
    outbox_client.upload(UUID_A, 'x' * 5000, 'abc', None, None, poster=poster)
    headers = poster.call_args.kwargs['headers']
    assert 'gzip' not in json.dumps(headers).lower()
    assert headers['Content-Type'].startswith('application/json')


def test_upload_400_est_permanent() -> None:
    poster = MagicMock(return_value=_response(400, {'error': 'Invalid JSON body'}))
    res = outbox_client.upload(UUID_A, '{}', 'abc', None, None, poster=poster)
    assert res.ok is False
    assert res.permanent is True
    assert 'Invalid JSON body' in (res.error or '')


def test_upload_429_reste_transitoire() -> None:
    # trop de requêtes : rejouer plus tard a du sens, contrairement à un 400
    poster = MagicMock(return_value=_response(429, {'error': 'slow down'}))
    res = outbox_client.upload(UUID_A, '{}', 'abc', None, None, poster=poster)
    assert res.permanent is False


def test_upload_500_est_transitoire() -> None:
    poster = MagicMock(return_value=_response(500, {'error': 'boom'}))
    res = outbox_client.upload(UUID_A, '{}', 'abc', None, None, poster=poster)
    assert res.ok is False
    assert res.permanent is False


def test_upload_exception_reseau_est_transitoire() -> None:
    poster = MagicMock(side_effect=OSError('network down'))
    res = outbox_client.upload(UUID_A, '{}', 'abc', None, None, poster=poster)
    assert res.ok is False
    assert res.permanent is False
    assert res.http_status is None
    assert 'network down' in (res.error or '')


def test_receipt_present_expose_le_hash() -> None:
    getter = MagicMock(return_value=_response(200, {'present': True, 'contentHash': 'abc123',
                                                    'roastId': 'r1', 'beanCreated': False,
                                                    'storeResolved': True}))
    res = outbox_client.fetch_receipt(UUID_A, getter=getter)
    assert res.present is True
    assert res.content_hash == 'abc123'
    assert res.roast_id == 'r1'
    assert res.store_resolved is True


def test_receipt_404_absent() -> None:
    getter = MagicMock(return_value=_response(404, {'present': False}))
    res = outbox_client.fetch_receipt(UUID_A, getter=getter)
    assert res.present is False
    assert res.http_status == 404


def test_receipt_500_nest_pas_une_absence() -> None:
    # une panne serveur ne doit pas être lue comme « la donnée n'est pas là »
    getter = MagicMock(return_value=_response(500, {'error': 'boom'}))
    res = outbox_client.fetch_receipt(UUID_A, getter=getter)
    assert res.present is False
    assert res.error is not None


def test_receipt_url_derivee_de_api_base_url() -> None:
    with patch.object(outbox_client.config, 'api_base_url',
                      'https://x.example/functions/v1/artisan-api/v1'):
        assert outbox_client.receipt_url(UUID_A) == (
            f'https://x.example/functions/v1/artisan-api/v1/aroast-receipt/{UUID_A}')
