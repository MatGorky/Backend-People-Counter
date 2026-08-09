from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class PassageEvent(db.Model):
    """One row = one beam interruption, parsed and time-normalized (spec-002).

    `occurred_at` is true UTC (the device's São Paulo-mislabeled-Z timestamp is
    normalized at ingestion). `raw_id` links to the data_tracker audit row and is
    UNIQUE — the hard idempotency guarantee for backfill and re-processing.
    """

    __tablename__ = "passage_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(100))
    room_id: Mapped[int | None] = mapped_column(ForeignKey("room.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    access_count: Mapped[int | None] = mapped_column(BigInteger)
    people_count: Mapped[int | None] = mapped_column(BigInteger)
    status_sensor: Mapped[str | None] = mapped_column(String(50))
    rssi: Mapped[int | None]
    ip_address: Mapped[str | None] = mapped_column(INET)
    pulse_ton: Mapped[int | None]
    pulse_toff: Mapped[int | None]
    raw_id: Mapped[int | None] = mapped_column(ForeignKey("data_tracker.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_passage_event_room_occurred", "room_id", "occurred_at"),
        Index("ix_passage_event_device_occurred", "device_id", "occurred_at"),
    )
