"""cursor initial_value parsing — avoid timestamp >= integer."""

from datetime import datetime

from chumoli.core.cursor_utils import parse_cursor_value


def test_year_only_becomes_datetime_not_int():
    v = parse_cursor_value("2016")
    assert isinstance(v, datetime)
    assert v == datetime(2016, 1, 1)


def test_iso_date():
    v = parse_cursor_value("2016-05-01")
    assert v == datetime(2016, 5, 1)


def test_iso_datetime():
    v = parse_cursor_value("2016-05-01T12:30:00")
    assert v == datetime(2016, 5, 1, 12, 30, 0)


def test_numeric_id_stays_int():
    assert parse_cursor_value("1000") == 1000
    assert parse_cursor_value("0") == 0
    assert parse_cursor_value("-5") == -5


def test_empty():
    assert parse_cursor_value("") is None
    assert parse_cursor_value(None) is None
    assert parse_cursor_value("   ") is None
