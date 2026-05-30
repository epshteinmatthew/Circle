from sqlmodel import Session, SQLModel, create_engine

# Import models so SQLModel.metadata registers all tables.
from schema.event import Event  # noqa: F401
from schema.group import Group  # noqa: F401
from schema.links import UserEventRSVPLink, UserGroupLink  # noqa: F401
from schema.user import User  # noqa: F401

DATABASE_URL = "sqlite:///circle.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
