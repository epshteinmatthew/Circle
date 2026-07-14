#class for events that have expired with a lot of RSVP's
#store name, # of RSVP's
#also have prediction stuff here
from datetime import datetime, time

from click import group
from google.api_core.exceptions import InvalidArgument
from sqlalchemy.orm import Relationship
from sqlmodel import SQLModel, Field, select

from schema import Group, Event
from schema.database import get_session


class PastEventCreate(SQLModel):
    """Fields callers may provide when creating a user."""

    model_config = {"extra": "forbid"}

    name: str
    rsvp_amount: int

    group_id: int



class PastEvent(PastEventCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id")
    group: "Group" = Relationship()


#todo: later
def search_past_events(name:str):
    with get_session() as session:
        events = session.exec(select(PastEvent)).all()


def create_past_event(event: Event) -> PastEvent:
    if event.time_range[1] > time.fromisoformat(datetime.now().isoformat()) and event.day.day >= datetime.now().day:
        raise InvalidArgument

    #here is where we search

    data = PastEventCreate(
        name = event.name,
        rsvp_amount =len(event.rsvp_users),
        group_id = event.group_id
    )

    """Build a new Event from caller-provided fields only."""
    return PastEvent.model_validate(data.model_dump())
