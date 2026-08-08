"""Aggregation queries over the raw ingest log.

`data_tracker` is the interim source of truth for visualizations until spec-002
introduces `passage_event`; these functions preserve the historic semantics exactly
(all topics counted — BUG-6; no zero-filled buckets — BUG-10) so the swap is a
one-place change later.
"""

from datetime import date, datetime

from sqlalchemy import func, select

from app.extensions import db
from app.models.data_tracker import DataTracker

# Single display timezone until rooms carry their own (spec-003).
DISPLAY_TZ = "America/Sao_Paulo"


def _local_time():
    # register_time is naive UTC; the double timezone() shift converts it to São Paulo
    # wall time. Normalization at ingestion arrives with spec-002 (BUG-11).
    return func.timezone(DISPLAY_TZ, func.timezone("UTC", DataTracker.register_time))


def hourly_counts(day: date) -> list[dict]:
    local_time = _local_time()
    query = (
        select(
            func.date_part("hour", local_time).label("hour"),
            func.count(DataTracker.id).label("count"),
        )
        .filter(func.date(local_time) == day)
        .group_by(func.date_part("hour", local_time))
    )
    result = db.session.execute(query).all()
    return [
        {"time": datetime(day.year, day.month, day.day, int(r.hour)), "count": r.count}
        for r in result
    ]


def daily_counts(year: int, month: int) -> list[dict]:
    local_time = _local_time()
    query = (
        select(
            func.date(local_time).label("date"),
            func.count(DataTracker.id).label("count"),
        )
        .filter(func.extract("year", local_time) == year)
        .filter(func.extract("month", local_time) == month)
        .group_by(func.date(local_time))
        .order_by(func.date(local_time))
    )
    return [{"date": r.date, "count": r.count} for r in db.session.execute(query).all()]


def raw_rows(topic: str | None = None) -> list[dict]:
    query = select(DataTracker.id, DataTracker.topic, DataTracker.payload)
    if topic is not None:
        query = query.filter_by(topic=topic)
    rows = db.session.execute(query).all()
    return [{"id": r.id, "topic": r.topic, "payload": r.payload} for r in rows]
