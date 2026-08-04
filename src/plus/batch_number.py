#
# batch_number.py
#
# Attribution d'un batch number de repli quand Artisan n'en a pas produit.
#
# Artisan n'attribue roastbatchnr que si le compteur de lots est actif ET si la
# torréfaction passe par DROP (canvas.incBatchCounter). Compteur désactivé,
# enregistrement arrêté sans DROP : la torréfaction part sans numéro, et le
# serveur ne peut alors plus la dédupliquer (matchBy=batch_number) ni adopter
# la fiche que quelqu'un aurait saisie à la main pour la même cuisson.
#
# roastbatchnr est un entier et ne peut pas porter '42bis' : la valeur produite
# ici part dans la clé texte 'batchnumber' du profil, que le parseur serveur
# (deriveBatchNumber) lit juste après roastbatchnr.

import re
from typing import Final

# '#42bis' -> base '#42', rang 1 ; '#42bis3' -> base '#42', rang 3.
_BIS_RE: Final[re.Pattern[str]] = re.compile(r'^(?P<base>.*?)bis(?P<n>\d*)$', re.IGNORECASE)


def next_fallback_batch(
    last_valid: str | None,
    suffix_count: int,
    day: str,
) -> tuple[str, int]:
    """Numéro de repli et nouveau compteur de suffixes.

    last_valid   : dernier batch number réellement attribué par Artisan sur ce
                   poste ('#42'), ou None/'' si le poste n'en a jamais eu.
    suffix_count : nombre de replis déjà produits depuis ce numéro.
    day          : date du jour au format YYYYMMDD, utilisée quand le poste n'a
                   aucune référence (première torréfaction).

    '#42' + 0 -> ('#42bis', 1) ; '#42' + 1 -> ('#42bis2', 2).
    """
    base = (last_valid or '').strip()
    if not base:
        # Poste neuf : la date garde le numéro lisible et ordonnable, et reste
        # unique tant que le compteur de suffixes du jour est persisté.
        n = suffix_count + 1
        return f'{day}-{n}', n

    # Un 'bis' passé comme référence ne doit pas engendrer 'bisbis' : on repart
    # de sa racine et on poursuit sa numérotation.
    m = _BIS_RE.match(base)
    if m:
        base = m.group('base')
        already = int(m.group('n')) if m.group('n') else 1
        suffix_count = max(suffix_count, already)

    n = suffix_count + 1
    return (f'{base}bis' if n == 1 else f'{base}bis{n}'), n
