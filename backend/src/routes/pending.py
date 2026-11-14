from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import pending_controller
from src.middlewares.rbac import require_permission
from src.models.user import User

router = APIRouter(tags=["pending"])


@router.get("/pending")
def queue(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("pending:read")),
) -> dict:
    return pending_controller.queue(db)
