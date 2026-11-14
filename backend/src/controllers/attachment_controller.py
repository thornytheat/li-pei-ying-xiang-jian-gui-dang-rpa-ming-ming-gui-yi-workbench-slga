"""附件控制器：详情 + 人工改判。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.user import User
from src.schemas.attachment import AttachmentConfirmRequest, AttachmentOut
from src.services import attachment_service
from src.services.case_service import serialize_attachment


def detail(db: Session, attachment_id: str) -> dict:
    att = attachment_service.get_attachment(db, attachment_id)
    return AttachmentOut(**serialize_attachment(att)).model_dump()


def confirm(db: Session, attachment_id: str, payload: AttachmentConfirmRequest, user: User) -> dict:
    result = attachment_service.confirm(
        db,
        attachment_id=attachment_id,
        user=user,
        material_type=payload.material_type,
        policy_no=payload.policy_no,
        note=payload.note,
    )
    return AttachmentOut(**result).model_dump()
