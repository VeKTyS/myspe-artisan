#
# outbox_enqueue.py
#
# Point de passage obligé de toute torréfaction sortante : garantir un batch
# number, résoudre la société, déposer le profil complet dans la file.
#
# Ce module remplace l'ancien chemin plus/queue.py -> POST /v1/aroast pour les
# torréfactions. Trois différences de fond avec ce qu'il remplace :
#
#   * il n'exige aucune connexion établie (l'ancien code n'enfilait rien si
#     plus_account était None, c.-à-d. après un simple échec de connexion au
#     démarrage) ;
#   * il envoie le profil COMPLET, pas un record de synthèse : une mise à jour
#     ne peut donc plus effacer des champs déjà en base ;
#   * il refuse d'envoyer sans société plutôt que de laisser le serveur deviner.

import datetime
import logging
import uuid as _uuid
from typing import Any, Final

from plus.batch_number import next_fallback_batch
from plus.entity import resolve_entity_slug
from plus.outbox import OutboxItem, get_store

_log: Final[logging.Logger] = logging.getLogger(__name__)

SETTING_LAST_VALID: Final[str] = 'zabawa/last_valid_batch'
SETTING_SUFFIX_COUNT: Final[str] = 'zabawa/batch_suffix_count'


def _settings() -> Any:
    from PyQt6.QtCore import QSettings
    return QSettings()


def _sync_record() -> dict[str, Any] | None:
    """Record de synthèse joint à l'envoi.

    Il alimente artisan_payload côté serveur, donc la sync descendante
    (GET /v1/aroast/<uuid>) par laquelle le desktop rapatrie les modifications
    faites sur le web. Sans lui, débrancher POST /v1/aroast casserait ce retour.
    """
    try:
        from plus import roast
        record, _ = roast.getSyncRecord()
        return record or None
    except Exception as e:  # pylint: disable=broad-except
        _log.exception(e)
        return None


def wake_worker() -> None:
    """Réveille le worker s'il tourne (sinon le prochain tic s'en chargera)."""
    try:
        from plus import config
        aw = config.app_window
        worker = getattr(aw, 'outbox_worker', None) if aw is not None else None
        if worker is not None:
            worker.wake()
    except Exception as e:  # pylint: disable=broad-except
        _log.exception(e)


def ensure_batch_number(qmc: Any, settings: Any, day: str | None = None) -> str | None:
    """Garantit un batch number et renvoie son libellé.

    Artisan n'attribue roastbatchnr que si le compteur est actif ET si la
    torréfaction passe par DROP. Sans numéro, le serveur ne peut plus
    dédupliquer (matchBy=batch_number) ni adopter une fiche saisie à la main.

    Quand le numéro manque, on reprend le dernier numéro valide du poste suffixé
    « bis » (règle métier). La valeur textuelle va dans qmc.batchnumber :
    roastbatchnr est un entier et ne peut pas porter '42bis'.
    """
    try:
        nr = int(getattr(qmc, 'roastbatchnr', 0) or 0)
    except (TypeError, ValueError):
        nr = 0

    if nr > 0:
        prefix = getattr(qmc, 'roastbatchprefix', '') or ''
        label = f'{prefix}{nr}'
        settings.setValue(SETTING_LAST_VALID, label)
        # Un vrai numéro réinitialise la suite des « bis » : le prochain repli
        # repartira de CE numéro-là.
        settings.setValue(SETTING_SUFFIX_COUNT, 0)
        return label

    last_valid = settings.value(SETTING_LAST_VALID, '', type=str) or None
    try:
        suffix_count = int(settings.value(SETTING_SUFFIX_COUNT, 0, type=int) or 0)
    except (TypeError, ValueError):
        suffix_count = 0
    day = day or datetime.date.today().strftime('%Y%m%d')

    label, new_count = next_fallback_batch(last_valid, suffix_count, day)
    settings.setValue(SETTING_SUFFIX_COUNT, new_count)
    qmc.batchnumber = label
    _log.info('batch number de repli attribué: %s', label)
    return label


