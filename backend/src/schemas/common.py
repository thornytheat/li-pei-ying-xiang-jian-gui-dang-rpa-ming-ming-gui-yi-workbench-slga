"""通用响应外壳（错误体统一由 middlewares/error_handler 输出）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorPayload(BaseModel):
    code: str
    message: str
    detail: str = ""
    trace_id: str | None = None
    extra: dict[str, Any] | None = None


class ListPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[dict[str, Any]] = []
    total: int = 0
