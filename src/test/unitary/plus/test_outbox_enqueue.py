"""Tests de plus.outbox_enqueue — attribution du numéro et dépôt dans la file.

Les deux fonctions testées ici sont le point de passage obligé de toute
torréfaction sortante : un numéro garanti, une société résolue, un contenu
complet. Ce qui échappe à ce module part « nu » vers le serveur.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from plus.outbox import OutboxStore
from plus.outbox_enqueue import (
    ensure_batch_number,
    enqueue_current_roast,
    ensure_roast_enqueued_at_off,
    off_safeguard_action,
)

UUID_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'


class FakeSettings:
    """Double minimal de QSettings, limité à ce qu'utilise le module."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._d: dict[str, Any] = dict(initial or {})

    def value(self, key: str, default: Any = None, type: Any = None) -> Any:  # noqa: A002
        v = self._d.get(key, default)
        if type is int and v is not None:
            return int(v)
        return v

    def setValue(self, key: str, value: Any) -> None:
        self._d[key] = value


class FakeQmc:
    def __init__(self) -> None:
        self.roastbatchnr = 0
        self.roastbatchprefix = '#'
        self.batchnumber: str | None = None
        self.plus_store: str | None = None
        self.plus_entity: str | None = None
        self.plus_entity_label: str | None = None
        self.roastUUID: str | None = UUID_A.replace('-', '')
        self.weight = [10.0, 8.0, 'Kg']
        # Artisan : timeindex[0] = CHARGE (-1 si absent), timeindex[6] = DROP
        # (0 si absent) ; timex = secondes de chaque échantillon.
        self.timeindex = [-1, 0, 0, 0, 0, 0, 0, 0]
        self.timex: list[float] = []

    def charge_puis_arret(self, minutes: float, *, drop: bool = False) -> None:
        """Simule une broche chargée à t=10 s puis arrêtée `minutes` plus tard."""
        self.timex = [0.0, 10.0, 10.0 + minutes * 60]
        self.timeindex[0] = 1
        self.timeindex[6] = 2 if drop else 0


class FakeAw:
    def __init__(self, store: OutboxStore) -> None:
        self.qmc = FakeQmc()
        self.simulator = None
        self._store = store
        self.messages: list[str] = []
        self.asked = 0
        self.answer: tuple[str, str] | None = None

    def sendmessage(self, msg: str, *a: Any, **k: Any) -> None:
        self.messages.append(msg)

    def getProfile(self) -> dict[str, Any]:
        return {'title': 'essai', 'roastUUID': self.qmc.roastUUID}

    def ask_entity(self) -> tuple[str, str] | None:
        self.asked += 1
        return self.answer


@pytest.fixture
def store(tmp_path: Path) -> Iterator[OutboxStore]:
    s = OutboxStore(str(tmp_path))
    yield s
    s.close()


@pytest.fixture
def aw(store: OutboxStore, monkeypatch: pytest.MonkeyPatch) -> FakeAw:
    import plus.outbox_enqueue as mod
    monkeypatch.setattr(mod, 'get_store', lambda: store)
    monkeypatch.setattr(mod, 'wake_worker', lambda: None)
    monkeypatch.setattr(mod, '_sync_record', lambda: {'roast_id': UUID_A})
    return FakeAw(store)


# --------------------------------------------------------------- batch number

def test_numero_existant_est_conserve_et_memorise() -> None:
    qmc, settings = FakeQmc(), FakeSettings()
    qmc.roastbatchnr = 42
    assert ensure_batch_number(qmc, settings) == '#42'
    assert settings.value('zabawa/last_valid_batch') == '#42'
    assert settings.value('zabawa/batch_suffix_count', 0, int) == 0
    assert qmc.batchnumber is None  # pas de repli : le champ texte reste vide


def test_absence_de_numero_produit_un_bis() -> None:
    qmc = FakeQmc()
    settings = FakeSettings({'zabawa/last_valid_batch': '#42'})
    assert ensure_batch_number(qmc, settings) == '#42bis'
    assert qmc.batchnumber == '#42bis'
    assert settings.value('zabawa/batch_suffix_count', 0, int) == 1


def test_deux_replis_de_suite_ne_derivent_pas() -> None:
    settings = FakeSettings({'zabawa/last_valid_batch': '#42'})
    assert ensure_batch_number(FakeQmc(), settings) == '#42bis'
    assert ensure_batch_number(FakeQmc(), settings) == '#42bis2'


