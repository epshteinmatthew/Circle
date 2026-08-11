"""Group routes."""
from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from sqlmodel import col, or_, select

from routers.auth import validate_uid
from routers.event import event_has_ended
from schema import Event, Group, GroupCreate, User, create_group
from schema.database import get_session
from schema.group import GroupData
from schema.links import UserIncomingGroupLink


class Response(Enum):
    YES = "YES"
    NO = "NO"
    BLOCK = "BLOCK"
router = APIRouter(tags=["group"])


@router.post("/create_group", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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


@router.post("/add_to_group/{added_user_email}/{group_id}/{id_req}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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
            if id_req in [user.id for user in added_user.blocked_users]:
                raise HTTPException(status_code=404, detail="user blocked")
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


@router.post("/respond_user_request/{id_req}/{response}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
async def respond_user_request(id_req: int, uid: int, response: Enum, authorization: Annotated[str | None, Header()] = None):
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
            if response == Response.YES:
                group.add_user(added_user)
            elif response == Response.NO:
                group.user_requests.remove(added_user)
            elif response == Response.BLOCK:
                link = session.get(UserIncomingGroupLink, (uid, id_req))
                if link is None:
                    raise HTTPException(status_code=400, detail="wrong users")
                blocked_user:User | None = session.exec(select(User).where(User.id == link.sender_id)).first()
                if blocked_user is None:
                    raise HTTPException(status_code=400, detail="wrong users")
                added_user.add_block(blocked_user)
                group.user_requests.remove(added_user)
            session.commit()
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.post("/leave_group/{id_req}/{group_id}", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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
                events = [event for event in events if event.created_by == user.id]
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


@router.get("/get_group_users/{group_id}/{id_req}" , dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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


@router.get("/get_group_events/{group_id}/{id_req}" , dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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
