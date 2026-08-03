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

from typing import Any
from datetime import time
from sqlalchemy import JSON as SAJSON, TypeDecorator
from sqlalchemy.ext.mutable import MutableList


class PollTimesType(TypeDecorator):
  """Stores list[tuple[time, time]] as a nested JSON list of ISO time strings.

  Db format: [["09:00:00", "10:00:00"], ["13:00:00", "14:00:00"]]
  Python format: [(time(9, 0), time(10, 0)), (time(13, 0), time(14, 0))]
  """

  impl = SAJSON
  cache_ok = True

  def process_bind_param(
          self, value: Any, dialect: Any
  ) -> list[list[str]] | None:
      if value is None:
          return None
      return [
          [_parse_time(t[0]).isoformat(), _parse_time(t[1]).isoformat()]
          for t in value
      ]
  def process_result_value(
      self, value: Any, dialect: Any
  ) -> list[tuple[time, time]]:
    if not value:
      return []
    # Parse list of [str, str] back to list of (time, time) tuples
    return [(_parse_time(item[0]), _parse_time(item[1])) for item in value]

class EventCreate(SQLModel):
    """Fields callers may provide when creating an event."""

    model_config = {"extra": "forbid"}

    name: str
    description: str
    address: str
    location_name: str
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
    event_user_amount: int = Field(default=1)

    group: "Group" = Relationship()
    rsvp_users: list["User"] = Relationship(
        back_populates="rsvp_events",
        link_model=UserEventRSVPLink,
    )
    # List of range tuples using PollTimesType wrapped with MutableList
    poll_times: list[tuple[time, time]] = Field(
        default_factory=list,
        sa_column=Column(MutableList.as_mutable(PollTimesType)),
    )
    best_poll_time: tuple[time, time] | None = Field(
        default=None,
        sa_column=Column(TimeRangeType, nullable=True),
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
        self.event_user_amount = len(self.rsvp_users) + 1
        return True

    def remove_rsvp(self, user: "User") -> bool:
        if user not in self.rsvp_users:
            return False
        self.rsvp_users.remove(user)
        self.event_user_amount = len(self.rsvp_users) + 1
        return True

    def add_poll_time(self, user: "User", time: tuple[time, time]) -> bool:
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
        self.event_user_amount = len(self.rsvp_users) + 1
        return True


    def remove_poll_time(self, user: "User") -> bool:
        if len(self.poll_times) == 0 or len(self.poll_times) != len(self.rsvp_users) + 1:
            return False
        if user in self.rsvp_users:
            #add one to the rsvp users index because the creator's suggested time is always first
            index:int = self.rsvp_users.index(user) + 1
            #hacky but OK
            del self.poll_times[index]
            self.rsvp_users.remove(user)
            self.compute_best_poll_time()
            self.event_user_amount = len(self.rsvp_users) + 1
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
        if max_number == 1:
            #if the highest frequency intersection is frequency of 1, just go with the time given by the creator of the event
            self.best_poll_time = (self.time_range[0], self.time_range[1])
            return
        seen = False
        start = time()
        end = time()
        #todo: some way to discriminate based on length of best interval.
        for indx, item in enumerate(intersect_list):
            if not seen and item == max_number:
                start = time(indx // 2, (indx % 2) * 30)
                seen = True
            if seen and item != max_number:
                #we are now on the first time outside the interval so we get the index before it
                end = time((indx-1) // 2, ((indx-1) % 2) * 30)
        self.best_poll_time = (start, end)

def create_event(data: EventCreate, polling: bool) -> Event:
    if data.time_range[0] > data.time_range[1]:
        raise InvalidArgument
    event = Event.model_validate(data.model_dump())
    event.best_poll_time = event.time_range
    if polling:
        event.poll_times.append(event.time_range)
    return event

class EventData(SQLModel):
    id: int
    name: str
    description: str
    day: date
    time_range: tuple[time, time]
    created_by: int