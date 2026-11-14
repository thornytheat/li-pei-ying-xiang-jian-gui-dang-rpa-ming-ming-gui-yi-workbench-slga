from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import audit_controller
from src.middlewares.rbac import require_permission
from src.models.user import User

router = APIRouter(tags=["audit"])


@router.get("/audit")
def recent(
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit:read")),
) -> dict:
    return audit_controller.recent(db, limit)