def test_poste_neuf_utilise_la_date() -> None:
    qmc, settings = FakeQmc(), FakeSettings()
    label = ensure_batch_number(qmc, settings, day='20260804')
    assert label == '20260804-1'
    assert qmc.batchnumber == '20260804-1'


def test_un_numero_reel_reinitialise_la_suite_des_bis() -> None:
    settings = FakeSettings({'zabawa/last_valid_batch': '#42',
                             'zabawa/batch_suffix_count': 3})
    qmc = FakeQmc()
    qmc.roastbatchnr = 43
    ensure_batch_number(qmc, settings)
    assert settings.value('zabawa/batch_suffix_count', 0, int) == 0
    assert ensure_batch_number(FakeQmc(), settings) == '#43bis'


# ------------------------------------------------------------------ enfilement

def test_enqueue_depose_le_alog_la_societe_et_le_batch(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_entity = 'esperanza'
    aw.qmc.roastbatchnr = 42
    assert enqueue_current_roast(aw, settings=FakeSettings()) is True
    items = store.all_items()
    assert len(items) == 1
    assert items[0].entity_slug == 'esperanza'
    assert items[0].batch_label == '#42'
    assert items[0].sync_record == {'roast_id': UUID_A}
    assert 'essai' in store.content(items[0].uuid)


def test_enqueue_deduit_la_societe_du_magasin(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_store = 'L1002@esperanza'
    aw.qmc.plus_entity = 'myspresso'  # le magasin fait foi
    assert enqueue_current_roast(aw, settings=FakeSettings()) is True
    assert store.all_items()[0].entity_slug == 'esperanza'


def test_enqueue_normalise_luuid(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_entity = 'esperanza'
    aw.qmc.roastUUID = UUID_A.replace('-', '')  # forme hex d'Artisan
    enqueue_current_roast(aw, settings=FakeSettings())
    assert store.all_items()[0].uuid == UUID_A  # forme canonique attendue par l'API


def test_enqueue_sans_societe_demande_et_annule_si_refus(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_store = 'DESKTOP'
    aw.answer = None  # l'opérateur ferme la boîte
    assert enqueue_current_roast(aw, settings=FakeSettings()) is False
    assert aw.asked == 1
    assert store.all_items() == []


def test_enqueue_sans_societe_utilise_la_reponse(aw: FakeAw, store: OutboxStore) -> None:
    aw.answer = ('esperanza', 'Esperanza')
    assert enqueue_current_roast(aw, settings=FakeSettings()) is True
    assert store.all_items()[0].entity_slug == 'esperanza'
    assert aw.qmc.plus_entity == 'esperanza'
    assert aw.qmc.plus_entity_label == 'Esperanza'


def test_enqueue_sans_demande_nenfile_pas_sans_societe(aw: FakeAw, store: OutboxStore) -> None:
    # appel automatique (DROP) : pas de boîte de dialogue intempestive si le
    # contexte l'interdit, mais rien ne part « nu » non plus
    assert enqueue_current_roast(aw, settings=FakeSettings(), ask_entity=False) is False
    assert aw.asked == 0
    assert store.all_items() == []


def test_simulateur_nest_jamais_enfile(aw: FakeAw, store: OutboxStore) -> None:
    aw.simulator = object()
    aw.qmc.plus_entity = 'esperanza'
    assert enqueue_current_roast(aw, settings=FakeSettings()) is False
    assert store.all_items() == []


def test_enqueue_renseigne_date_et_grain(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_entity = 'esperanza'
    aw.qmc.roastepoch = 1785000000
    aw.qmc.plus_coffee_label = 'Pérou, APU Cenfrocafe 2024'
    enqueue_current_roast(aw, settings=FakeSettings())
    item = store.all_items()[0]
    assert item.roast_at == 1785000000
    assert item.bean_label == 'Pérou, APU Cenfrocafe 2024'


def test_le_melange_lemporte_sur_le_cafe_simple(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_entity = 'esperanza'
    aw.qmc.plus_coffee_label = 'Pérou'
    aw.qmc.plus_blend_label = 'Mélange maison'
    enqueue_current_roast(aw, settings=FakeSettings())
    assert store.all_items()[0].bean_label == 'Mélange maison'


def test_sans_roastepoch_on_horodate_quand_meme(aw: FakeAw, store: OutboxStore) -> None:
    # une ligne sans date est inexploitable pour retrouver la cuisson
    aw.qmc.plus_entity = 'esperanza'
    enqueue_current_roast(aw, settings=FakeSettings())
    assert (store.all_items()[0].roast_at or 0) > 0


# ------------------------------------------------------------ filet de l'arrêt
#
# Constat du 2026-10-29 : une broche de 09:46 s'est arrêtée à 10:00 sans que son
# fichier parte. Le serveur a reçu la seule fin de session, a supprimé la ligne
# « en cours », et la torréfaction a disparu. À l'arrêt (OFF), toute broche
# chargée doit être dans la file, quel que soit l'ordre des boutons.

def test_regle_du_filet() -> None:
    def act(**kw: Any) -> str:
        base = {'charged': True, 'dropped': False, 'already_queued': False, 'roast_sec': 900.0}
        return off_safeguard_action(**{**base, **kw})
    assert act(charged=False) == 'none'             # préchauffe : pas de broche
    assert act(already_queued=True) == 'none'       # le DROP l'a déjà enfilée
    assert act() == 'send'                          # OFF sans DROP après 15 min
    assert act(dropped=True, roast_sec=60) == 'send'  # DROP marqué : vraie broche
    assert act(roast_sec=299) == 'ask'              # faux départ possible
    assert act(roast_sec=300) == 'send'


def test_arret_sans_drop_enfile_la_broche(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_store = 'L1002@esperanza'
    aw.qmc.charge_puis_arret(14)
    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings()) is True
    items = store.all_items()
    assert [i.uuid for i in items] == [UUID_A]
    assert items[0].entity_slug == 'esperanza'


def test_drop_refait_sans_envoi_est_rattrape(aw: FakeAw, store: OutboxStore) -> None:
    # DROP annulé puis remis : le second DROP n'enfile rien (autoDROPenabled
    # passe à False). DROP marqué = vraie broche, envoyée même si courte.
    aw.qmc.plus_store = 'L1002@esperanza'
    aw.qmc.charge_puis_arret(3, drop=True)
    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings(),
                                        confirm=lambda _s: False) is True
    assert len(store.all_items()) == 1


def test_broche_deja_enfilee_nest_pas_renvoyee(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_store = 'L1002@esperanza'
    aw.qmc.roastbatchnr = 42
    aw.qmc.charge_puis_arret(18, drop=True)
    enqueue_current_roast(aw, settings=FakeSettings(), ask_entity=False)  # au DROP
    before = store.get(UUID_A)
    aw.messages.clear()
    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings()) is True
    after = store.get(UUID_A)
    assert before is not None and after is not None
    assert after.updated_at == before.updated_at  # pas de ré-enfilement
    assert aw.messages == []


def test_sans_charge_rien_ne_part(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_store = 'L1002@esperanza'
    aw.qmc.timex = [0.0, 600.0]  # enregistrement sans CHARGE (préchauffe)
    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings()) is False
    assert store.all_items() == []


def test_arret_court_sans_drop_demande_avant_denvoyer(aw: FakeAw, store: OutboxStore) -> None:
    aw.qmc.plus_store = 'L1002@esperanza'
    aw.qmc.charge_puis_arret(2)
    asked: list[float] = []

    def refuse(sec: float) -> bool:
        asked.append(sec)
        return False
    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings(), confirm=refuse) is False
    assert asked == [120.0]
    assert store.all_items() == []

    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings(),
                                        confirm=lambda _s: True) is True
    assert len(store.all_items()) == 1


def test_arret_court_sans_boite_de_dialogue_envoie(aw: FakeAw, store: OutboxStore) -> None:
    # Dans le doute, on envoie : une broche en trop se supprime sur le web,
    # une broche perdue ne se retrouve pas.
    aw.qmc.plus_store = 'L1002@esperanza'
    aw.qmc.charge_puis_arret(2)
    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings()) is True


def test_filet_demande_la_societe_si_inconnue(aw: FakeAw, store: OutboxStore) -> None:
    # Au DROP, la société inconnue bloque l'envoi sans rien demander. À l'arrêt,
    # l'enregistrement est fini : on peut poser la question.
    aw.qmc.charge_puis_arret(15, drop=True)
    aw.answer = ('esperanza', 'Esperanza')
    assert ensure_roast_enqueued_at_off(aw, settings=FakeSettings()) is True
    assert aw.asked == 1
    assert store.all_items()[0].entity_slug == 'esperanza'
