"""NamingRule 的对外结构与入参。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RuleOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    version: int
    template: str
    conflict_policy: str
    date_source: str
    is_active: bool
    note: str = ""
    created_by_email: str = ""
    created_at: str | None = None
    usage_runs: int = 0


class RuleCreateRequest(BaseModel):
    template: str = Field(min_length=4, max_length=200)
    note: str = Field(default="", max_length=200)
    conflict_policy: str = Field(default="sha256_duplicate_first", max_length=30)
    date_source: str = Field(default="filename>content>case", max_length=30)


class RulePreviewRequest(BaseModel):
    template: str = Field(min_length=4, max_length=200)
