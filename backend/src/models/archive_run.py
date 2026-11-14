"""ArchiveRun：归档批次（扫描/归档/待确认/重复/失败计数 + 日志）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, new_uuid, utcnow


class ArchiveRun(Base):
    __tablename__ = "archive_runs"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    run_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="archive")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    template_snapshot: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    triggered_by_email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    # 批次链：首次批次 root_run_id 指向自己；补扫（resume）产生的批次指向同一根批次，
    # 同一条链共享 handover_version，重试发布移交清单版本号保持一致。
    root_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    root_run_no: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    handover_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 来源覆盖快照（CoverageSummary.to_dict()），与 run_source_reads 行互为冗余便于列表直出
    source_coverage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    log: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
