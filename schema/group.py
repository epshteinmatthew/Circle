from typing import TYPE_CHECKING

from mypyc.ir.ops import Sequence
from sqlmodel import Field, Relationship, SQLModel

from schema.links import UserGroupLink, UserIncomingGroupLink

if TYPE_CHECKING:
    from schema.user import User

class GroupCreate(SQLModel):
    """Fields callers may provide when creating a group."""

    model_config = {"extra": "forbid"}

    name: str

    created_by:int


class Group(GroupCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)

    created_by:int = Field(foreign_key="user.id")

    users: list["User"] = Relationship(
        back_populates="groups",
        link_model=UserGroupLink,
    )

    user_requests: list["User"] = Relationship(
        back_populates="incoming_groups",
        link_model=UserIncomingGroupLink,
        sa_relationship_kwargs={
            "primaryjoin": "Group.id == UserIncomingGroupLink.group_id",
            "secondaryjoin": "User.id == UserIncomingGroupLink.user_id",
            "foreign_keys": "[UserIncomingGroupLink.group_id, UserIncomingGroupLink.user_id]",
        },
    )

    def add_request(self, user: "User", sender: "User") -> UserIncomingGroupLink | None:
        if (
            user in self.users
            or user in self.user_requests
            or sender not in self.users
            or self.id is None
            or user.id is None
            or sender.id is None
        ):
            return None
        return UserIncomingGroupLink(
            user_id=user.id,
            group_id=self.id,
            sender_id=sender.id,
        )

    def add_user(self, user: "User") -> bool:
        if user in self.users:
            return False
        self.users.append(user)
        if user in self.user_requests:
            self.user_requests.remove(user)
        return True

    def remove_user(self, user: "User") -> bool:
        if user not in self.users:
            return False
        self.users.remove(user)
        return True


def create_group(data: GroupCreate, created_by: "User", users: Sequence["User"]) -> Group:
    """Build a new Group from caller-provided fields only."""
    group = Group.model_validate({"name": data.name, "created_by": data.created_by})
    group.add_user(created_by)
    return group


def _rebuild_models() -> None:
    from schema.user import User

    GroupCreate.model_rebuild(_types_namespace={"User": User})
    Group.model_rebuild(_types_namespace={"User": User})


_rebuild_models()

class GroupData(SQLModel):
    name: str
    created_by: int
    users: list[int]
