"""命名规则控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.user import User
from src.schemas.rule import RuleCreateRequest, RuleOut, RulePreviewRequest
from src.services import rule_service


def list_rules(db: Session) -> dict:
    payload = rule_service.list_rules(db)
    payload["items"] = [RuleOut(**item).model_dump() for item in payload["items"]]
    if payload.get("active"):
        payload["active"] = RuleOut(**payload["active"]).model_dump()
    return payload


def create_rule(db: Session, payload: RuleCreateRequest, user: User) -> dict:
    rule = rule_service.create_rule(
        db,
        user=user,
        template=payload.template,
        note=payload.note,
        conflict_policy=payload.conflict_policy,
        date_source=payload.date_source,
    )
    return RuleOut(**rule).model_dump()


def preview(db: Session, payload: RulePreviewRequest) -> dict:
    return rule_service.preview(db, payload.template)


def activate(db: Session, rule_id: str, user: User) -> dict:
    return RuleOut(**rule_service.activate_rule(db, user, rule_id)).model_dump()
