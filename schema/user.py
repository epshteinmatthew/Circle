from datetime import time
from typing import TYPE_CHECKING

from google.api_core.exceptions import InvalidArgument
from pydantic.v1 import BaseModel
from sqlalchemy import Column, JSON, Enum
from sqlmodel import Field, Relationship, SQLModel

from schema.availabilities import AvailabilitySlot, DayOfWeek, getIntervalIntersections
from schema.links import UserEventRSVPLink, UserGroupLink, UserIncomingGroupLink
from schema.time_range import roundTime, TimeRangeType

if TYPE_CHECKING:
    from schema.event import Event
    from schema.group import Group


class UserCreate(SQLModel):
    """Fields callers may provide when creating a user."""

    model_config = {"extra": "forbid"}

    name: str
    email: str



class User(UserCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)

    rsvp_events: list["Event"] = Relationship(
        back_populates="rsvp_users",
        link_model=UserEventRSVPLink,
    )
    groups: list["Group"] = Relationship(
        back_populates="users",
        link_model=UserGroupLink,
    )

    incoming_groups: list["Group"] = Relationship(
        back_populates="user_requests",
        link_model=UserIncomingGroupLink
    )

    def add_event_rsvp(self, event: "Event") -> bool:
        if event in self.rsvp_events:
            return False
        self.rsvp_events.append(event)
        return True

    def remove_event_rsvp(self, event: "Event") -> bool:
        if event not in self.rsvp_events:
            return False
        self.rsvp_events.remove(event)
        return True

    def add_group(self, group: "Group") -> bool:
        if group in self.groups:
            return False
        self.groups.append(group)
        return True

    def remove_group(self, group: "Group") -> bool:
        if group not in self.groups:
            return False
        self.groups.remove(group)
        return True



def create_user(data: UserCreate, availabilities: list[AvailabilitySlot]) -> User:
    """Build a new User from caller-provided fields only."""
    sanitized_availabilities = []

    for slot in availabilities:
        if slot.time_range[0] < slot.time_range[1]:
            slot.time_range = roundTime(slot.time_range)
            sanitized_availabilities.append(slot)

    for day in DayOfWeek:
        if getIntervalIntersections(sanitized_availabilities, day)[0] > 0:
            raise InvalidArgument
    

    user = User.model_validate(data.model_dump())


    return user

