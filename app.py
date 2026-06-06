"""Circle Flask application and schema usage example."""
import json
from collections.abc import Sequence
from datetime import date, time, datetime, timezone

from fastapi import FastAPI, HTTPException
from flask import jsonify
from sqlalchemy import Select
from sqlmodel import select, col, delete

from schema import (
    Event,
    EventCreate,
    Group,
    GroupCreate,
    User,
    UserCreate,
    create_event,
    create_group,
    create_user,
)
from schema.database import get_session, init_db
from schema.event import EventData
from schema.group import GroupData
from schema.links import UserIncomingGroupLink


#todo: validation and refresh tokens

def get_user_with_email_and_name(name:str, email:str) -> User | None:
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.name == name and User.email == email)).first()
            session.commit()
            return user
    except:
        return None

def delete_event(id:int) -> bool:
    try:
        with get_session() as session:
            event = session.exec(select(Event).where(Event.id == id))
            session.delete(event)
            event = session.exec(select(Event).where(Event.id==id))
            return event is None
    except:
        return False

#todo: deep user, deep event, deep group
#deep user: get the user and all of their events and groups
#deep event: get the event and all of the users for RSVP and the user for create
#deep group: idk yet

app = FastAPI()

init_db()
'''
# 1. Define the input data using the EventCreate schema
event_in = EventCreate(
    name="Team Sync & Board Game Night",
    description="Monthly alignment meeting followed by Catan.",
    day=date(2026, 6, 15),
    time_range=(time(17, 0), time(20, 30)),  # 5:00 PM to 8:30 PM
    created_by=42,                            # ID of the creating User
    group_id=7                                # ID of the target Group
)

# 2. Instantiate the Event model using your function
new_event = create_event(event_in)

with get_session() as session:
    session.add(new_event)
    session.commit()
'''


@app.get("/")
def index() -> str:
    return "Circle — try /demo for a schema example (data in circle.db)"

#todo: google path
#this will do login and then split into either a sign up flow or give you your user
#to get your user you need name and email OR id
#these will always be the ones tied to the google account for simplicity's sake

#todo: augment this to some kind of sign-up flow
@app.post("/create_user")
def create_user_route(user_data: UserCreate) -> User:
    try:
        with get_session() as session:
            new_user:User = create_user(user_data)
            same_name_and_email:User|None = session.exec(select(User).where(User.name == new_user.name, User.email == new_user.email)).first()
            if same_name_and_email:
                raise HTTPException(status_code = 409, detail = "Duplicate name and email")
            session.add(new_user)
            session.commit()
            return new_user
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

@app.get("/get_user_with_id/{id_req}")
def get_user_with_id(id_req) -> User:
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User | None = session.exec(select(User).where(User.id == id_req)).first()
            session.commit()
            if user is not None:
                return user
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")


@app.get("/get_all_user_events/{id_req}")
def get_all_user_events(id_req) -> Sequence[Event]:
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User|None = session.exec(select(User).where(User.id == id_req)).first()
            if not user:
                raise HTTPException(status_code = 400, detail = "Bad request")
            events:Sequence[Event] = session.exec(select(Event).where(Event.created_by == user.id, datetime.combine(Event.day, Event.time_range[1]) < datetime.now(timezone.utc))).all()
            session.commit()
            return events
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")


@app.get("/get_all_user_rsvp_events/{id_req}")
def get_all_user_rsvp_events(id_req) -> Sequence[Event]:
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User|None = session.exec(select(User).where(User.id == id_req)).first()
            if not user:
                raise HTTPException(status_code=400, detail="Bad request")
            events:Sequence[Event] = session.exec(select(Event).where(col(Event.id).in_(user.rsvp_events), datetime.combine(Event.day, Event.time_range[1]) < datetime.now(timezone.utc))).all()
            session.commit()
            return events
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

@app.get("/get_all_user_groups/{id_req}")
def get_all_user_groups(id_req) -> Sequence[Group]:
    if not id_req:
        raise HTTPException(status_code=400, detail="Bad request")
    try:
        with get_session() as session:
            user:User|None = session.exec(select(User).where(User.id == id_req)).first()
            if not user:
                raise HTTPException(status_code=400, detail="Bad request")
            groups:Sequence[Group] = session.exec(select(Group).where(col(Group.id).in_(user.groups))).all()
            session.commit()
            return groups
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

@app.get("/get_event/{id_req}")
def get_event_by_id(id_req):
    if not id_req:
        raise HTTPException(status_code=400, detail="bad request")
    try:
        with get_session() as session:
            event: Event | None = session.exec(select(Event).where(Event.id == id_req)).first()
            if event is None:
                raise HTTPException(status_code=404, detail="no such event")
            return event

    except HTTPException as e:
       raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

@app.post("/create_event/{group_id}")
def create_event_route(group_id, event_data:EventCreate) -> Event:
    try:
        with get_session() as session:
            group:Group|None = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            event = create_event(event_data)
            delete(Event).where(col(datetime.combine(Event.day, Event.time_range[1])) < datetime.now(timezone.utc))
            session.add(event)
            session.commit()
            return event
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")


@app.post("/update_event")
def update_event(event_data: EventData) -> Event:
    #todo: what to do with RSVP?
    try:
        with get_session() as session:
            event: Event | None = session.exec(select(Event).where(Event.id == event_data.id)).first()
            if event is None:
                raise HTTPException(status_code=404, detail="no such event")
            event.name = event_data.name
            event.day = event_data.day
            event.time_range = event_data.time_range
            session.add(event)
            delete(Event).where(col(datetime.combine(Event.day, Event.time_range[1])) < datetime.now(timezone.utc))
            return event

    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")


#todo: delete event


@app.post("/create_group")
def create_group_route(group_data: GroupData) -> Group:
    try:
        with get_session() as session:
            creator:User|None = session.exec(select(User).where(col(User.id) == group_data.created_by)).first()
            if creator is None:
                raise HTTPException(status_code=404, detail="no such user")
            invitees:Sequence[User] = session.exec(select(User).where(col(User.id).in_(group_data.users))).all()
            group = create_group(GroupCreate(name=group_data.name, created_by=group_data.created_by), creator, users=invitees)
            session.add(group)
            session.commit()
            return group
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

@app.post("/add_to_group/{id_req}")
def add_to_group(link: UserIncomingGroupLink, id_req: int) -> Group:
    try:
        with get_session() as session:
            group:Group|None = session.exec(select(Group).where(Group.id == link.group_id)).first()
            added_user: User|None = session.exec(select(User).where(User.id == link.user_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if added_user is None:
                raise HTTPException(status_code=404, detail="no such user")
            if id_req not in group.users or link.user_id in group.users or link.user_id in group.user_requests:
                raise HTTPException(status_code=400, detail="wrong users")
            group.user_requests.append(added_user)
            session.commit()
            return group
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

@app.post("/leave_group/{id_req}/{group_id}")
def leave_group(id_req: int, group_id: int):
    #todo: require auth verify for this and all other similar stuff
    try:
        with get_session() as session:
            group:Group|None = session.exec(select(Group).where(Group.id == group_id)).first()
            user: User|None = session.exec(select(User).where(User.id == id_req)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if user is None:
                raise HTTPException(status_code=404, detail="no such user")
            if id_req not in group.users:
                raise HTTPException(status_code=400, detail="user not in group")
            group.users.remove(user)
            session.commit()
            return group
    except HTTPException as e:
        raise e
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

#todo: expiry (how?)


