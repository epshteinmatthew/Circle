import enum
from datetime import time

from sqlalchemy import Column, Enum
from sqlmodel import Field, SQLModel

from schema.time_range import TimeRangeType


class DayOfWeek(enum.Enum):
    MON = "Monday"
    TUE = "Tuesday"
    WED = "Wednesday"
    THU = "Thursday"
    FRI = "Friday"
    SAT = "Saturday"
    SUN = "Sunday"

class AvailabilitySlot(SQLModel, table=True):
    __tablename__ = "availability_slots"

    id: int = Field(default=None, primary_key=True)

    # Foreign key referencing the users table
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")

    # Store the day as an Enum
    day: DayOfWeek = Field(sa_column=Column(Enum(DayOfWeek), nullable=False))

    # Use your original custom TimeRangeType here via sa_column!
    time_range: tuple[time, time] = Field(
        sa_column=Column(TimeRangeType, nullable=False)
    )


def getBestIntervalIntersection(slots: list[AvailabilitySlot], day: DayOfWeek):
    """Returns a tuple (max_number, max_indices) where max_number is the maximum number of intersecting slots, and max_indices is an array of indices which correspond to times when this intersection takes place.
    Any given index can be translated to a time by dividing the index by two to get the hours and multiplying the remainder by 30 to get the minutes"""
    intersect_list = [0] * 48
    max_number = 0
    for slot in slots:
        if slot.day == day:
            start = slot.time_range[0].hour * 2 + slot.time_range[0].minute // 30
            end = slot.time_range[1].hour * 2 + slot.time_range[1].minute // 30
            for i in range(start, end+1):
                intersect_list[i] += 1
                if intersect_list[i] > max_number:
                    max_number = intersect_list[i]
    max_indices = []
    for item, index in enumerate(intersect_list):
        if item == max_number:
            max_indices.append(index)
    return max_number, max_indices

def getIntervalIntersections(slots: list[AvailabilitySlot], day: DayOfWeek):
    """Returns a list of 48 30-minute time intervals (corresponding to a full day) where the value of each item in the list corresponds to the amount of intervals in the slots param which intersect at the respective time."""
    intersect_list = [0] * 48
    for slot in slots:
        if slot.day == day:
            start = slot.time_range[0].hour * 2 + slot.time_range[0].minute // 30
            end = slot.time_range[1].hour * 2 + slot.time_range[1].minute // 30
            for i in range(start, end+1):
                intersect_list[i] += 1

    return intersect_list

