"""Datetime/range helpers and availability intersection utilities."""

from datetime import datetime, timedelta, timezone, time
from typing import Any

from schema.availabilities import AvailabilitySlot


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value)
    if isinstance(value, str):
        return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    raise TypeError(f"Cannot parse datetime from {value!r}")


def ranges_overlap(
    a_start: datetime,
    a_end: datetime,
    b_start: datetime,
    b_end: datetime,
) -> bool:
    """Return True if two datetime ranges overlap (inclusive)."""
    return a_start <= b_end and b_start <= a_end


def range_tuples_overlap(
    a: tuple[datetime, datetime],
    b: tuple[datetime, datetime],
) -> bool:
    return ranges_overlap(a[0], a[1], b[0], b[1])

def slot_index(dt: datetime, origin: datetime) -> int:
    return int((ensure_utc(dt) - ensure_utc(origin)).total_seconds() // 1800)

def getBestIntervalIntersection(slots: list[AvailabilitySlot], weekday_start: datetime):
    """Returns a tuple (max_number, max_indices) where max_number is the maximum number of intersecting slots, and max_indices is an array of indices which correspond to times when this intersection takes place.
    Any given index can be translated to a time by dividing the index by two to get the hours and multiplying the remainder by 30 to get the minutes"""
    weekday_start = ensure_utc(weekday_start)
    monday_this_week = weekday_start - timedelta(days=weekday_start.weekday())
    monday_this_week = monday_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    datetime_slots = []
    for slot in slots:
        start_src = ensure_utc(slot.time_range[0])
        end_src = ensure_utc(slot.time_range[1])
        reset_time = (
            datetime.combine(
                (monday_this_week + timedelta(days=start_src.weekday())).date(),
                start_src.timetz().replace(tzinfo=None),
                tzinfo=timezone.utc,
            ),
            datetime.combine(
                (monday_this_week + timedelta(days=start_src.weekday() + (end_src.date() - start_src.date()).days)).date(),
                end_src.timetz().replace(tzinfo=None),
                tzinfo=timezone.utc,
            ),
        )
        if ranges_overlap(reset_time[0], reset_time[1], weekday_start, weekday_start + timedelta(days=1)):
            datetime_slots.append(reset_time)
    if len(datetime_slots) == 0:
        return 0, []
    earliest: datetime = min([slot[0] for slot in datetime_slots])
    latest: datetime = max([slot[1] for slot in datetime_slots])
    # +1 because the count loop includes the end slot index.
    diff = int((latest - earliest).total_seconds() // 1800) + 1
    counts = [0] * diff
    for start, end in datetime_slots:
        for i in range(slot_index(start, earliest), slot_index(end, earliest) + 1):
            counts[i] += 1
    max_count = max(counts) if counts else 0
    seen = False
    start = datetime.now()
    for indx, item in enumerate(counts):
        if not seen and item == max_count:
            start = earliest + timedelta( minutes=indx  * 30)
            seen = True
        if seen and item != max_count:
            # we are now on the first time outside the interval so we get the index before it
            return max_count, (start, earliest + timedelta(minutes=30 * (indx-1)))
    if seen:
        return max_count, (start, earliest + timedelta(minutes=30 * len(counts)))
    return 0,[]


def getIntervalIntersections(slots: list[AvailabilitySlot], weekday_start: datetime):
    """Returns a list of 48 30-minute time intervals (corresponding to a full day) where the value of each item in the list corresponds to the amount of intervals in the slots param which intersect at the respective time."""
    weekday_start = ensure_utc(weekday_start)
    monday_this_week = weekday_start - timedelta(days=weekday_start.weekday())
    monday_this_week = monday_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    datetime_slots = []
    for slot in slots:
        start_src = ensure_utc(slot.time_range[0])
        end_src = ensure_utc(slot.time_range[1])
        reset_time = (
            datetime.combine(
                (monday_this_week + timedelta(days=start_src.weekday())).date(),
                start_src.timetz().replace(tzinfo=None),
                tzinfo=timezone.utc,
            ),
            datetime.combine(
                (monday_this_week + timedelta(
                    days=start_src.weekday() + (end_src.date() - start_src.date()).days)).date(),
                end_src.timetz().replace(tzinfo=None),
                tzinfo=timezone.utc,
            ),
        )
        if ranges_overlap(reset_time[0], reset_time[1], weekday_start, weekday_start + timedelta(days=1)):
            datetime_slots.append(reset_time)
    if len(datetime_slots) == 0:
        return 0, []
    earliest: datetime = min([slot[0] for slot in datetime_slots])
    latest: datetime = max([slot[1] for slot in datetime_slots])
    # +1 because the count loop includes the end slot index.
    diff = int((latest - earliest).total_seconds() // 1800) + 1
    counts = [0] * diff
    for start, end in datetime_slots:
        for i in range(slot_index(start, earliest), slot_index(end, earliest) + 1):
            counts[i] += 1
    return counts, earliest, latest
