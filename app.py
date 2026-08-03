"""Circle Flask application and schema usage example."""
import json
from collections.abc import Sequence
from datetime import datetime, timezone, time
import time as timeint
from typing import Annotated, TypedDict, Any

import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import Select
from sqlmodel import select, col, delete, or_, SQLModel

import setup
from auth import refresh_jwt_key, generate_refresh_token, validate_uid, validate
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
from schema.availabilities import getIntervalIntersections, DayOfWeek, getBestIntervalIntersection
from schema.database import get_session, init_db
from schema.event import EventData
from schema.group import GroupData
from schema.links import UserIncomingGroupLink
from schema.time_range import roundTime
from schema.user import AvailabilitySlot, DeepUser, GroupSummary, EventSummary
from setup import GOOGLE_CLIENT_ID
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter

def event_has_ended(event: Event, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    end = datetime.combine(event.day, event.time_range[1])
    return end < now.replace(tzinfo=None)

def delete_ended_events(session) -> None:
    now = datetime.now(timezone.utc).date()
    ended = [
        e for e in session.exec(select(Event)).all()
        if e.day < now
    ]
    for e in ended:
        session.delete(e)

def get_user_id_by_email(email:str) -> int | None:
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.email == email)).first()
            session.commit()
            return user.id
    except:
        return None

#todo: deep event, deep group (do we need this?)
#deep event: get the event and all of the users for RSVP and the user for create
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


@app.get("/", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))])
def index() -> str:
    return "Circle — try /demo for a schema example (data in circle.db)"



@app.post('/login', dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))])
def login(token:str):
    CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    try:
        # Specify the WEB_CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        if idinfo['aud'] == GOOGLE_CLIENT_ID and 'accounts.google.com' in idinfo['iss'] and idinfo['exp'] >= timeint.time():
            #plus one day
            user_id: int | None = get_user_id_by_email(idinfo['email'])
            if user_id is None:
                raise HTTPException(status_code=401, detail="user not found")
            encoded_jwt = jwt.encode({'cid': idinfo['aud'], 'exp': timeint.time() + 86400, 'uid': user_id}, setup.GOOGLE_CLIENT_SECRET, algorithm="HS256")
            refresh_token = generate_refresh_token(user_id)
            return {"jwt": encoded_jwt, "refresh" : refresh_token}
        else:
            raise HTTPException(status_code=403, detail="Not authorized")
    except HTTPException as e:
            raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))
