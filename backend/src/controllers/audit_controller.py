"""审计日志读取（仅 admin）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import audit_service


def recent(db: Session, limit: int = 60) -> dict:
    return {"items": audit_service.recent(db, limit=limit), "total": limit}
