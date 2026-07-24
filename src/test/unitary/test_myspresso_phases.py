"""Unit tests for the MySpresso DÉVELOPPEMENT tile computation.

The development stopwatch must anchor to the moment BT crosses the fixed
threshold of 202 °C (first-crack territory) — NOT to the 1C event marker
(``timeindex[2]``), which some machines/events set earlier. These tests pin
that rule down on the pure ``development_display`` helper so it can be verified
without a running Qt widget.
"""

from artisanlib.myspresso_phases import (
    DEV_THRESHOLD_C,
    _dev_start_index,
    _dev_threshold,
    development_display,
)


def test_threshold_is_202_celsius_and_converts_to_fahrenheit() -> None:
    assert DEV_THRESHOLD_C == 202.0
    assert _dev_threshold('C') == 202.0
    # 202 °C == 395.6 °F: the rule stays physically 202 °C in Fahrenheit mode.
    assert abs(_dev_threshold('F') - 395.6) < 0.01


def test_start_index_ignores_charge_residual_and_finds_rising_crossing() -> None:
    # Hot-drum residual (205) right at CHARGE must NOT start the clock: BT has to
    # first drop below the threshold (turning point) before a crossing counts.
    temp2 = [205, 150, 100, 150, 201, 202, 210]
    #         0    1    2    3    4    5    6
    assert _dev_start_index(temp2, 0, 202.0) == 5


def test_start_index_none_when_threshold_never_reached() -> None:
    temp2 = [100, 150, 180, 199, 201]
    assert _dev_start_index(temp2, 0, 202.0) is None


def test_start_index_skips_invalid_sentinels() -> None:
    temp2 = [100, -1, 150, -1, 203]
    assert _dev_start_index(temp2, 0, 202.0) == 4


def test_display_starts_at_202_not_at_1C_marker() -> None:
    timex = list(range(11))  # 0..10 s
    temp2 = [90, 100, 150, 190, 202, 205, 208, 210, 212, 214, 216]
    # BT crosses 202 at index 4. A 1C marker set early at index 2 must be ignored.
    timeindex = [0, 0, 2, 0, 0, 0, 0, 0]
    value, sub, state, progress = development_display(timex, temp2, timeindex, 'C', 10.0)
    assert value == '00:06'  # 10 - 4 s since the 202 °C crossing
    assert state == 'active'


def test_display_done_at_drop_uses_drop_time_for_dtr() -> None:
    timex = list(range(11))
    temp2 = [90, 100, 150, 190, 202, 205, 208, 210, 212, 214, 216]
    timeindex = [0, 0, 0, 0, 0, 0, 8, 0]  # DROP at index 8 (t=8)
    value, sub, state, progress = development_display(timex, temp2, timeindex, 'C', 10.0)
    assert value == '00:04'  # drop(8) - cross(4)
    assert sub == '50.0 %'   # dev(4) / total(8)
    assert state == 'done'
    assert progress == 1.0


def test_display_idle_before_charge() -> None:
    assert development_display([], [], [-1, 0, 0, 0, 0, 0, 0, 0], 'C', 0.0) == (
        '--:--', '', 'idle', 0.0)


def test_display_idle_when_threshold_not_yet_reached() -> None:
    timex = list(range(5))
    temp2 = [90, 120, 160, 190, 199]  # never hits 202
    timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
    assert development_display(timex, temp2, timeindex, 'C', 4.0) == ('--:--', '', 'idle', 0.0)


def test_display_fahrenheit_crossing() -> None:
    timex = list(range(8))
    # BT in °F; 202 °C == 395.6 °F, crossed at index 4.
    temp2 = [200, 250, 300, 390, 396, 400, 405, 410]
    timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
    value, sub, state, progress = development_display(timex, temp2, timeindex, 'F', 7.0)
    assert value == '00:03'  # 7 - 4
    assert state == 'active'