@app.post("/refresh", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))])
async def refresh(authorization: Annotated[str | None, Header()] = None):
    try:
        if authorization is None:
            raise HTTPException(status_code=403, detail="Not authorized")
        res = refresh_jwt_key(authorization)
        if res == "not allowed":
            raise HTTPException(status_code=403, detail="Not authorized")
        return res
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.post("/logout", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))])
async def logout(authorization: Annotated[str | None, Header()] = None):
    try:
        if authorization is None:
            raise HTTPException(status_code=403, detail="Not authorized")
        refresh = authorization
        f = []
        with open("refresh.json", "r") as fp:
            f = json.load(fp)
        if refresh in f:
            f.remove(refresh)
        with open("refresh.json", "w") as fp:
            json.dump(fp = fp, obj= f)
        return "logged out"
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.post("/sign_up", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))])
def sign_up(user_data: UserCreate, availabilities: list[AvailabilitySlot], token:str):
    try:
        #todo fix? or do i need to?
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        if idinfo['aud'] == GOOGLE_CLIENT_ID and 'accounts.google.com' in idinfo['iss'] and idinfo[
            'exp'] >= timeint.time():
             # plus one day
            with get_session() as session:
                new_user:User = create_user(user_data, availabilities)
                same_name_and_email:User|None = session.exec(select(User).where(User.name == new_user.name, User.email == new_user.email)).first()
                if same_name_and_email:
                    raise HTTPException(status_code = 409, detail = "Duplicate name and email")
                session.add(new_user)
                session.commit()
                if new_user.id is None:
                    raise HTTPException(status_code=500, detail="gabagool")
                for slot in availabilities:
                    slot.user_id = new_user.id
                    session.add(slot)
                session.commit()
                encoded_jwt = jwt.encode(
                    {'cid': idinfo['aud'], 'exp': timeint.time() + 86400, 'uid': new_user.id},
                    setup.GOOGLE_CLIENT_SECRET, algorithm="HS256")
                refresh_token = generate_refresh_token(new_user.id)
                return {"jwt": encoded_jwt, "refresh": refresh_token, "user_id": new_user.id}
        raise HTTPException(status_code=401, detail="Not authorized")
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.post("/update_username/{id_req}/{new_name}")
async def update_username(id_req, new_name:str, authorization: Annotated[str | None, Header()] = None) -> User:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User | None = session.exec(select(User).where(User.id == id_req)).first()
            if user is not None:
                user.name = new_name
                session.add(user)
                session.commit()
                session.refresh(user)
                return user
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.get("/get_user_with_id/{id_req}")
async def get_user_with_id(id_req, authorization: Annotated[str | None, Header()] = None) -> DeepUser:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized") 
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User | None = session.exec(select(User).where(User.id == id_req)).first()
            if user is not None:
                created = session.exec(select(Event).where(Event.created_by == user.id)).all()
                return DeepUser(
                    id=user.id,
                    name=user.name,
                    email=user.email,
                    groups=[GroupSummary(id = group.id, name = group.name, created_by = group.created_by) for group in user.groups],
                    incoming_groups=[GroupSummary(id = group.id, name = group.name, created_by = group.created_by) for group in user.incoming_groups],
                    rsvp_events=[EventSummary(id = event.id, name= event.name, description = event.description, address = event.address, location_name = event.location_name, day = event.day, time_range = event.time_range, created_by = event.created_by, group_id = event.group_id, created_at = event.created_at, poll_times = event.poll_times, best_poll_time = event.best_poll_time, event_user_amount = event.event_user_amount) for event in user.rsvp_events],
                    created_events=[EventSummary(id = event.id, name= event.name, description = event.description, address = event.address, location_name = event.location_name, day = event.day, time_range = event.time_range, created_by = event.created_by, group_id = event.group_id, created_at = event.created_at, poll_times = event.poll_times, best_poll_time = event.best_poll_time, event_user_amount = event.event_user_amount) for event in created],
                )
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.get("/get_all_user_events/{id_req}")
async def get_all_user_events(id_req, authorization: Annotated[str | None, Header()] = None) -> Sequence[Event]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail=authorization)
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User|None = session.exec(select(User).where(User.id == id_req)).first()
            if not user:
                raise HTTPException(status_code = 400, detail = "Bad request")
            rsvp = list(user.rsvp_events)
            delete_ended_events(session)
            return [e for e in rsvp if not event_has_ended(e)]
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.get("/get_all_user_rsvp_events/{id_req}")
async def get_all_user_rsvp_events(id_req, authorization: Annotated[str | None, Header()] = None) -> Sequence[Event]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User|None = session.exec(select(User).where(User.id == id_req)).first()
            if not user:
                raise HTTPException(status_code=400, detail="Bad request")
            events: Sequence[Event] = session.exec(select(Event).where(Event.created_by == user.id)).all()
            events = [
                e for e in events
                if not event_has_ended(e)
            ]
            delete_ended_events(session)
            return events
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.get("/get_all_user_groups/{id_req}")
async def get_all_user_groups(id_req, authorization: Annotated[str | None, Header()] = None) -> Sequence[Group]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    if not id_req:
        raise HTTPException(status_code=400, detail="Bad request")
    try:
        with get_session() as session:
            user:User|None = session.exec(select(User).where(User.id == id_req)).first()
            if not user:
                raise HTTPException(status_code=400, detail="Bad request")
            return user.groups
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.get("/get_event/{id_req}")
async def get_event_by_id(id_req, authorization: Annotated[str | None, Header()] = None) -> Event:
    if not validate(authorization):
        raise HTTPException(status_code=403, detail="not authorized")
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
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.get("/get_event_users/{id_req}")
async def get_event_users(id_req, authorization: Annotated[str | None, Header()] = None) -> Sequence[User]:
    if not validate(authorization):
        raise HTTPException(status_code=403, detail="not authorized")
    if not id_req:
        raise HTTPException(status_code=400, detail="Bad request")
    try:
        with get_session() as session:
            event: Event|None = session.exec(select(Event).where(Event.id == id_req)).first()
            if not event:
                raise HTTPException(status_code=400, detail="Bad request")
            if not event_has_ended(event):
                raise HTTPException(status_code=400, detail="event not ended")  # only if that’s the intent
            users = list(event.rsvp_users)
            # include creator if needed:
            creator:User|None = session.exec(select(User).where(User.id == event.created_by)).first()
            if creator and creator not in users:
                users.append(creator)
            return users
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.post("/create_event/{group_id}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def create_event_route(group_id, polling:bool, event_data:EventCreate, authorization: Annotated[str | None, Header()] = None) -> Event:
    if not validate_uid(authorization, event_data.created_by):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            group:Group|None = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            event = create_event(event_data, polling)
            session.add(event)
            session.commit()
            session.refresh(event)
            return event
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))



