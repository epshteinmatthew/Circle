from datetime import date, datetime, time
from typing import Any, TYPE_CHECKING

from google.api_core.exceptions import InvalidArgument
from pydantic import field_validator, computed_field, model_validator
from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

from schema.links import UserEventRSVPLink
from schema.time_range import TimeRangeType

if TYPE_CHECKING:
    from schema.group import Group
    from schema.user import User

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
    if data.time_range[0] > data.time_range[1]:
        raise InvalidArgument
    """Build a new Event from caller-provided fields only."""
    return Event.model_validate(data.model_dump())


class EventData(SQLModel):
    id: int
    name: str
    description: str
    day: date
    time_range: tuple[time, time]
    created_by: int