from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from schema.links import UserGroupLink

if TYPE_CHECKING:
    from schema.user import User


class GroupBase(SQLModel):
    name: str


class GroupCreate(GroupBase):
    """Fields callers may provide when creating a group."""

    model_config = {"extra": "forbid"}

    users: list["User"] = Field(default_factory=list)


class Group(GroupBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    users: list["User"] = Relationship(
        back_populates="groups",
        link_model=UserGroupLink,
    )

    def add_user(self, user: "User") -> bool:
        if user in self.users:
            return False
        self.users.append(user)
        return True

    def remove_user(self, user: "User") -> bool:
        if user not in self.users:
            return False
        self.users.remove(user)
        return True


def create_group(data: GroupCreate) -> Group:
    """Build a new Group from caller-provided fields only."""
    group = Group.model_validate({"name": data.name})
    for user in data.users:
        group.add_user(user)
    return group


def _rebuild_models() -> None:
    from schema.user import User

    GroupCreate.model_rebuild(_types_namespace={"User": User})
    Group.model_rebuild(_types_namespace={"User": User})


_rebuild_models()
