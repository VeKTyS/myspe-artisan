"""Unit tests for MyQLCDNumber (the MySpresso ValueTile).

MyQLCDNumber is a QLabel-based drop-in replacement for QLCDNumber.
These tests lock the API-compatibility contract every Artisan call
site relies on: display()/value(), digit-count handling (incl. the
legacy setNumDigits alias), no-op segment/decimal-point setters, the
legacy ``QLCDNumber { ... }`` stylesheet rewriting, and click signals.
"""

from PyQt6.QtCore import Qt

from artisanlib.widgets import MyQLCDNumber


def test_display_string_and_value(qtbot) -> None:  # type: ignore[no-untyped-def]
    lcd = MyQLCDNumber()
    qtbot.addWidget(lcd)
    lcd.display('12:34')
    assert lcd.text() == '12:34'
    assert lcd.value() == 0.0  # non-numeric display, like QLCDNumber
    lcd.display('205.3')
    assert lcd.text() == '205.3'
    assert lcd.value() == 205.3


def test_display_numbers(qtbot) -> None:  # type: ignore[no-untyped-def]
    lcd = MyQLCDNumber()
    qtbot.addWidget(lcd)
    lcd.display(42)
    assert lcd.text() == '42'
    assert lcd.intValue() == 42
    lcd.display(3.5)
    assert lcd.text() == '3.5'
    assert lcd.value() == 3.5


def test_digit_count_and_legacy_alias(qtbot) -> None:  # type: ignore[no-untyped-def]
    lcd = MyQLCDNumber()
    qtbot.addWidget(lcd)
    lcd.setDigitCount(3)
    assert lcd.digitCount() == 3
    lcd.setNumDigits(6)
    assert lcd.digitCount() == 6


def test_compat_noops_accept_qlcd_args(qtbot) -> None:  # type: ignore[no-untyped-def]
    from PyQt6.QtWidgets import QFrame, QLCDNumber
    lcd = MyQLCDNumber()
    qtbot.addWidget(lcd)
    # legacy call sites pass QLCDNumber enums — must not raise
    lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
    lcd.setSmallDecimalPoint(False)
    lcd.setFrameStyle(QFrame.Shadow.Plain)
    lcd.setLineWidth(0)


def test_legacy_stylesheet_selector_rewritten(qtbot) -> None:  # type: ignore[no-untyped-def]
    lcd = MyQLCDNumber()
    qtbot.addWidget(lcd)
    lcd.setStyleSheet('QLCDNumber { border-radius: 4; color: #070D1F; background-color: #FAF8F4;}')
    sheet = lcd.styleSheet()
    assert 'MyQLCDNumber' in sheet
    assert 'MyMyQLCDNumber' not in sheet  # word-boundary rewrite, idempotent-safe
    assert '#070D1F' in sheet
    # base tile geometry appended last so it wins the cascade
    assert sheet.rstrip().endswith('MyQLCDNumber { border-radius: 2px; padding: 0px 4px; }')


def test_click_signals(qtbot) -> None:  # type: ignore[no-untyped-def]
    lcd = MyQLCDNumber()
    qtbot.addWidget(lcd)
    lcd.show()
    with qtbot.waitSignals([lcd.clicked, lcd.left_clicked], timeout=1000):
        qtbot.mouseClick(lcd, Qt.MouseButton.LeftButton)
