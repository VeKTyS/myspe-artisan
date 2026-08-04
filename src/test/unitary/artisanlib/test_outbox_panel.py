"""Tests de l'étiquette d'état de la file d'envoi.

Le libellé est la seule logique métier de ce module d'interface : c'est lui qui
dit à l'opérateur, sans ouvrir de menu, si une torréfaction est restée en
chemin. L'ancien dispositif n'affichait rien du tout en cas d'échec.
"""

from artisanlib.outbox_panel import badge_text


def test_badge_a_jour() -> None:
    assert badge_text({}, 0) == '✓ à jour'
    assert badge_text({'verified': 12}, 0) == '✓ à jour'


def test_badge_en_attente() -> None:
    assert badge_text({'pending': 2}, 0) == '2 en attente'
    assert badge_text({'pending': 1}, 0) == '1 en attente'


def test_badge_sent_compte_comme_en_attente() -> None:
    # 'sent' = envoyé mais pas encore confirmé : pour l'opérateur, c'est en cours
    assert badge_text({'sent': 1}, 0) == '1 en attente'
    assert badge_text({'sent': 1, 'pending': 2}, 0) == '3 en attente'


def test_badge_echec_prioritaire() -> None:
    assert badge_text({'pending': 2, 'failed': 1}, 0) == '1 échec, 2 en attente'
    assert badge_text({'failed': 3}, 0) == '3 échecs'


def test_badge_a_verifier() -> None:
    assert badge_text({}, 3) == '3 à vérifier'
    assert badge_text({'verified': 5}, 1) == '1 à vérifier'


def test_badge_cumule_les_situations() -> None:
    assert badge_text({'pending': 1, 'failed': 2}, 3) == '2 échecs, 1 en attente, 3 à vérifier'
