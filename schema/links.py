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
    """Association table: pending group invite/request.

    user_id: invitee
    sender_id: user who sent the request
    """

    user_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    group_id: int | None = Field(default=None, foreign_key="group.id", primary_key=True)
    sender_id: int | None = Field(default=None, foreign_key="user.id")


class UserBlockLink(SQLModel, table=True):
    """Association table: blocker blocked blocked user."""

    blocker_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    blocked_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)

