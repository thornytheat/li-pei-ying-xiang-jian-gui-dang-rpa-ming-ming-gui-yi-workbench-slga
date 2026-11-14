"""Attachment：影像件（原名 / 新名 / 类型 / 置信 / 哈希 / 重复标记）。"""
from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import Date, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{settings.db_schema}.claim_cases.id"), nullable=True, index=True
    )
    scan_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_code: Mapped[str] = mapped_column(String(30), nullable=False, default="shared_drive")
    original_name: Mapped[str] = mapped_column(String(240), nullable=False)
    stored_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    material_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", index=True)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="classified", index=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ext: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    content_sample: Mapped[str] = mapped_column(Text, nullable=False, default="")
    match_detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    policy_no: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    policy_source: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    doc_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    manual_note: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    first_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{settings.db_schema}.archive_runs.id"), nullable=True
    )
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{settings.db_schema}.archive_runs.id"), nullable=True
    )
