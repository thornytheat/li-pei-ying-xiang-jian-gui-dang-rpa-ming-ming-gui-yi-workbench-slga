from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import rule_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.rule import RuleCreateRequest, RulePreviewRequest

router = APIRouter(tags=["rules"])


@router.get("/rules")
def list_rules(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rules:read")),
) -> dict:
    return rule_controller.list_rules(db)


@router.post("/rules")
def create_rule(
    payload: RuleCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rules:write")),
) -> dict:
    return rule_controller.create_rule(db, payload, user)


@router.post("/rules/preview")
def preview(
    payload: RulePreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rules:read")),
) -> dict:
    return rule_controller.preview(db, payload)


@router.post("/rules/{rule_id}/activate")
def activate(
    rule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rules:write")),
) -> dict:
    return rule_controller.activate(db, rule_id, user)