def _canonical_uuid(qmc: Any) -> str:
    """UUID canonique (avec tirets), tel que l'attend l'API.

    Artisan stocke roastUUID en hexadécimal sans tirets ; l'API valide la forme
    canonique. Un UUID absent ou illisible est régénéré et réécrit dans le
    profil, sinon l'item ne serait pas identifiable côté serveur.
    """
    raw = getattr(qmc, 'roastUUID', None)
    try:
        return str(_uuid.UUID(str(raw)))
    except (ValueError, TypeError, AttributeError):
        canonical = str(_uuid.uuid4())
        qmc.roastUUID = canonical.replace('-', '')
        return canonical


def enqueue_current_roast(
    aw: Any,
    *,
    ask_entity: bool = True,
    settings: Any = None,
) -> bool:
    """Dépose la torréfaction courante dans la file. Renvoie True si enfilée.

    `ask_entity=False` pour les appels automatiques où l'on ne veut pas ouvrir
    de boîte de dialogue : dans ce cas, une société non résolue empêche
    simplement l'enfilement — rien ne part « nu ».
    """
    try:
        if getattr(aw, 'simulator', None):
            return False  # les torréfactions simulées ne partent jamais

        qmc = aw.qmc
        cfg = settings if settings is not None else _settings()

        batch_label = ensure_batch_number(qmc, cfg)
        uuid = _canonical_uuid(qmc)

        entity = resolve_entity_slug(
            getattr(qmc, 'plus_store', None),
            getattr(qmc, 'plus_entity', None),
            None,
        )
        if entity is None and ask_entity:
            answer = _ask_entity(aw)
            if answer is not None:
                entity, label = answer
                qmc.plus_entity = entity
                qmc.plus_entity_label = label
        if entity is None:
            _log.info('torréfaction non enfilée: société non résolue')
            _notify(aw, 'Torréfaction non envoyée : société non renseignée '
                        '(choisissez-la dans Propriétés).')
            return False

        alog_content = repr(aw.getProfile())
        store = get_store()
        item: OutboxItem = store.enqueue(
            uuid,
            alog_content,
            sync_record=_sync_record(),
            entity_slug=entity,
            batch_label=batch_label,
            now=_now(),
            roast_at=_roast_epoch(qmc),
            bean_label=_bean_label(qmc),
        )
        _log.info('torréfaction enfilée: %s (%s, %s)', item.uuid, batch_label, entity)
        _notify(aw, f'Torréfaction {batch_label or ""} en file d\'envoi vers ZABAWA.plus')
        wake_worker()
        return True
    except Exception as e:  # pylint: disable=broad-except
        # Une exception ici ferait perdre la torréfaction en silence : on la
        # trace et on le dit à l'opérateur.
        _log.exception(e)
        _notify(aw, f'Mise en file impossible : {e}')
        return False


def _now() -> float:
    import time
    return time.time()


def _roast_epoch(qmc: Any) -> float | None:
    """Date et heure de la torréfaction, en epoch.

    roastepoch est renseigné par Artisan à CHARGE. Repli sur l'heure courante
    plutôt que rien : dans le panneau de la file, une ligne sans date est
    inexploitable pour retrouver la cuisson concernée.
    """
    try:
        epoch = float(getattr(qmc, 'roastepoch', 0) or 0)
        if epoch > 0:
            return epoch
    except (TypeError, ValueError):
        pass
    return _now()


def _bean_label(qmc: Any) -> str | None:
    """Libellé du café torréfié, tel qu'affiché dans la file.

    Un mélange l'emporte sur un café simple (c'est ce que l'opérateur a choisi),
    puis le libellé du café, puis les champs libres du profil.
    """
    for attr in ('plus_blend_label', 'plus_coffee_label', 'beans', 'title'):
        value = getattr(qmc, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _notify(aw: Any, message: str) -> None:
    try:
        aw.sendmessage(message)
    except Exception:  # pylint: disable=broad-except
        pass


def _ask_entity(aw: Any) -> tuple[str, str] | None:
    """Demande la société à l'opérateur. Renvoie (slug, libellé) ou None.

    Délègue à aw.ask_entity() quand l'application en fournit une (c'est le cas
    en production, cf. artisanlib/outbox_panel.py) pour que ce module reste
    testable sans Qt.
    """
    asker = getattr(aw, 'ask_entity', None)
    if asker is None:
        return None
    try:
        return asker()
    except Exception as e:  # pylint: disable=broad-except
        _log.exception(e)
        return None
