from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class TestData(db.Model):
    """Legacy discovery-era table (8 prod rows from Sept 2024). Slated for removal
    together with the legacy test topic in spec-002 (DEBT-6)."""

    __tablename__ = "test_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    value: Mapped[str] = mapped_column(String(100))
    register_time: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
