"""ClaimCase：理赔案件（保单号 / 客户 / 险种 / 状态）。"""
from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import Date, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid


class ClaimCase(Base, TimestampMixin):
    __tablename__ = "claim_cases"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    policy_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    insurance_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_docs", index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="shared_drive")
    assignee: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    incident_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    claim_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
