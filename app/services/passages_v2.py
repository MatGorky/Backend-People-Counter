"""Aggregations over passage_event — the spec-002 source of truth.

All buckets are zero-filled and computed in the room's timezone; the
"visits = ceil(passages / 2)" product rule lives HERE, not in clients.
Values are returned JSON-ready (ISO strings, ints).
"""

import calendar
from datetime import date, timedelta
from math import ceil

from sqlalchemy import func, select

from app.extensions import db
from app.models.passage_event import PassageEvent


def _totals(passages: int) -> dict:
    return {"passages": passages, "visits": ceil(passages / 2)}


def _local(room):
    # occurred_at is timestamptz (UTC); one conversion to the room's wall time.
    return func.timezone(room.timezone, PassageEvent.occurred_at)


def daily(room, day: date) -> dict:
    local = _local(room)
    rows = db.session.execute(
        select(
            func.date_part("hour", local).label("hour"),
            func.count(PassageEvent.id).label("count"),
        )
        .filter(PassageEvent.room_id == room.id, func.date(local) == day)
        .group_by(func.date_part("hour", local))
    ).all()
    by_hour = {int(r.hour): r.count for r in rows}
    data = [
        {"time": f"{day.isoformat()}T{hour:02d}:00:00", "count": by_hour.get(hour, 0)}
        for hour in range(24)
    ]
    return {"data": data, "totals": _totals(sum(by_hour.values()))}


def _per_day(room, start: date, end: date) -> dict:
    local = _local(room)
    rows = db.session.execute(
        select(func.date(local).label("date"), func.count(PassageEvent.id).label("count"))
        .filter(
            PassageEvent.room_id == room.id,
            func.date(local) >= start,
            func.date(local) <= end,
        )
        .group_by(func.date(local))
    ).all()
    by_day = {r.date: r.count for r in rows}
    data = []
    cursor = start
    while cursor <= end:
        data.append({"date": cursor.isoformat(), "count": by_day.get(cursor, 0)})
        cursor += timedelta(days=1)
    return {"data": data, "totals": _totals(sum(by_day.values()))}


def monthly(room, year: int, month: int) -> dict:
    last_day = calendar.monthrange(year, month)[1]
    return _per_day(room, date(year, month, 1), date(year, month, last_day))


def date_range(room, start: date, end: date) -> dict:
    return _per_day(room, start, end)


def yearly(room, year: int, resolution: str = "monthly") -> dict:
    if resolution == "daily":
        return _per_day(room, date(year, 1, 1), date(year, 12, 31))

    local = _local(room)
    rows = db.session.execute(
        select(
            func.date_part("month", local).label("month"),
            func.count(PassageEvent.id).label("count"),
        )
        .filter(
            PassageEvent.room_id == room.id,
            func.date_part("year", local) == year,
        )
        .group_by(func.date_part("month", local))
    ).all()
    by_month = {int(r.month): r.count for r in rows}
    data = [
        {"month": f"{year}-{month:02d}", "count": by_month.get(month, 0)} for month in range(1, 13)
    ]
    return {"data": data, "totals": _totals(sum(by_month.values()))}
