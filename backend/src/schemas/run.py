"""ArchiveRun 的对外结构与入参。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RunOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    run_no: str
    mode: str
    mode_label: str
    status: str
    status_label: str
    rule_version: int
    template_snapshot: str
    triggered_by_email: str = ""
    note: str = ""
    scanned: int = 0
    new_files: int = 0
    archived: int = 0
    duplicate: int = 0
    pending: int = 0
    unknown: int = 0
    unchanged: int = 0
    failed: int = 0
    manual: int = 0
    auto_named: int = 0
    log: list[str] = []
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int = 0
    created_at: str | None = None


class RunCreateRequest(BaseModel):
    mode: Literal["dry_run", "archive"] = "archive"
    note: str = Field(default="", max_length=200)
