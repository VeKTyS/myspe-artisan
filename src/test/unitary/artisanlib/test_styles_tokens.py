"""Unit tests for the MySpresso QSS template / design-token pipeline.

The QSS stylesheet is a template referencing design tokens as ``@TOKEN@``
placeholders, resolved by ``artisanlib.styles.load_qss()``. These tests
lock the single-source-of-truth invariant:

- every placeholder used in the QSS exists in ``design_tokens``
- the QSS file contains no hardcoded hex colour literals
- ``load_qss()`` returns fully-resolved CSS (no placeholder survives)
"""

import pathlib
import re

from artisanlib import design_tokens
from artisanlib.styles import _token_values, load_qss

_QSS_PATH = pathlib.Path(design_tokens.__file__).parent / 'styles' / 'myspresso.qss'

_PLACEHOLDER_RE = re.compile(r'@([A-Z][A-Z0-9_]*)@')
_HEX_RE = re.compile(r'#[0-9A-Fa-f]{3,8}\b')


def test_qss_placeholders_all_resolve() -> None:
    qss_template = _QSS_PATH.read_text(encoding='utf-8')
    used = set(_PLACEHOLDER_RE.findall(qss_template))
    assert used, 'QSS template should reference design tokens'
    known = set(_token_values())
    missing = used - known
    assert not missing, f'QSS references unknown design tokens: {sorted(missing)}'


def test_qss_template_has_no_hex_literals() -> None:
    qss_template = _QSS_PATH.read_text(encoding='utf-8')
    hexes = _HEX_RE.findall(qss_template)
    assert not hexes, (
        f'hardcoded hex colours in myspresso.qss (use @TOKEN@ instead): {sorted(set(hexes))}'
    )


def test_load_qss_fully_resolved() -> None:
    qss = load_qss()
    assert qss, 'load_qss() should return the stylesheet'
    leftovers = _PLACEHOLDER_RE.findall(qss)
    assert not leftovers, f'unresolved placeholders after load_qss(): {sorted(set(leftovers))}'
    # spot-check: the app background token must be present, resolved
    assert design_tokens.WARM_100 in qss
