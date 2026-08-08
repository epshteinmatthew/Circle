from datetime import datetime

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from schema.time_range import DateTimeRangeType


class AvailabilitySlot(SQLModel, table=True):
    __tablename__ = "availability_slots"

    id: int = Field(default=None, primary_key=True)

    # Foreign key referencing the users table
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")

    # Weekly template stored as datetimes (weekday + time matter; calendar date is a carrier).
    time_range: tuple[datetime, datetime] = Field(
        sa_column=Column(DateTimeRangeType, nullable=False)
    )
