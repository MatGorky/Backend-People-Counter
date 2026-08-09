from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Device(db.Model):
    """A physical sensor, registered explicitly and pointed at a room (spec-003).

    Messages from unregistered device_ids are raw-logged but never become passage
    events — prevents public-broker spoofing from creating data (SEC-3 mitigation).
    `last_seen` doubles as a device-health signal.
    """

    __tablename__ = "device"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("room.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
