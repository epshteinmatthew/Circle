import enum
from typing import Any, Optional
from datetime import time, datetime, timedelta

from sqlalchemy import Column, Enum
from sqlalchemy.types import TypeDecorator, JSON as SAJSON
from sqlmodel import SQLModel, Field, Relationship

from schema import User
from schema.event import _parse_time

class DayOfWeek(enum.Enum):
    MON = "Monday"
    TUE = "Tuesday"
    WED = "Wednesday"
    THU = "Thursday"
    FRI = "Friday"
    SAT = "Saturday"
    SUN = "Sunday"

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


class AvailabilitySlot(SQLModel, table=True):
    __tablename__ = "availability_slots"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign key referencing the users table
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")

    # Store the day as an Enum
    day: DayOfWeek = Field(sa_column=Column(Enum(DayOfWeek), nullable=False))

    # Use your original custom TimeRangeType here via sa_column!
    time_range: tuple[time, time] = Field(
        sa_column=Column(TimeRangeType, nullable=False)
    )

    # Link back to the parent User
    user: Optional[User] = Relationship(back_populates="availabilities")


def getIntervalIntersections(slots: list[AvailabilitySlot], day: DayOfWeek):
    """Returns a tuple (max_number, max_indices) where max_number is the maximum number of intersecting slots, and max_indices is an array of indices which correspond to times when this intersection takes place.
    Any given index can be translated to a time by dividing the index by two to get the hours and multiplying the remainder by 30 to get the minutes"""
    intersect_list = [0] * 48
    max_number = 0
    for slot in slots:
        if slot.day == day:
            start = slot.time_range[0].hour * 2 + slot.time_range[0].minute // 30
            end = slot.time_range[1].hour * 2 + slot.time_range[1].minute // 30
            for i in range(start, end+1):
                intersect_list[i] += 1
                if intersect_list[i] > max_number:
                    max_number = intersect_list[i]
    max_indices = []
    for item, index in enumerate(intersect_list):
        if item == max_number:
            max_indices.append(index)
    return max_number, max_indices

