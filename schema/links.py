from sqlmodel import Field, SQLModel


class UserEventRSVPLink(SQLModel, table=True):
    """Association table: user RSVP'd to event."""

    user_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    event_id: int | None = Field(default=None, foreign_key="event.id", primary_key=True)


class UserGroupLink(SQLModel, table=True):
    """Association table: user in group."""

    user_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    group_id: int | None = Field(default=None, foreign_key="group.id", primary_key=True)



class UserIncomingGroupLink(SQLModel, table=True):
    """Association table: user in group."""

    user_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    group_id: int | None = Field(default=None, foreign_key="group.id", primary_key=True)

