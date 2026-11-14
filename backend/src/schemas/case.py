"""ClaimCase / Attachment 的对外结构（服务层产出 dict，此处做一次模型校验与文档化）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class MaterialRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    material_type: str
    label: str


class CaseOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    case_no: str
    policy_no: str
    customer_name: str
    insurance_type: str
    insurance_label: str
    status: str
    status_label: str
    channel: str
    assignee: str
    incident_date: str | None = None
    claim_amount: float = 0
    note: str = ""
    attachment_count: int = 0
    archived_count: int = 0
    duplicate_count: int = 0
    pending_count: int = 0
    unknown_count: int = 0
    classified_count: int = 0
    expected_materials: list[MaterialRef] = []
    archived_materials: list[MaterialRef] = []
    missing_materials: list[MaterialRef] = []
    missing_labels: list[str] = []
    attachments: list[dict[str, Any]] = []
    updated_at: str | None = None


class CaseListOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[CaseOut]
    total: int
    page: int
    page_size: int
    pages: int
