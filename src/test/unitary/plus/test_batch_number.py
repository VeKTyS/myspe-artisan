"""Tests de plus.batch_number — attribution du numéro de repli.

Règle métier (francis, 2026-08-04) : quand Artisan n'a pas attribué de numéro,
on reprend le dernier numéro valide du poste et on le suffixe « bis ». Sans
batch number, le serveur ne peut plus dédupliquer (matchBy=batch_number) ni
adopter les fiches saisies à la main.

Le dernier numéro valide ne devient jamais un « bis » : sinon la suite
dériverait en '#42bisbis' au lieu de '#42bis2'.
"""

from plus.batch_number import next_fallback_batch


def test_premier_repli_suffixe_bis() -> None:
    assert next_fallback_batch('#42', 0, '20260804') == ('#42bis', 1)


def test_replis_suivants_numerotes() -> None:
    assert next_fallback_batch('#42', 1, '20260804') == ('#42bis2', 2)
    assert next_fallback_batch('#42', 2, '20260804') == ('#42bis3', 3)


def test_poste_neuf_sans_reference_utilise_la_date() -> None:
    assert next_fallback_batch(None, 0, '20260804') == ('20260804-1', 1)
    assert next_fallback_batch('', 1, '20260804') == ('20260804-2', 2)


def test_un_bis_passe_en_reference_ne_derive_pas() -> None:
    # robustesse : un appelant qui mémoriserait un 'bis' comme dernier valide
    # ne doit pas produire '#42bisbis'
    assert next_fallback_batch('#42bis', 0, '20260804') == ('#42bis2', 2)
    assert next_fallback_batch('#42bis3', 0, '20260804') == ('#42bis4', 4)


def test_reference_avec_espaces_est_nettoyee() -> None:
    assert next_fallback_batch('  #42  ', 0, '20260804') == ('#42bis', 1)


def test_prefixe_absent_reste_lisible() -> None:
    # compteur actif sans préfixe : '42' est un numéro valide comme un autre
    assert next_fallback_batch('42', 0, '20260804') == ('42bis', 1)
