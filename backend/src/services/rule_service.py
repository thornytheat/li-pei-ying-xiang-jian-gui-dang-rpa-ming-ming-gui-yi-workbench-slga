"""命名规则：版本化（新建版本即停用旧版本）、模板校验、真实附件预览。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.log_templates import ACTION_RULE_ACTIVATE, ACTION_RULE_CREATE
from src.models.archive_run import ArchiveRun
from src.models.attachment import Attachment
from src.models.naming_rule import NamingRule
from src.models.user import User
from src.services import audit_service
from src.services.naming_engine import REQUIRED_TOKENS, preview_rows, validate_template
from src.utils.errors import AppError
from src.utils.ids import as_uuid


def serialize(rule: NamingRule, usage: int = 0) -> dict:
    return {
        "id": str(rule.id),
        "version": rule.version,
        "template": rule.template,
        "conflict_policy": rule.conflict_policy,
        "date_source": rule.date_source,
        "is_active": rule.is_active,
        "note": rule.note,
        "created_by_email": rule.created_by_email,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "usage_runs": usage,
    }


def list_rules(db: Session) -> dict:
    rules = db.execute(select(NamingRule).order_by(NamingRule.version.desc())).scalars().all()
    usage: dict[int, int] = {}
    for version, count in (
        db.query(ArchiveRun.rule_version, func.count(ArchiveRun.id)).group_by(ArchiveRun.rule_version).all()
    ):
        usage[version] = count
    active = next((rule for rule in rules if rule.is_active), None)
    return {
        "items": [serialize(rule, usage.get(rule.version, 0)) for rule in rules],
        "active": serialize(active, usage.get(active.version, 0)) if active else None,
        "tokens": list(REQUIRED_TOKENS),
        "required_tokens": list(REQUIRED_TOKENS),
    }


def get_active(db: Session) -> NamingRule:
    rule = db.execute(select(NamingRule).where(NamingRule.is_active.is_(True))).scalars().first()
    if rule is None:
        raise AppError(codes.RUN_NOT_READY, "没有启用的命名规则", "active naming rule missing")
    return rule


def create_rule(db: Session, user: User, template: str, note: str, conflict_policy: str, date_source: str) -> dict:
    ok, missing, message = validate_template(template)
    if not ok:
        raise AppError(codes.TEMPLATE_INVALID, message, "missing=" + ",".join(missing), extra={"missing": missing})

    max_version = db.execute(select(NamingRule.version).order_by(NamingRule.version.desc())).scalars().first() or 0
    db.query(NamingRule).filter(NamingRule.is_active.is_(True)).update({"is_active": False})
    rule = NamingRule(
        version=max_version + 1,
        template=template.strip(),
        conflict_policy=conflict_policy or "sha256_duplicate_first",
        date_source=date_source or "filename>content>case",
        is_active=True,
        note=(note or "").strip()[:240],
        created_by_email=user.email,
    )
    db.add(rule)
    db.flush()
    audit_service.record(
        db,
        action=ACTION_RULE_CREATE,
        actor=user,
        entity_type="naming_rule",
        entity_id=rule.id,
        detail={"version": rule.version, "template": rule.template},
    )
    db.commit()
    return serialize(rule)


def activate_rule(db: Session, user: User, rule_id: str) -> dict:
    uid = as_uuid(rule_id)
    rule = db.get(NamingRule, uid) if uid else None
    if rule is None:
        raise AppError(codes.NOT_FOUND, "规则版本不存在", f"rule_id={rule_id}")
    db.query(NamingRule).filter(NamingRule.is_active.is_(True)).update({"is_active": False})
    rule.is_active = True
    audit_service.record(
        db, action=ACTION_RULE_ACTIVATE, actor=user, entity_type="naming_rule", entity_id=rule.id,
        detail={"version": rule.version},
    )
    db.commit()
    return serialize(rule)


def preview(db: Session, template: str) -> dict:
    ok, missing, message = validate_template(template)
    samples = (
        db.execute(
            select(Attachment)
            .where(Attachment.status != "unknown")
            .order_by(Attachment.scan_seq)
            .limit(6)
        )
        .scalars()
        .all()
    )
    rows = preview_rows(
        template,
        [
            {
                "attachment_id": str(item.id),
                "original_name": item.original_name,
                "material_type": item.material_type,
                "confidence": round(float(item.confidence), 4),
                "policy_no": item.policy_no,
                "doc_date": item.doc_date,
                "ext": item.ext,
                "sha256": item.sha256,
            }
            for item in samples
        ],
    )
    return {"valid": ok, "message": message, "missing": missing, "rows": rows, "template": template}
