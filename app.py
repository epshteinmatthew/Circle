"""Circle FastAPI application."""
from fastapi import FastAPI, Depends
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter

from routers.auth import router as auth_router
from routers.availability import router as availability_router
from routers.event import router as event_router
from routers.group import router as group_router
from routers.user import router as user_router
from schema.database import init_db

#todo: deep event, deep group (do we need this?)
#deep event: get the event and all of the users for RSVP and the user for create
app = FastAPI()
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(group_router)
app.include_router(event_router)
app.include_router(availability_router)

init_db()


@app.get("/", dependencies=[ Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 5))))])
def index() -> str:
    return "Circle — try /demo for a schema example (data in circle.db)"
