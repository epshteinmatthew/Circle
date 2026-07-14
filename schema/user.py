from datetime import time
from typing import TYPE_CHECKING

from google.api_core.exceptions import InvalidArgument
from pydantic.v1 import BaseModel
from sqlalchemy import Column, JSON, Enum
from sqlmodel import Field, Relationship, SQLModel

from schema.links import UserEventRSVPLink, UserGroupLink, UserIncomingGroupLink
from schema.time_range import roundTime, DayOfWeek, TimeRangeType

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

    availabilities: list["AvailabilitySlot"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
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

class AvailabilitySlot(SQLModel, table=True):
    __tablename__ = "availability_slots"

    id: int = Field(default=None, primary_key=True)

    # Foreign key referencing the users table
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")

    # Store the day as an Enum
    day: DayOfWeek = Field(sa_column=Column(Enum(DayOfWeek), nullable=False))

    # Use your original custom TimeRangeType here via sa_column!
    time_range: tuple[time, time] = Field(
        sa_column=Column(TimeRangeType, nullable=False)
    )


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



