import enum
from typing import Any, Optional
from datetime import time, datetime, timedelta, timezone

from sqlalchemy import Column, Enum
from sqlalchemy.types import TypeDecorator, JSON as SAJSON
from sqlmodel import SQLModel, Field, Relationship

def _parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        return time.fromisoformat(value)
    raise TypeError(f"Cannot parse time from {value!r}")


def roundTime(value, roundTo=30 * 60):
    """Round a time-of-day to nearest roundTo seconds (default 30 minutes)."""
    if value is None:
        return None
    if isinstance(value, str):
        value = time.fromisoformat(value)
    if isinstance(value, datetime):
        t = value.time().replace(tzinfo=None)
    elif isinstance(value, time):
        t = value.replace(tzinfo=None) if value.tzinfo else value
    else:
        raise TypeError(f"Cannot round {value!r}")

    total = t.hour * 3600 + t.minute * 60 + t.second
    rounded = int((total + roundTo / 2) // roundTo * roundTo) % (24 * 3600)
    return time(rounded // 3600, (rounded % 3600) // 60, rounded % 60)


def round_datetime(value: datetime, round_to: int = 30 * 60) -> datetime:
    """Round a datetime to the nearest round_to seconds (default 30 minutes)."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    ts = int(value.timestamp())
    rounded = int((ts + round_to / 2) // round_to * round_to)
    return datetime.fromtimestamp(rounded, tz=timezone.utc)





def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise TypeError(f"Cannot parse datetime from {value!r}")


class TimeRangeType(TypeDecorator):
    """Store tuple[time, time] as JSON list of ISO time strings."""

    impl = SAJSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> list[str] | None:
        if value is None:
            return None
        start, end = value
        start, end = _parse_time(start), _parse_time(end)
        return [start.isoformat(), end.isoformat()]

    def process_result_value(self, value: Any, dialect: Any) -> tuple[time, time] | None:
        if value is None:
            return None
        return _parse_time(value[0]), _parse_time(value[1])


class DateTimeRangeType(TypeDecorator):
    """Store tuple[datetime, datetime] as JSON list of ISO datetime strings."""

    impl = SAJSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> list[str] | None:
        if value is None:
            return None
        start, end = value
        return [_parse_datetime(start).isoformat(), _parse_datetime(end).isoformat()]

    def process_result_value(
        self, value: Any, dialect: Any
    ) -> tuple[datetime, datetime] | None:
        if value is None:
            return None
        return _parse_datetime(value[0]), _parse_datetime(value[1])





