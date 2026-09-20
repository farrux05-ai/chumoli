from chumoli.core.config import ScheduleConfig, ScheduleKind
import pytest


def test_daily_at_requires_time() -> None:
    with pytest.raises(Exception):
        ScheduleConfig(kind=ScheduleKind.DAILY_AT)


def test_interval_still_requires_minutes() -> None:
    with pytest.raises(Exception):
        ScheduleConfig(kind=ScheduleKind.INTERVAL)
