"""Report data assembly for spec-005: KPIs, profiles and data-quality over a range."""

from datetime import date
from math import ceil

from sqlalchemy import func, select

from app.extensions import db
from app.models.passage_event import PassageEvent
from app.services import passages_v2


def hourly_profile(room, start: date, end: date) -> list[dict]:
    """Total passages per hour-of-day across the range (the traffic 'shape')."""
    local = func.timezone(room.timezone, PassageEvent.occurred_at)
    rows = db.session.execute(
        select(
            func.date_part("hour", local).label("hour"),
            func.count(PassageEvent.id).label("count"),
        )
        .filter(
            PassageEvent.room_id == room.id,
            func.date(local) >= start,
            func.date(local) <= end,
        )
        .group_by(func.date_part("hour", local))
    ).all()
    by_hour = {int(r.hour): r.count for r in rows}
    return [{"hour": h, "count": by_hour.get(h, 0)} for h in range(24)]


def gap_stats(room, start: date, end: date) -> dict:
    """Delivery losses inside the range, from device-counter jumps."""
    local = func.timezone(room.timezone, PassageEvent.occurred_at)
    rows = db.session.execute(
        select(PassageEvent.device_id, PassageEvent.access_count)
        .filter(
            PassageEvent.room_id == room.id,
            PassageEvent.access_count.is_not(None),
            func.date(local) >= start,
            func.date(local) <= end,
        )
        .order_by(PassageEvent.device_id, PassageEvent.id)
    ).all()
    jumps = 0
    missed = 0
    prev: dict[str, int] = {}
    for device_id, access in rows:
        last = prev.get(device_id)
        if last is not None and access > last + 1:
            jumps += 1
            missed += access - last - 1
        prev[device_id] = access
    return {"gap_jumps": jumps, "estimated_missed": missed}


def range_report(room, start: date, end: date) -> dict:
    per_day_body = passages_v2.date_range(room, start, end)
    per_day = per_day_body["data"]
    totals = per_day_body["totals"]
    profile = hourly_profile(room, start, end)

    days = len(per_day)
    busiest_day = max(per_day, key=lambda d: d["count"]) if days else None
    busiest_hour = max(profile, key=lambda h: h["count"])
    open_days = sum(1 for d in per_day if d["count"] > 0)

    return {
        "room": {"name": room.name, "slug": room.slug, "timezone": room.timezone},
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "totals": totals,
        "daily_average": round(totals["passages"] / days, 1) if days else 0.0,
        "visits_daily_average": round(ceil(totals["passages"] / 2) / days, 1) if days else 0.0,
        "open_days": open_days,
        "busiest_day": busiest_day,
        "busiest_hour": busiest_hour,
        "per_day": per_day,
        "hourly_profile": profile,
        "data_quality": gap_stats(room, start, end),
    }
