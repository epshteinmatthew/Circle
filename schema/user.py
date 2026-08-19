from datetime import datetime
from typing import TYPE_CHECKING

from google.api_core.exceptions import InvalidArgument
from sqlmodel import Field, Relationship, SQLModel

from schema.availabilities import AvailabilitySlot
from schema.interval_utils import ranges_overlap
from schema.links import (
    UserBlockLink,
    UserEventRSVPLink,
    UserGroupLink,
    UserIncomingGroupLink,
)
from schema.time_range import roundTime, round_datetime

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
        link_model=UserIncomingGroupLink,
        sa_relationship_kwargs={
            "primaryjoin": "User.id == UserIncomingGroupLink.user_id",
            "secondaryjoin": "Group.id == UserIncomingGroupLink.group_id",
            "foreign_keys": "[UserIncomingGroupLink.user_id, UserIncomingGroupLink.group_id]",
        },
    )

    blocked_users: list["User"] = Relationship(
        link_model=UserBlockLink,
        sa_relationship_kwargs={
            "primaryjoin": "User.id==UserBlockLink.blocker_id",
            "secondaryjoin": "User.id==UserBlockLink.blocked_id",
        },
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

    def add_block(self, user: "User") -> bool:
        if user is self or user in self.blocked_users:
            return False
        self.blocked_users.append(user)
        return True

    def remove_block(self, user: "User") -> bool:
        if user not in self.blocked_users:
            return False
        self.blocked_users.remove(user)
        return True




def create_user(data: UserCreate, availabilities: list[AvailabilitySlot]) -> User:
    """Build a new User from caller-provided fields only."""
    sanitized_availabilities = []

    for slot in availabilities:
        if slot.time_range[0] < slot.time_range[1]:
            slot.time_range = (
                round_datetime(slot.time_range[0]),
                round_datetime(slot.time_range[1]),
            )
            sanitized_availabilities.append(slot)

    for i, slot_a in enumerate(sanitized_availabilities):
        for slot_b in sanitized_availabilities[i + 1 :]:
            if ranges_overlap(
                slot_a.time_range[0],
                slot_a.time_range[1],
                slot_b.time_range[0],
                slot_b.time_range[1],
            ):
                raise InvalidArgument

    user = User.model_validate(data.model_dump())


    return user

class GroupSummary(SQLModel):
    id: int
    name: str
    created_by: int

class UserSummary(SQLModel):
    id: int
    name: str

class EventSummary(SQLModel):
    id: int
    name: str
    description: str
    address: str
    location_name: str
    start_time: datetime
    end_time: datetime
    created_by: int
    group_id: int
    created_at: datetime
    poll_times: list[tuple[datetime, datetime]] = Field(default_factory=list)
    best_poll_time: tuple[datetime, datetime] | None = None
    event_user_amount: int

class DeepUser(SQLModel):
    id: int
    name: str
    email: str
    groups: list[GroupSummary] = Field(default_factory=list)
    incoming_groups: list[GroupSummary] = Field(default_factory=list)
    created_events: list[EventSummary] = Field(default_factory=list)
    rsvp_events: list[EventSummary] = Field(default_factory=list)
    blocked_users: list[UserSummary] = Field(default_factory=list)

