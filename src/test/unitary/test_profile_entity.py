"""La société doit faire l'aller-retour profil ↔ fichier, comme plus_store.

Ce test lit le source plutôt que d'instancier ApplicationWindow (28 000 lignes,
qui exige un QApplication complet) : ce qu'il vérifie, c'est que les quatre
points de passage du champ existent — déclaration, liste des champs de profil,
écriture, lecture. Un oubli sur l'un d'eux fait silencieusement disparaître la
société du fichier, et la torréfaction repart « nue » vers le serveur.
"""

from pathlib import Path

SRC = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding='utf-8')


def test_les_attributs_existent_sur_le_canvas() -> None:
    src = _read('artisanlib/canvas.py')
    assert 'self.plus_entity:str|None = None' in src
    assert 'self.plus_entity_label:str|None = None' in src
    assert 'self.batchnumber:str|None = None' in src


def test_les_champs_sont_dans_la_liste_de_profil() -> None:
    src = _read('artisanlib/canvas.py')
    assert "'plus_entity', 'plus_entity_label'" in src
    assert "'batchnumber'" in src


def test_les_champs_sont_ecrits_par_getProfile() -> None:
    src = _read('artisanlib/main.py')
    assert "profile['plus_entity'] = encodeLocalStrict(plus_entity)" in src
    assert "profile['plus_entity_label']" in src
    assert "profile['batchnumber']" in src


def test_les_champs_sont_relus_par_setProfile() -> None:
    src = _read('artisanlib/main.py')
    assert 'self.qmc.plus_entity = plus.entity.resolve_entity_slug(' in src
    assert 'self.qmc.plus_entity_label = (' in src
    assert 'self.qmc.batchnumber = (' in src


def test_le_type_de_profil_declare_les_champs() -> None:
    src = _read('artisanlib/atypes.py')
    assert 'plus_entity: str' in src
    assert 'plus_entity_label: str' in src
    assert 'batchnumber: str' in src
