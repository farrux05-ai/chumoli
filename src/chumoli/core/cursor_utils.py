"""Parse UI cursor/initial values for incremental extract filters."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_cursor_value(raw: Any) -> Any:
    """UI string → dlt incremental initial_value (datetime, int, or str).

    Rules (avoids timestamp >= integer errors):
      - ISO date ``2016-05-01`` → datetime(2016, 5, 1)
      - ISO datetime ``2016-05-01T00:00:00`` → datetime
      - Year only ``2016`` → datetime(2016, 1, 1)  (not int — common user intent)
      - Other pure integers → int
      - Everything else → string as-is
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return int(raw)

    s = str(raw).strip()
    if not s:
        return None

    # ISO datetime / date first (before digit-only branch)
    try:
        if "T" in s or (" " in s and ":" in s):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        # Full ISO date YYYY-MM-DD
        if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
            d = date.fromisoformat(s[:10])
            return datetime(d.year, d.month, d.day)
    except ValueError:
        pass

    # Pure digits / negative int
    neg = s[0] == "-"
    digits = s[1:] if neg else s
    if digits.isdigit():
        # 4-digit year (1900–2100) → Jan 1 of that year (not integer)
        if not neg and len(digits) == 4:
            year = int(digits)
            if 1900 <= year <= 2100:
                return datetime(year, 1, 1)
        return int(s)

    try:
        d = date.fromisoformat(s)
        return datetime(d.year, d.month, d.day)
    except ValueError:
        return s
