from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Room(db.Model):
    """A monitored space. Users are granted access per room (spec-003)."""

    __tablename__ = "room"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/Sao_Paulo", server_default="America/Sao_Paulo"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
