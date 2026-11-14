"""NamingRule：命名模板与冲突策略（版本化）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, new_uuid, utcnow


class NamingRule(Base):
    __tablename__ = "naming_rules"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    template: Mapped[str] = mapped_column(String(200), nullable=False)
    conflict_policy: Mapped[str] = mapped_column(String(30), nullable=False, default="sha256_duplicate_first")
    date_source: Mapped[str] = mapped_column(String(30), nullable=False, default="filename>content>case")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    note: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    created_by_email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