@app.post("/update_event", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def update_event(event_data: EventData,polling:bool, authorization: Annotated[str | None, Header()] = None) -> Event:
    #todo: what to do with RSVP?
    #note, do not allow poll to go from false to true.
    if not validate_uid(authorization, event_data.created_by):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            event: Event | None = session.exec(select(Event).where(Event.id == event_data.id, Event.created_by==event_data.created_by)).first()
            if event is None:
                raise HTTPException(status_code=404, detail="no such event")
            event.name = event_data.name
            event.day = event_data.day
            event.time_range = event_data.time_range
            if len(event.poll_times) > 0 and not polling:
                event.poll_times = []
                event.time_range = event.best_poll_time
            session.add(event)

            session.commit()
            session.refresh(event)
            return event

    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.post("/delete_event/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def delete_event_route(id_req: int, uid:int,  authorization: Annotated[str | None, Header()] = None) -> bool:
    if not validate_uid(authorization, uid):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            event: Event | None = session.exec(select(Event).where(Event.id == id_req, Event.created_by == uid)).first()
            if event is None or event.created_by != uid:
                raise HTTPException(status_code=404, detail="no such event")
            session.delete(event)
            session.commit()
            return True

    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.post("/rsvp_to_event/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def rsvp_to_event(id_req: int, uid:int,  authorization: Annotated[str | None, Header()] = None) -> Event:
    if not validate_uid(authorization, uid):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            event: Event | None = session.exec(select(Event).where(Event.id == id_req)).first()
            if event is None:
                raise HTTPException(status_code=404, detail="no such event")
            group: Group | None = session.exec(select(Group).where(Group.id == event.group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            userList = [item for item in group.users if item.id == uid]
            if len(userList) == 0:
                raise HTTPException(status_code=404, detail="user not in group")
            if len(event.poll_times) > 0:
                raise HTTPException(status_code=404, detail="must have a poll time")
            event.add_rsvp(userList[0])
            session.add(event)
            session.commit()
            session.refresh(event)
            return event
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


class PollRsvpBody(SQLModel):
    poll_time: tuple[time, time]

@app.post("/rsvp_to_event_poll/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def rsvp_to_event_poll(id_req: int, uid:int, body: PollRsvpBody, authorization: Annotated[str | None, Header()] = None) -> Event:
    poll_time = (roundTime(body.poll_time[0]), roundTime(body.poll_time[1]))
    if not validate_uid(authorization, uid):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            event: Event | None = session.exec(select(Event).where(Event.id == id_req)).first()
            if event is None:
                raise HTTPException(status_code=404, detail="no such event")
            group: Group | None = session.exec(select(Group).where(Group.id == event.group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            userList = [item for item in group.users if item.id == uid]
            if len(userList) == 0:
                raise HTTPException(status_code=404, detail="user not in group")
            if len(event.poll_times) == 0:
                raise HTTPException(status_code=404, detail="not open to poll")
            poll_time = (roundTime(poll_time[0]), roundTime(poll_time[1]))
            if poll_time[0] > poll_time[1] or poll_time is None:
                raise HTTPException(status_code=400, detail="bad poll time")
            event.add_poll_time(userList[0], poll_time)
            session.add(event)
            session.commit()
            session.refresh(event)
            return event
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))



@app.post("/remove_rsvp_to_event/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def remove_rsvp_to_event(id_req: int, uid:int,  authorization: Annotated[str | None, Header()] = None) -> Event:
    if not validate_uid(authorization, uid):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            event: Event | None = session.exec(select(Event).where(Event.id == id_req)).first()
            if event is None:
                raise HTTPException(status_code=404, detail="no such event")
            group: Group | None = session.exec(select(Group).where(Group.id == event.group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            userList = [item for item in group.users if item.id == uid and item in event.rsvp_users]
            if len(userList) == 0:
                raise HTTPException(status_code=404, detail="user not in group or not RSVP'd")
            if len(event.poll_times) > 0:
                event.remove_poll_time(userList[0])
            else:
                event.remove_rsvp(userList[0])
            session.add(event)
            session.commit()
            session.refresh(event)
            return event
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))



@app.post("/create_group", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def create_group_route(group_data: GroupData, authorization: Annotated[str | None, Header()] = None) -> Group:
    if not validate_uid(authorization, group_data.created_by):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            creator:User|None = session.exec(select(User).where(col(User.id) == group_data.created_by)).first()
            if creator is None:
                raise HTTPException(status_code=404, detail="no such user")
            invitees:Sequence[User] = session.exec(select(User).where(col(User.id).in_(group_data.users))).all()
            group = create_group(GroupCreate(name=group_data.name, created_by=group_data.created_by), creator, users=invitees)
            session.add(group)
            session.commit()
            session.refresh(group)
            return group
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.post("/add_to_group/{added_user_email}/{group_id}/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def add_to_group(id_req:int, group_id: int, added_user_email: str, authorization: Annotated[str | None, Header()] = None) -> Group:
    if added_user_email is None or not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:

            group:Group|None = session.exec(select(Group).where(Group.id == group_id)).first()
            added_user: User|None = session.exec(select(User).where(User.email == added_user_email)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if added_user is None:
                raise HTTPException(status_code=404, detail="no such user")
            user_id_list = [user.id for user in group.users]
            if id_req not in user_id_list or added_user.id in user_id_list or added_user.id in [user.id for user in group.user_requests]:
                raise HTTPException(status_code=400, detail="wrong users")
            if len(group.users) + len(group.user_requests) < 20:
                group.user_requests.append(added_user)
                session.commit()
                session.refresh(group)
                return group
            else:
                raise HTTPException(status_code=400, detail="too many users")
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.post("/respond_user_request/{id_req}/{response}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def respond_user_request(id_req: int, uid: int, response: bool, authorization: Annotated[str | None, Header()] = None):
    if not validate_uid(authorization, uid):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            group: Group | None = session.exec(select(Group).where(Group.id == id_req)).first()
            added_user: User | None = session.exec(select(User).where(User.id == uid)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if added_user is None:
                raise HTTPException(status_code=404, detail="no such user")
            if uid not in [user.id for user in group.user_requests]:
                raise HTTPException(status_code=400, detail="wrong users")
            if response:
                group.users.append(added_user)
                group.user_requests.remove(added_user)
            if not response:
                group.user_requests.remove(added_user)
            session.commit()
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.post("/leave_group/{id_req}/{group_id}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def leave_group(id_req: int, group_id: int, authorization: Annotated[str | None, Header()] = None):
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            group:Group|None = session.exec(select(Group).where(Group.id == group_id)).first()
            user: User|None = session.exec(select(User).where(User.id == id_req)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if user is None:
                raise HTTPException(status_code=404, detail="no such user")
            if id_req not in [user.id for user in group.users]:
                raise HTTPException(status_code=400, detail="user not in group")
            events: Sequence[Event] | None = session.exec(select(Event).where(or_(Event.group == group))).all()
            if events is not None:
                events = [event for event in events if event.created_by == user.id or user.id in event.rsvp_users]
            #this is garbage
            if events is not None:
                for event in events:
                    session.delete(event)
            group.users.remove(user)
            session.commit()
            return group
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.get("/get_group_users/{group_id}/{id_req}" , dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def get_group_users(id_req: int, group_id: int, authorization:Annotated[str|None, Header()] = None) -> Sequence[User]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            group: Group | None = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if id_req not in [user.id for user in group.users]:
                raise HTTPException(status_code=404, detail="User not in group")
            return group.users
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))



@app.get("/get_group_events/{group_id}/{id_req}" , dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def get_group_events(id_req: int, group_id: int, authorization:Annotated[str|None, Header()] = None) -> Sequence[Event]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            group: Group | None = session.exec(select(Group).where(Group.id == group_id)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            events: Sequence[Event] | None = session.exec(select(Event).where(Event.group_id == group_id)).all()
            if events is None:
                raise HTTPException(status_code=404, detail="no such group")
            if id_req not in [user.id for user in group.users]:
                raise HTTPException(status_code=404, detail="User not in group")
            return [e for e in events if not event_has_ended(e)]
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.get("/get_user_availabilities/{id_req}",  dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def get_user_availabilities(id_req: int, authorization: Annotated[str | None, Header()] = None) -> Sequence[AvailabilitySlot]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            slots: Sequence[AvailabilitySlot]|None = session.exec(select(AvailabilitySlot).where(AvailabilitySlot.user_id == id_req)).all()
            if slots is None:
                raise HTTPException(status_code=404, detail="no such slots")
            return slots
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.get("/get_group_availabilities/{id_req}/{group_id}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def get_group_availabilities(id_req: int, group_id:int, authorization: Annotated[str | None, Header()] = None) -> dict[str, list[int]]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            group: Group | None = session.exec(select(Group).where(Group.id == group_id)).first()
            user: User | None = session.exec(select(User).where(User.id == id_req)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if user is None:
                raise HTTPException(status_code=404, detail="no such user")
            if user not in group.users:
                raise HTTPException(status_code=400, detail="user not in group")

            slots: Sequence[AvailabilitySlot] | None = session.exec(select(AvailabilitySlot).where(col(AvailabilitySlot.user_id).in_([u.id for u in group.users]))).all()
            if slots is None:
                raise HTTPException(status_code=404, detail="no such slots")
            intersections = {}
            for day in DayOfWeek:
                selected_slots = getIntervalIntersections(list(slots), day)
                intersections[day.name] = selected_slots
            return intersections
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.get("/get_group_best_availabilities/{id_req}/{group_id}",
         dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def get_best_group_availability(id_req: int, group_id: int, authorization: Annotated[str | None, Header()] = None) -> list[AvailabilitySlot]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            group: Group | None = session.exec(select(Group).where(Group.id == group_id)).first()
            user: User | None = session.exec(select(User).where(User.id == id_req)).first()
            if group is None:
                raise HTTPException(status_code=404, detail="no such group")
            if user is None:
                raise HTTPException(status_code=404, detail="no such user")
            if user not in group.users:
                raise HTTPException(status_code=400, detail="user not in group")

            slots: Sequence[AvailabilitySlot] | None = session.exec(
                select(AvailabilitySlot).where(col(AvailabilitySlot.user_id).in_([u.id for u in group.users]))).all()
            if slots is None:
                raise HTTPException(status_code=404, detail="no such slots")
            intersections = []
            for day in DayOfWeek:
                selected_slots = getBestIntervalIntersection(list(slots), day)
                found = False
                #using this to get around the fact that i cant use break statement
                done = False
                start_time = time()
                end_time = time()
                for indx, slot in enumerate(selected_slots[1]):
                    if slot == selected_slots[0] and not found and not done:
                        found = True
                        start_time = time(indx // 2, (indx % 2) * 30)
                    if slot != selected_slots[0] and found and not done:
                        end_time = time(indx // 2, (indx % 2) * 30)
                        done = True
                intersections.append(AvailabilitySlot(user_id=1, day=day, time_range=(start_time, end_time)))
            return intersections
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))

@app.post("/add_availability/{id_req}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def add_availability(id_req:int, aSlot: AvailabilitySlot, authorization: Annotated[str | None, Header()] = None) -> list[AvailabilitySlot]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:

            availabilities: list[AvailabilitySlot] = list(session.exec(select(AvailabilitySlot).where(AvailabilitySlot.user_id == id_req)).all())
            if aSlot.time_range[0] > aSlot.time_range[1]:
                raise HTTPException(status_code=400, detail="overlapping time for slot")
            sanitized_availabilities:list[AvailabilitySlot] = [aSlot]
            for slot in availabilities:
                if slot.time_range[0] < slot.time_range[1]:
                    slot.time_range = (
                        roundTime(slot.time_range[0]),
                        roundTime(slot.time_range[1]),
                    )
                    sanitized_availabilities.append(slot)

            for day in DayOfWeek:
                if getIntervalIntersections(sanitized_availabilities, day)[0] > 0:
                    raise HTTPException(status_code=400, detail="overlapping availabilities")
            session.add(aSlot)
            session.commit()
            return sanitized_availabilities
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.post("/update_availability/{id_req}/{slot_id}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def update_availability(id_req: int,slot_id:int, aSlot: AvailabilitySlot, authorization: Annotated[str | None, Header()] = None) -> list[AvailabilitySlot]:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            old_slot: AvailabilitySlot|None = session.exec(select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id, AvailabilitySlot.user_id == id_req)).first()
            if old_slot is None:
                raise HTTPException(status_code=400, detail="No such slot")
            aSlot.id = old_slot.id
            availabilities: list[AvailabilitySlot] = list(
                session.exec(select(AvailabilitySlot).where(AvailabilitySlot.user_id == id_req, AvailabilitySlot.id != slot_id)).all())
            if aSlot.time_range[0] > aSlot.time_range[1]:
                raise HTTPException(status_code=400, detail="overlapping time for slot")
            sanitized_availabilities: list[AvailabilitySlot] = [aSlot]
            for slot in availabilities:
                if slot.time_range[0] < slot.time_range[1]:
                    slot.time_range = (
                        roundTime(slot.time_range[0]),
                        roundTime(slot.time_range[1]),
                    )
                    sanitized_availabilities.append(slot)

            for day in DayOfWeek:
                if getIntervalIntersections(sanitized_availabilities, day)[0] > 0:
                    raise HTTPException(status_code=400, detail="overlapping availabilities")
            old_slot = aSlot
            session.add(old_slot)
            session.commit()
            return sanitized_availabilities
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@app.post("/delete_availability/{id_req}/{slot_id}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def delete_availability(id_req: int, slot_id: int, authorization: Annotated[str | None, Header()] = None) ->bool:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with get_session() as session:
            old_slot: AvailabilitySlot | None = session.exec(select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id,AvailabilitySlot.user_id == id_req)).first()
            if old_slot is None:
                raise HTTPException(status_code=400, detail="No such slot")
            session.delete(old_slot)
            session.commit()
            return True
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))









