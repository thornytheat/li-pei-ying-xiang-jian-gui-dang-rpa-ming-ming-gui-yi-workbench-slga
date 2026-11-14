"""HandoverPublish：移交清单发布留痕（同批次链重试发布，版本号保持一致）。

口径：
  - 发布前硬校验：批次链上所有投件源必须全部 covered，否则拒绝发布（HANDOVER_BLOCKED / 409）；
  - handover_version 取自批次链根批次，重试/补扫后再发布仍是同一版本号；
  - 每次发布新增一行（发布人、时间、行数、字节数、文件名），形成可审计的发布轨迹；
  - 文件名固定携带版本号，同一版本多次导出文件名一致，便于下游核对。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, new_uuid, utcnow


class HandoverPublish(Base):
    __tablename__ = "handover_publishes"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    root_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    root_run_no: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    handover_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_no: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    triggered_by_email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    file_name: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    byte_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
