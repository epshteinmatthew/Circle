"""User routes."""
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from sqlmodel import select

from routers.auth import validate_uid
from routers.event import delete_ended_events, event_has_ended
from schema import Event, Group, User
from schema.database import get_session
from schema.user import DeepUser, GroupSummary, EventSummary

router = APIRouter(tags=["user"])


@router.post("/update_username/{id_req}/{new_name}")
async def update_username(id_req, new_name:str, authorization: Annotated[str | None, Header()] = None) -> User:
    if not validate_uid(authorization, id_req):
        raise HTTPException(status_code=403, detail="not authorized")
    if not id_req:
        raise HTTPException(status_code = 400, detail = "Bad request")
    try:
        with get_session() as session:
            user:User | None = session.exec(select(User).where(User.id == id_req)).first()
            same_name: User | None = session.exec(select(User).where(User.name == new_name)).first()
            if same_name:
                raise HTTPException(status_code=409, detail="Duplicate name")
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


@router.get("/get_user_with_id/{id_req}")
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
                    rsvp_events=[EventSummary(id = event.id, name= event.name, description = event.description, address = event.address, location_name = event.location_name, start_time = event.start_time, end_time = event.end_time, created_by = event.created_by, group_id = event.group_id, created_at = event.created_at, poll_times = event.poll_times, best_poll_time = event.best_poll_time, event_user_amount = event.event_user_amount) for event in user.rsvp_events],
                    created_events=[EventSummary(id = event.id, name= event.name, description = event.description, address = event.address, location_name = event.location_name, start_time = event.start_time, end_time = event.end_time, created_by = event.created_by, group_id = event.group_id, created_at = event.created_at, poll_times = event.poll_times, best_poll_time = event.best_poll_time, event_user_amount = event.event_user_amount) for event in created],
                )
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.get("/get_all_user_events/{id_req}")
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


@router.get("/get_all_user_rsvp_events/{id_req}")
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


@router.get("/get_all_user_groups/{id_req}")
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
