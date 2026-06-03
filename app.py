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
from schema.group import GroupData


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
            events:Sequence[Event] = session.exec(select(Event).where(Event.created_by == user.id, Event.expires_at < datetime.now(timezone.utc))).all()
            session.commit()
            return events
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
            events:Sequence[Event] = session.exec(select(Event).where(col(Event.id).in_(user.rsvp_events), Event.expires_at < datetime.now(timezone.utc))).all()
            session.commit()
            return events
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
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

#todo: create for events and group

@app.post("/create_event/{group_id}")
def create_event_route(group_id, event_data:EventCreate) -> Event:
    try:
        with get_session() as session:
            group:Group|None = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            event = create_event(event_data)
            delete(Event).where(col(Event.expires_at) < datetime.now(timezone.utc))
            session.add(event)
            session.commit()
            return event
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")

#todo: update, get event by ID
#update event: update time, or name, or desc, or location
#this should probably send a notif to people that RSVP'd

@app.post("/create_group")
def create_group_route(group_data: GroupData) -> Group:
    try:
        with get_session() as session:
            creator:User|None = session.exec(Select(User).where(col(User.id) == group_data.created_by)).first()
            if creator is None:
                raise HTTPException(status_code=404, detail="no such user")
            invitees:Sequence[User] = session.exec(Select(User).where(col(User.id).in_(group_data.users))).all()
            group = create_group(GroupCreate(name=group_data.name, created_by=group_data.created_by), creator, users=invitees)
            session.add(group)
            session.commit()
            return group
    except:
        raise HTTPException(status_code=500, detail="Something went wrong")


#todo: expiry (how?)
#todo: delete expired events on create event?
#or maybe something else? maybe deep user?


if __name__ == "__main__":
    app.run(debug=True)
