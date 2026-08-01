import enum
from typing import Any, Optional
from datetime import time, datetime, timedelta

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





class TimeRangeType(TypeDecorator):
    """Store tuple[time, time] as JSON list of ISO time strings."""

    impl = SAJSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> list[str] | None:
        if value is None:
            return None
        start, end = value
        return [start.isoformat(), end.isoformat()]

    def process_result_value(self, value: Any, dialect: Any) -> tuple[time, time] | None:
        if value is None:
            return None
        return _parse_time(value[0]), _parse_time(value[1])





