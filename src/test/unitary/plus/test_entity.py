"""Tests de plus.entity — cascade de résolution de la société d'une torréfaction.

Sans société, le serveur ne requalifie pas le code magasin en 'CODE@slug' et ne
résout pas le grain : la torréfaction atterrit sur les fiches fourre-tout
(« Grain inconnu », aucun décrément de stock). Cette cascade est donc le point
unique qui décide du rattachement — d'où le niveau de détail des cas ci-dessous.
"""

from plus.entity import resolve_entity_slug, slug_from_store_hr_id


def test_slug_extrait_du_store_composite() -> None:
    assert slug_from_store_hr_id('L1002@esperanza') == 'esperanza'


def test_slug_absent_dun_code_nu() -> None:
    assert slug_from_store_hr_id('L1002') is None
    assert slug_from_store_hr_id('') is None
    assert slug_from_store_hr_id(None) is None


def test_slug_prend_le_dernier_segment() -> None:
    # un code de magasin peut contenir un '@' : le slug est le DERNIER segment
    assert slug_from_store_hr_id('L@1002@myspresso') == 'myspresso'


def test_slug_normalise_en_minuscules() -> None:
    assert slug_from_store_hr_id('L1002@Esperanza') == 'esperanza'


def test_slug_vide_apres_le_separateur() -> None:
    assert slug_from_store_hr_id('L1002@') is None
    assert slug_from_store_hr_id('L1002@   ') is None


def test_cascade_le_magasin_gagne() -> None:
    # le magasin choisi fait foi : c'est lui qui porte le stock décrémenté
    assert resolve_entity_slug('L1002@esperanza', 'myspresso', 'myspresso') == 'esperanza'


def test_cascade_selecteur_si_magasin_nu() -> None:
    assert resolve_entity_slug('L1002', 'myspresso', None) == 'myspresso'


def test_cascade_profil_en_dernier() -> None:
    assert resolve_entity_slug(None, None, 'esperanza') == 'esperanza'


def test_cascade_normalise_les_valeurs_choisies() -> None:
    assert resolve_entity_slug(None, '  Esperanza  ', None) == 'esperanza'
    assert resolve_entity_slug(None, None, 'MySpresso') == 'myspresso'


def test_cascade_rien_a_resoudre() -> None:
    # None impose à l'appelant de demander la société plutôt que d'envoyer « nu »
    assert resolve_entity_slug(None, None, None) is None
    assert resolve_entity_slug('', '', '') is None
    assert resolve_entity_slug('DESKTOP', None, None) is None
