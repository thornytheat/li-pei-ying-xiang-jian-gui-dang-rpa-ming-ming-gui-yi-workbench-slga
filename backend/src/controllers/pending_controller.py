"""待确认队列控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.schemas.attachment import AttachmentOut
from src.services import pending_service


def queue(db: Session) -> dict:
    payload = pending_service.queue(db)
    payload["pending"] = [AttachmentOut(**item).model_dump() for item in payload["pending"]]
    payload["unknown"] = [AttachmentOut(**item).model_dump() for item in payload["unknown"]]
    payload["items"] = payload["pending"] + payload["unknown"]
    return payload
