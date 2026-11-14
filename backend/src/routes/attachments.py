from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import attachment_controller
from src.middlewares.rate_limit import rate_limit
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.attachment import AttachmentConfirmRequest

router = APIRouter(tags=["attachments"])


@router.get("/attachments/{attachment_id}")
def detail(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attachments:read")),
) -> dict:
    return attachment_controller.detail(db, attachment_id)


@router.post("/attachments/{attachment_id}/confirm", dependencies=[rate_limit("confirm")])
def confirm(
    attachment_id: str,
    payload: AttachmentConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attachments:confirm")),
) -> dict:
    return attachment_controller.confirm(db, attachment_id, payload, user)
