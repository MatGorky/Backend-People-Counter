from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class DataTracker(db.Model):
    """Raw MQTT ingest log: one row per received message, payload stored verbatim.

    Currently also the (interim) source for all visualizations — replaced as the
    source of truth by `passage_event` in spec-002; stays as the audit trail.
    """

    __tablename__ = "data_tracker"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(100))
    payload: Mapped[str] = mapped_column(String(1000))
    # Naive UTC server receipt time (see docs/current-state.md §6 on time semantics).
    register_time: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
