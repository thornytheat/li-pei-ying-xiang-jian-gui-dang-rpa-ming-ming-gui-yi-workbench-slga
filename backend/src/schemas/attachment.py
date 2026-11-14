"""Attachment 的对外结构与人工改判入参。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AttachmentOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    case_id: str | None = None
    case_no: str = ""
    customer_name: str = ""
    policy_no: str = ""
    policy_source: str = ""
    scan_seq: int
    source_code: str
    original_name: str
    stored_name: str | None = None
    material_type: str
    material_label: str
    confidence: float
    status: str
    status_label: str
    sha256: str
    sha256_short: str
    size_bytes: int = 0
    size_human: str = ""
    ext: str = ""
    doc_date: str | None = None
    sequence_no: int | None = None
    duplicate_of: str | None = None
    manual_note: str = ""
    content_preview: str = ""
    signals: list[dict[str, Any]] = []
    reason: str = ""
    runner_up: str = ""


class AttachmentConfirmRequest(BaseModel):
    material_type: str = Field(description="invoice / diagnosis / id_card / bank_card / discharge")
    policy_no: str = Field(default="", max_length=20, description="P + 12 位数字；留空则取案件绑定保单号")
    note: str = Field(default="", max_length=200)
