#
# outbox_client.py
#
# Transport HTTP de la file d'envoi : dépôt de la torréfaction, puis lecture du
# reçu qui prouve son arrivée.
#
# Deux choix de mise en œuvre méritent l'explication :
#
# 1. On n'emprunte PAS plus.connection.sendData, qui gzippe tout corps de plus
#    de 500 octets alors que l'Edge Function upload-roast ne décompresse pas :
#    un profil complet ferait systématiquement « HTTP 400 Invalid JSON body ».
#    On sérialise donc le corps à la main.
#
# 2. Le reçu est une requête distincte, sur une autre fonction (artisan-api).
#    C'est délibéré : un 2xx d'upload dit seulement « j'ai reçu », pas « c'est
#    en base et c'est ta version ». Une écriture concurrente (import web, autre
#    poste) peut avoir remis une version antérieure entre-temps.

import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Final

import requests

from plus import config

_log: Final[logging.Logger] = logging.getLogger(__name__)

# Codes 4xx qu'il reste utile de rejouer : contrairement à un corps invalide,
# ils traduisent un état passager du serveur ou du réseau.
_TRANSIENT_4XX: Final[frozenset[int]] = frozenset({408, 409, 425, 429})


@dataclass(frozen=True)
class UploadResult:
    ok: bool
    http_status: int | None
    permanent: bool
    error: str | None
    server_roast_id: str | None = None
    bean_created: bool = False
    store_resolved: bool | None = None


@dataclass(frozen=True)
class ReceiptResult:
    present: bool
    content_hash: str | None
    http_status: int | None
    error: str | None = None
    roast_id: str | None = None
    bean_created: bool = False
    store_resolved: bool | None = None


def _headers() -> dict[str, str]:
    return {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {config.artisan_service_token}',
        'apikey': config.SUPABASE_ANON_KEY,
    }


def upload_url(entity_slug: str | None) -> str:
    """URL d'envoi.

    createMissingBean=true : sans cette demande explicite, un café absent du
    référentiel de la société atterrit sur la fiche fourre-tout (« Grain
    inconnu ») et le stock n'est pas décrémenté.
    """
    url = (f'{config.upload_roast_url}'
           '?strategy=overwrite&updateInventory=true&createMissingBean=true')
    if entity_slug:
        url += f'&entrepriseSlug={urllib.parse.quote(entity_slug, safe="")}'
    return url


def receipt_url(uuid: str) -> str:
    base = config.api_base_url.rstrip('/')
    return f'{base}/aroast-receipt/{uuid}'


def _error_text(r: Any, status: int) -> str:
    try:
        body = r.json()
        if isinstance(body, dict) and body.get('error'):
            return f'HTTP {status} — {body["error"]}'
    except Exception:  # pylint: disable=broad-except - corps non JSON
        pass
    try:
        return f'HTTP {status} — {str(r.text)[:200]}'
    except Exception:  # pylint: disable=broad-except
        return f'HTTP {status}'


def upload(
    uuid: str,
    alog_content: str,
    content_sha256: str,
    sync_record: dict[str, Any] | None,
    entity_slug: str | None,
    *,
    poster: Callable[..., Any] | None = None,
) -> UploadResult:
    """Dépose la torréfaction. Ne garantit rien d'autre que la réponse HTTP."""
    post = poster if poster is not None else requests.post
    payload: dict[str, Any] = {
        'id': uuid,
        'alogContent': alog_content,
        'contentSha256': content_sha256,
        'source': 'desktop-outbox',
    }
    if sync_record is not None:
        # Alimente artisan_payload côté serveur, donc la sync descendante
        # (GET /v1/aroast/<uuid>) que le desktop utilise pour rapatrier les
        # modifications faites sur le web.
        payload['syncRecord'] = sync_record

    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    try:
        r = post(
            upload_url(entity_slug),
            data=body,
            headers=_headers(),
            timeout=(config.connect_timeout, 30),
            verify=config.verify_ssl,
        )
    except Exception as e:  # pylint: disable=broad-except - réseau, DNS, TLS…
        _log.debug('upload %s: %s', uuid, e)
        return UploadResult(ok=False, http_status=None, permanent=False, error=str(e))

    status = int(r.status_code)
    if 200 <= status < 300:
        try:
            data = r.json()
        except Exception:  # pylint: disable=broad-except
            data = {}
        if not isinstance(data, dict):
            data = {}
        return UploadResult(
            ok=True,
            http_status=status,
            permanent=False,
            error=None,
            server_roast_id=data.get('roastId'),
            bean_created=bool(data.get('beanCreated')),
            store_resolved=data.get('storeResolved'),
        )

    permanent = 400 <= status < 500 and status not in _TRANSIENT_4XX
    return UploadResult(ok=False, http_status=status, permanent=permanent,
                        error=_error_text(r, status))


def fetch_receipt(uuid: str, *, getter: Callable[..., Any] | None = None) -> ReceiptResult:
    """Relit le reçu d'ingestion. `present=False` ne vaut preuve d'absence que
    si `error` est None : une panne serveur n'est pas une absence de donnée."""
    get = getter if getter is not None else requests.get
    try:
        r = get(
            receipt_url(uuid),
            headers=_headers(),
            timeout=(config.connect_timeout, 20),
            verify=config.verify_ssl,
        )
    except Exception as e:  # pylint: disable=broad-except
        _log.debug('reçu %s: %s', uuid, e)
        return ReceiptResult(present=False, content_hash=None, http_status=None, error=str(e))

    status = int(r.status_code)
    if status == 404:
        return ReceiptResult(present=False, content_hash=None, http_status=404)
    if not 200 <= status < 300:
        return ReceiptResult(present=False, content_hash=None, http_status=status,
                             error=_error_text(r, status))
    try:
        data = r.json()
    except Exception as e:  # pylint: disable=broad-except
        return ReceiptResult(present=False, content_hash=None, http_status=status,
                             error=f'reçu illisible: {e}')
    if not isinstance(data, dict):
        return ReceiptResult(present=False, content_hash=None, http_status=status,
                             error='reçu de forme inattendue')
    return ReceiptResult(
        present=bool(data.get('present')),
        content_hash=data.get('contentHash'),
        http_status=status,
        roast_id=data.get('roastId'),
        bean_created=bool(data.get('beanCreated')),
        store_resolved=data.get('storeResolved'),
    )
