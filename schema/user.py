from typing import TYPE_CHECKING

from pydantic.v1 import BaseModel
from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

from schema.links import UserEventRSVPLink, UserGroupLink, UserIncomingGroupLink

if TYPE_CHECKING:
    from schema.event import Event
    from schema.group import Group


class UserCreate(SQLModel):
    """Fields callers may provide when creating a user."""

    model_config = {"extra": "forbid"}

    name: str
    email: str
    availability: str


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



def create_user(data: UserCreate) -> User:
    """Build a new User from caller-provided fields only."""
    return User.model_validate(data.model_dump())


