import enum
from typing import Any, Optional
from datetime import time

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


