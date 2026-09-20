from datetime import datetime

from chumoli.core.cursor_utils import parse_cursor_value


def test_parse_empty() -> None:
    assert parse_cursor_value(None) is None
    assert parse_cursor_value("") is None
    assert parse_cursor_value("  ") is None


def test_parse_int() -> None:
    assert parse_cursor_value("1000") == 1000
    assert parse_cursor_value("0") == 0


def test_parse_date() -> None:
    v = parse_cursor_value("2016-05-01")
    assert isinstance(v, datetime)
    assert v.year == 2016 and v.month == 5 and v.day == 1


def test_parse_datetime() -> None:
    v = parse_cursor_value("2016-05-01T12:30:00")
    assert isinstance(v, datetime)
    assert v.hour == 12 and v.minute == 30


def test_sql_manifest_has_initial_field() -> None:
    # Avoid importing dlt-backed connector module
    text = open("src/chumoli/connectors/sql_database/connector.py", encoding="utf-8").read()
    assert "cursor_initial_value" in text
    assert "parse_cursor_value" in text
