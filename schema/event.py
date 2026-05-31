from datetime import date, datetime, time
from typing import Any, TYPE_CHECKING

from pydantic import field_validator, computed_field, model_validator
from sqlalchemy import Column
from sqlalchemy.types import JSON as SAJSON
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, Relationship, SQLModel

from schema.links import UserEventRSVPLink

if TYPE_CHECKING:
    from schema.group import Group
    from schema.user import User


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


class EventCreate(SQLModel):
    """Fields callers may provide when creating an event."""

    model_config = {"extra": "forbid"}

    name: str
    description: str
    day: date
    time_range: tuple[time, time]
    created_by: int
    group_id: int


class Event(EventCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id")
    time_range: tuple[time, time] = Field(sa_column=Column(TimeRangeType))
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(default=time_range[1])

    @model_validator(mode="after")
    def calculate_expires_at(self) -> "Event":
        if self.expires_at is None and hasattr(self, 'day') and self.time_range:
            self.expires_at = datetime.combine(self.day, self.time_range[1])
        return self

    group: "Group" = Relationship()
    rsvp_users: list["User"] = Relationship(
        back_populates="rsvp_events",
        link_model=UserEventRSVPLink,
    )

    @field_validator("time_range", mode="before")
    @classmethod
    def _coerce_time_range(cls, value: Any) -> Any:
        if value is None or isinstance(value, tuple):
            return value
        if isinstance(value, list) and len(value) == 2:
            return _parse_time(value[0]), _parse_time(value[1])
        return value

    def add_rsvp(self, user: "User") -> bool:
        if user in self.rsvp_users:
            return False
        self.rsvp_users.append(user)
        return True

    def remove_rsvp(self, user: "User") -> bool:
        if user not in self.rsvp_users:
            return False
        self.rsvp_users.remove(user)
        return True


def _parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        return time.fromisoformat(value)
    raise TypeError(f"Cannot parse time from {value!r}")


def create_event(data: EventCreate) -> Event:
    """Build a new Event from caller-provided fields only."""
    return Event.model_validate(data.model_dump())
