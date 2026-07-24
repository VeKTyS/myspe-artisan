"""Unit tests for util.roast_elapsed_seconds — the MySpresso roast clock.

It must reset to 0 at CHARGE (measured from CHARGE once charged), which fixes
both the DÉVELOPPEMENT counter that started at ~00:59 (the ON→CHARGE gap) and
the hero timer that did not reset at CHARGE. The underlying ArtisanTime clock
runs from ON; the reset is a pure display offset.
"""

from artisanlib.util import roast_elapsed_seconds


def _timeindex(charge: int = -1) -> list[int]:
    # [CHARGE, DRYe, FCs, FCe, SCs, SCe, DROP, COOL]
    ti = [0] * 8
    ti[0] = charge
    return ti


def test_recording_charged_measures_from_charge() -> None:
    # ON at 0, CHARGE 59 s later (timex[charge]=59); live clock 120 s since ON.
    timex = [0.0, 59.0, 120.0]  # CHARGE at index 1
    assert roast_elapsed_seconds(True, True, 120.0, 120.0, timex, _timeindex(1)) == 61.0


def test_recording_resets_to_zero_at_charge() -> None:
    timex = [0.0, 59.0]
    assert roast_elapsed_seconds(True, True, 59.0, 59.0, timex, _timeindex(1)) == 0.0


def test_recording_before_charge_shows_monitor_since_on() -> None:
    timex = [0.0, 1.0, 2.0]
    assert roast_elapsed_seconds(True, True, 30.0, 30.0, timex, _timeindex(-1)) == 30.0


def test_monitoring_only_uses_monitor_seconds() -> None:
    assert roast_elapsed_seconds(False, True, 0.0, 45.0, [], _timeindex(-1)) == 45.0


def test_stopped_charged_uses_timex_since_charge() -> None:
    timex = [0.0, 59.0, 400.0]  # last sample 400 s, CHARGE at 59 s
    assert roast_elapsed_seconds(False, False, 0.0, 0.0, timex, _timeindex(1)) == 341.0


def test_stopped_not_charged_is_zero() -> None:
    assert roast_elapsed_seconds(False, False, 0.0, 0.0, [], _timeindex(-1)) == 0.0


def test_clamped_non_negative_when_offset_exceeds_live() -> None:
    timex = [0.0, 59.0]
    assert roast_elapsed_seconds(True, True, 50.0, 50.0, timex, _timeindex(1)) == 0.0
