"""导出控制器：返回 CSV 字节流并记审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.log_templates import ACTION_EXPORT_AUDIT, ACTION_EXPORT_HANDOVER
from src.models.user import User
from src.services import audit_service, export_service


def handover(db: Session, user: User, request: Request) -> tuple[str, bytes]:
    filename, content = export_service.handover_csv(db)
    audit_service.record(
        db,
        action=ACTION_EXPORT_HANDOVER,
        actor=user,
        entity_type="export",
        entity_id=filename,
        detail={"rows": 60, "bytes": len(content)},
        trace_id=getattr(request.state, "trace_id", ""),
    )
    db.commit()
    return filename, content


def audit(db: Session, user: User, request: Request) -> tuple[str, bytes]:
    filename, content = export_service.audit_csv(db)
    audit_service.record(
        db,
        action=ACTION_EXPORT_AUDIT,
        actor=user,
        entity_type="export",
        entity_id=filename,
        detail={"bytes": len(content)},
        trace_id=getattr(request.state, "trace_id", ""),
    )
    db.commit()
    return filename, content
