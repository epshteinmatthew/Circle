"""Auth helpers and routes (login, refresh, logout, sign_up)."""
import json
import time
import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from google.auth.transport import requests
from google.oauth2 import id_token
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter
from sqlmodel import select

import setup
from schema import User, UserCreate, create_user
from schema.availabilities import AvailabilitySlot
from schema.database import get_session
from setup import GOOGLE_CLIENT_ID

router = APIRouter(tags=["auth"])


def generate_refresh_token(user_id: int) -> str:
    key = str(uuid.uuid4()).replace("-", "")[:32]
    keys = {}
    with open("refresh.json", "r") as f:
        keys = json.loads(f.read())
    keys[key] = user_id
    with open("refresh.json", "w") as f:
        f.write(json.dumps(keys))
    return key


def refresh_jwt_key(refresh: str) -> str:
    with open("refresh.json", "r") as fp:
        f = json.load(fp)
        if refresh in f.keys():
            uid = f[refresh]
            encoded_jwt = jwt.encode(
                {"cid": setup.GOOGLE_CLIENT_ID, "exp": time.time() + 8640, "uid": uid},
                setup.GOOGLE_CLIENT_SECRET,
                algorithm="HS256",
            )
            return encoded_jwt
        return "not allowed"


def validate(encoded):
    try:
        decoded = jwt.decode(encoded, setup.GOOGLE_CLIENT_SECRET, algorithms=["HS256"])
        if decoded["exp"] >= time.time() and decoded["cid"] == setup.GOOGLE_CLIENT_ID:
            return True
        else:
            return False
    except:
        return False


def validate_uid(encoded, uid: int):
    try:
        decoded = jwt.decode(encoded, setup.GOOGLE_CLIENT_SECRET, algorithms=["HS256"])
        if (
            decoded["exp"] >= time.time()
            and decoded["cid"] == setup.GOOGLE_CLIENT_ID
            and int(decoded["uid"]) == int(uid)
        ):
            return True
        else:
            return False
    except:
        return False


def get_user_id_by_email(email: str) -> int | None:
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.email == email)).first()
            session.commit()
            return user.id
    except:
        return None


@router.post(
    "/login",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))],
)
def login(token: str):
    try:
        # Specify the WEB_CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        if (
            idinfo["aud"] == GOOGLE_CLIENT_ID
            and "accounts.google.com" in idinfo["iss"]
            and idinfo["exp"] >= time.time()
        ):
            # plus one day
            user_id: int | None = get_user_id_by_email(idinfo["email"])
            if user_id is None:
                raise HTTPException(status_code=401, detail="user not found")
            encoded_jwt = jwt.encode(
                {"cid": idinfo["aud"], "exp": time.time() + 86400, "uid": user_id},
                setup.GOOGLE_CLIENT_SECRET,
                algorithm="HS256",
            )
            refresh_token = generate_refresh_token(user_id)
            return {"jwt": encoded_jwt, "refresh": refresh_token}
        else:
            raise HTTPException(status_code=403, detail="Not authorized")
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.post(
    "/refresh",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))],
)
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


@router.post(
    "/logout",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))],
)
async def logout(authorization: Annotated[str | None, Header()] = None):
    try:
        if authorization is None:
            raise HTTPException(status_code=403, detail="Not authorized")
        refresh = authorization
        f = {}
        with open("refresh.json", "r") as fp:
            f = json.load(fp)
        if refresh in f.keys():
            f.pop(refresh)
        with open("refresh.json", "w") as fp:
            json.dump(fp=fp, obj=f)
        return "logged out"
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))


@router.post(
    "/sign_up",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))],
)
def sign_up(user_data: UserCreate, availabilities: list[AvailabilitySlot], token: str):
    try:
        # todo fix? or do i need to?
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        if (
            idinfo["aud"] == GOOGLE_CLIENT_ID
            and "accounts.google.com" in idinfo["iss"]
            and idinfo["exp"] >= time.time()
        ):
            # plus one day
            with get_session() as session:
                user_id: int | None = get_user_id_by_email(idinfo["email"])
                if user_id is not None:
                    raise HTTPException(
                        status_code=409, detail="Log in, your account already exists"
                    )
                new_user: User = create_user(user_data, availabilities)
                same_name: User | None = session.exec(
                    select(User).where(User.name == new_user.name)
                ).first()
                if same_name:
                    raise HTTPException(status_code=409, detail="Duplicate name")
                session.add(new_user)
                session.commit()
                if new_user.id is None:
                    raise HTTPException(status_code=500, detail="Issue creating user")
                for slot in availabilities:
                    slot.user_id = new_user.id
                    session.add(slot)
                session.commit()
                encoded_jwt = jwt.encode(
                    {
                        "cid": idinfo["aud"],
                        "exp": time.time() + 86400,
                        "uid": new_user.id,
                    },
                    setup.GOOGLE_CLIENT_SECRET,
                    algorithm="HS256",
                )
                refresh_token = generate_refresh_token(new_user.id)
                return {
                    "jwt": encoded_jwt,
                    "refresh": refresh_token,
                    "user_id": new_user.id,
                }
        raise HTTPException(status_code=401, detail="Not authorized")
    except HTTPException as e:
        raise e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=repr(ex))
