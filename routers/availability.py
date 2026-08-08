"""Availability routes."""
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from sqlmodel import col, select

from routers.auth import validate_uid
from schema import Group, User
from schema.availabilities import AvailabilitySlot
from schema.database import get_session
from schema.interval_utils import (
    getBestIntervalIntersection,
    getIntervalIntersections,
    ranges_overlap,
)
from schema.time_range import roundTime

router = APIRouter(tags=["availability"])


@router.get("/get_user_availabilities/{id_req}",  dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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


@router.get("/get_group_availabilities/{id_req}/{group_id}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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
            return {"all": getIntervalIntersections(list(slots))}
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.get("/get_group_best_availabilities/{id_req}/{group_id}",
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
            result = getBestIntervalIntersection(list(slots), datetime.now(timezone.utc))
            if result is None:
                return []
            return result[1]
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.post("/add_availability/{id_req}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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

            for i, slot_a in enumerate(sanitized_availabilities):
                for slot_b in sanitized_availabilities[i + 1:]:
                    if ranges_overlap(
                        slot_a.time_range[0],
                        slot_a.time_range[1],
                        slot_b.time_range[0],
                        slot_b.time_range[1],
                    ):
                        raise HTTPException(status_code=400, detail="overlapping availabilities")
            session.add(aSlot)
            session.commit()
            return sanitized_availabilities
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.post("/update_availability/{id_req}/{slot_id}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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

            for i, slot_a in enumerate(sanitized_availabilities):
                for slot_b in sanitized_availabilities[i + 1:]:
                    if ranges_overlap(
                        slot_a.time_range[0],
                        slot_a.time_range[1],
                        slot_b.time_range[0],
                        slot_b.time_range[1],
                    ):
                        raise HTTPException(status_code=400, detail="overlapping availabilities")
            old_slot = aSlot
            session.add(old_slot)
            session.commit()
            return sanitized_availabilities
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.post("/delete_availability/{id_req}/{slot_id}", dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.SECOND * 2))))])
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
