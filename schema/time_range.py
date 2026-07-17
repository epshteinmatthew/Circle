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



def roundTime(dt, roundTo=30):
   """Round a datetime object to any time lapse in seconds
   dt : datetime.datetime object, default now.
   roundTo : Closest number of seconds to round to, default 1 minute.
   Author: Thierry Husson 2012 - Use it as you want but don't blame me.
   """
   if dt == None : return None
   seconds = (dt.replace(tzinfo=None) - dt.min).seconds
   rounding = (seconds+roundTo/2) // roundTo * roundTo
   return dt + timedelta(0,rounding-seconds,-dt.microsecond)






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





