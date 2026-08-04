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


# ---------------------------------------------------------------------------
# Date, grain et rapport d'erreur copiable
# ---------------------------------------------------------------------------

import time
from dataclasses import dataclass

from artisanlib.outbox_panel import _format_roast_date, error_report


@dataclass
class _Item:
    uuid: str = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    batch_label: str | None = '#42'
    bean_label: str | None = 'Pérou APU Cenfrocafe'
    entity_slug: str | None = 'esperanza'
    roast_at: float | None = None
    state: str = 'failed'
    attempts: int = 3
    last_http_status: int | None = 500
    last_error: str | None = 'overwrite: magasin introuvable ou ambigu'


def test_date_formatee_en_francais() -> None:
    epoch = time.mktime(time.strptime('2026-08-04 09:17', '%Y-%m-%d %H:%M'))
    assert _format_roast_date(epoch) == '04/08/2026 09:17'


def test_date_absente_affiche_un_tiret() -> None:
    assert _format_roast_date(None) == '—'
    assert _format_roast_date(0) == '—'


def test_rapport_derreur_contient_tout_le_necessaire() -> None:
    rapport = error_report(_Item(roast_at=1785000000))
    assert '#42' in rapport
    assert 'Pérou APU Cenfrocafe' in rapport
    assert 'esperanza' in rapport
    assert 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' in rapport
    assert '500' in rapport
    assert 'magasin introuvable ou ambigu' in rapport
    assert '3 tentative(s)' in rapport


def test_rapport_sans_erreur_reste_lisible() -> None:
    rapport = error_report(_Item(last_error=None, last_http_status=None, state='pending'))
    assert 'Erreur : aucune' in rapport
    assert 'Code HTTP' not in rapport
