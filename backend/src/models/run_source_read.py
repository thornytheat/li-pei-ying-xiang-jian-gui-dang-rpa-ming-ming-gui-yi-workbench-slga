"""RunSourceRead：批次内单个投件源的读取覆盖台账（一批次 × 三来源，逐行留痕）。

口径：
  - status=covered：本来源本轮读取成功，read_count=实际读到的附件数；
  - status=failed：读取超时/未挂载/权限不足，read_count=0，failure_reason/failure_detail 记录原因；
  - 失败来源的材料从未被读到，不会产生附件行，更不会被记成「丢失」；
  - 补扫批次只为本轮重读的来源新增行，历史行保留，恢复轨迹可追溯。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, new_uuid, utcnow


class RunSourceRead(Base):
    __tablename__ = "run_source_reads"
    __table_args__ = (
        UniqueConstraint("run_id", "source_code", name="uq_run_source"),
        {"schema": settings.db_schema},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    root_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    failure_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
