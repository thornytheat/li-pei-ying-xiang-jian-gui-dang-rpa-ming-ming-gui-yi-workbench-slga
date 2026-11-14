"""导出控制器：返回 CSV 字节流并记审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.log_templates import ACTION_EXPORT_AUDIT, ACTION_EXPORT_HANDOVER
from src.models.user import User
from src.services import audit_service, export_service, source_service


def handover(db: Session, user: User, request: Request) -> tuple[str, bytes]:
    # 服务层先做来源覆盖硬闸门（未全覆盖抛 HANDOVER_BLOCKED / 409，不会产出文件）
    filename, content = export_service.handover_csv(db, actor_email=user.email)
    latest = source_service.latest_coverage_run(db)
    coverage = source_service.chain_coverage(db, latest) if latest else None
    audit_service.record(
        db,
        action=ACTION_EXPORT_HANDOVER,
        actor=user,
        entity_type="export",
        entity_id=filename,
        detail={
            "bytes": len(content),
            "root_run_no": (latest.root_run_no if latest else ""),
            "handover_version": (latest.handover_version if latest else 0),
            "all_sources_covered": bool(coverage.all_covered) if coverage else False,
        },
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
