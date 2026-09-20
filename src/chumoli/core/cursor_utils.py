"""Parse UI cursor/initial values for incremental extract filters."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_cursor_value(raw: Any) -> Any:
    """UI string → dlt incremental initial_value (date, int, or str).

    Examples: "2016-05-01", "2016-05-01T00:00:00", "1000"
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.isdigit() or (s[0] == "-" and s[1:].isdigit()):
        return int(s)
    try:
        if "T" in s or " " in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        d = date.fromisoformat(s)
        return datetime(d.year, d.month, d.day)
    except ValueError:
        return s
