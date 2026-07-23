from datetime import date, datetime, time

from typing import Any, TYPE_CHECKING

from google.api_core.exceptions import InvalidArgument
from pydantic import field_validator, computed_field, model_validator
from sqlalchemy import Column, ARRAY
from sqlmodel import Field, Relationship, SQLModel

from schema.links import UserEventRSVPLink
from schema.time_range import TimeRangeType, _parse_time

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
    name:str = Field(index=True)
    time_range: tuple[time, time] = Field(sa_column=Column(TimeRangeType))
    created_at: datetime = Field(default_factory=datetime.now)

    group: "Group" = Relationship()
    rsvp_users: list["User"] = Relationship(
        back_populates="rsvp_events",
        link_model=UserEventRSVPLink,
    )
    poll_times: list[tuple[time, time]] = Field(sa_column=Column(ARRAY(TimeRangeType)))
    best_poll_time:tuple[time, time] = Field(default=time_range, sa_column=Column(TimeRangeType))

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

    def add_poll_time(self, user: "User", time: "TimeRangeType") -> bool:
        if len(self.poll_times) == 0 or len(self.poll_times) != len(self.rsvp_users) + 1:
            return False
        if user in self.rsvp_users:
            #add one to the rsvp users index because the creator's suggested time is always first
            index:int = self.rsvp_users.index(user) + 1
            self.poll_times[index] = (time[0], time[1])
            self.compute_best_poll_time()
            return True
        self.rsvp_users.append(user)
        self.poll_times.append((time[0], time[1]))
        return True


    def remove_poll_time(self, user: "User", time: "TimeRangeType") -> bool:
        if len(self.poll_times) == 0 or len(self.poll_times) != len(self.rsvp_users) + 1:
            return False
        if user in self.rsvp_users:
            #add one to the rsvp users index because the creator's suggested time is always first
            index:int = self.rsvp_users.index(user) + 1
            #hacky but OK
            del self.poll_times[index]
            self.rsvp_users.remove(user)
            self.compute_best_poll_time()
            return True
        return False

    def compute_best_poll_time(self):
        intersect_list = [0] * 48
        max_number = 0
        for tme in self.poll_times:
            start = tme[0].hour * 2 + tme[0].minute // 30
            end = tme[1].hour * 2 + tme[1].minute // 30
            for i in range(start, end + 1):
                intersect_list[i] += 1
                if intersect_list[i] > max_number:
                    max_number = intersect_list[i]
        seen = False
        start = time()
        end = time()
        for indx, item in enumerate(intersect_list):
            if not seen and item == max_number:
                start = time(indx // 2, (indx % 2) * 30)
                seen = True
            if seen and item != max_number:
                #we are now on the first time outside the interval so we get the index before it
                end = time((indx-1) // 2, ((indx-1) % 2) * 30)
        self.best_poll_time = (start, end)


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