from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class UserRoom(db.Model):
    """Room access grant. Users live in Supabase; we store only their UUID (spec-003)."""

    __tablename__ = "user_room"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("room.id"), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    granted_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
