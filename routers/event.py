"""Event routes."""
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from sqlmodel import SQLModel, select

from routers.auth import validate, validate_uid
from schema import Event, EventCreate, Group, User, create_event
from schema.database import get_session
from schema.event import EventData
from schema.interval_utils import ensure_utc, ranges_overlap
from schema.time_range import round_datetime

router = APIRouter(tags=["event"])


def event_has_ended(event: Event) -> bool:
    return ensure_utc(event.end_time) < datetime.now(timezone.utc)


def delete_ended_events(session) -> None:
    ended = [
        e for e in session.exec(select(Event)).all()
        if event_has_ended(e)
    ]
    for e in ended:
        session.delete(e)


class PollRsvpBody(SQLModel):
    poll_time: tuple[datetime, datetime]


@router.get("/get_event/{id_req}")
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


@router.get("/get_event_users/{id_req}")
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


@router.post("/create_event/{group_id}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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


@router.post("/update_event", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def update_event(event_data: EventData,polling:bool, authorization: Annotated[str | None, Header()] = None) -> Event:
    #note, do not allow poll to go from false to true.
    if not validate_uid(authorization, event_data.created_by):
        raise HTTPException(status_code=403, detail="not authorized")
    try:
        with (get_session() as session):
            event: Event | None = session.exec(select(Event).where(Event.id == event_data.id, Event.created_by==event_data.created_by)).first()
            if event is None:
                raise HTTPException(status_code=404, detail="no such event")
            new_start = ensure_utc(event_data.start_time)
            new_end = ensure_utc(event_data.end_time)
            if new_start >= new_end:
                raise HTTPException(status_code=400, detail="start_time must be before end_time")
            old_start = ensure_utc(event.start_time)
            old_end = ensure_utc(event.end_time)
            if len(event.poll_times) <= 0 and (old_start, old_end) != (new_start, new_end):
                event.rsvp_users = []
                event.event_user_amount = 1
            event.name = event_data.name
            if len(event.poll_times) > 0 and not polling:
                new_rsvp = [
                    user
                    for index, user in enumerate(event.rsvp_users)
                    if ranges_overlap(
                        event.poll_times[index + 1][0],
                        event.poll_times[index + 1][1],
                        new_start,
                        new_end,
                    )
                ]
                event.rsvp_users = new_rsvp
                event.event_user_amount = len(new_rsvp) + 1
                event.poll_times = []
                event.best_poll_time = (new_start, new_end)
            #could probably merge this with the if-clause above, but who cares
            event.address = event_data.address
            event.location_name = event_data.location_name
            if new_start.date() != old_start.date():
                event.rsvp_users = []
                event.event_user_amount = 1
            event.start_time = new_start
            event.end_time = new_end
            session.add(event)

            session.commit()
            session.refresh(event)
            return event

    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.post("/delete_event/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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


@router.post("/rsvp_to_event/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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


@router.post("/rsvp_to_event_poll/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def rsvp_to_event_poll(id_req: int, uid:int, body: PollRsvpBody, authorization: Annotated[str | None, Header()] = None) -> Event:
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
            poll_time = (
                round_datetime(body.poll_time[0]),
                round_datetime(body.poll_time[1]),
            )
            if poll_time[0] >= poll_time[1]:
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


@router.post("/remove_rsvp_to_event/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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
