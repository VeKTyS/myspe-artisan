#
# outbox_processor.py
#
# Logique d'acquittement de la file d'envoi : envoyer, relire le reçu, acquitter.
#
# Séparée du QThread (plus/outbox_worker.py) et sans aucun import Qt au niveau
# module : c'est ici que se décide si une torréfaction est réputée arrivée, donc
# ce code doit rester testable sans interface, sans réseau et sans horloge.

import logging
import time
from typing import Any, Callable, Final

from plus.outbox import STATE_SENT, OutboxStore

_log: Final[logging.Logger] = logging.getLogger(__name__)


def process_once(
    store: OutboxStore,
    *,
    uploader: Callable[..., Any],
    receipter: Callable[..., Any],
    now: float,
    on_verified: Callable[[str, Any], None] | None = None,
) -> int:
    """Un tour de file. Renvoie le nombre d'items traités.

    Deux populations sont traitées :
      * les items déjà envoyés (sent) — à re-vérifier SANS réenvoi, sinon un
        reçu momentanément indisponible ferait renvoyer inutilement un profil
        de plusieurs centaines de Ko ;
      * les items échus (pending) — à envoyer.
    """
    treated = 0
    for item in store.sent_items() + store.due_items(now):
        treated += 1

        if item.state != STATE_SENT:
            try:
                content = store.content(item.uuid)
            except (KeyError, OSError) as e:
                # Fichier disparu : rejouer n'y changera rien. L'item doit être
                # visible en échec plutôt que boucler en silence.
                store.mark_error(item.uuid, http_status=None,
                                 error=f'contenu introuvable: {e}', permanent=True, now=now)
                continue
            res = uploader(item.uuid, content, item.content_sha256,
                           item.sync_record, item.entity_slug)
            if not res.ok:
                store.mark_error(item.uuid, http_status=res.http_status,
                                 error=res.error or "échec de l'envoi",
                                 permanent=res.permanent, now=now)
                continue
            store.mark_sent(item.uuid, http_status=res.http_status or 0,
                            server_roast_id=res.server_roast_id,
                            bean_created=res.bean_created,
                            store_resolved=res.store_resolved, now=now)

        receipt = receipter(item.uuid)
        if not receipt.present:
            # Une panne du reçu n'est pas une absence de donnée : les deux cas
            # se rejouent, mais le message doit rester lisible pour l'opérateur.
            reason = (f'reçu indisponible: {receipt.error}' if receipt.error
                      else 'reçu absent côté serveur')
            store.mark_error(item.uuid, http_status=receipt.http_status,
                             error=reason, permanent=False, now=now)
            continue
        # content_hash vide = torréfaction ingérée avant la migration du hash :
        # on ne bloque pas la file dessus.
        if receipt.content_hash and receipt.content_hash.lower() != item.content_sha256.lower():
            store.mark_error(item.uuid, http_status=receipt.http_status,
                             error='reçu : une autre version est en base',
                             permanent=False, now=now)
            continue

        store.mark_verified(item.uuid, now=now)
        if on_verified is not None:
            try:
                on_verified(item.uuid, item.sync_record)
            except Exception as e:  # pylint: disable=broad-except
                # L'acquittement reste acquis : la donnée EST arrivée, seul le
                # cache local n'a pas suivi.
                _log.exception(e)
    return treated


def default_on_verified(uuid: str, sync_record: Any) -> None:
    """Tient à jour le cache de sync et l'icône d'état après acquittement.

    Ce travail était fait par Worker.addSyncItem dans plus/queue.py. Les
    torréfactions n'empruntant plus cette route, il se fait ici — sans quoi
    l'icône d'état et le suivi des éditions cesseraient de fonctionner.
    """
    try:
        from plus import config, roast, sync, util
        if isinstance(sync_record, dict) and 'modified_at' in sync_record:
            sync.addSync(uuid, util.ISO86012epoch(sync_record['modified_at']))
        else:
            sync.addSync(uuid, time.time())
        sr, h = roast.getSyncRecord()
        if sr.get('roast_id') == uuid:
            sync.setSyncRecordHash(sync_record=sr, h=h)
        aw = config.app_window
        if aw is not None:
            aw.updatePlusStatusSignal.emit()  # @UndefinedVariable
    except Exception as e:  # pylint: disable=broad-except
        _log.exception(e)

    # Le serveur vient de décrémenter le café vert de cette torréfaction : on
    # rafraîchit le stock local sans attendre l'expiration du cache, sinon le
    # poste continue d'afficher un stock qu'on sait déjà périmé.
    try:
        from plus import stock
        stock.invalidate()
        stock.update()
    except Exception as e:  # pylint: disable=broad-except
        _log.exception(e)
