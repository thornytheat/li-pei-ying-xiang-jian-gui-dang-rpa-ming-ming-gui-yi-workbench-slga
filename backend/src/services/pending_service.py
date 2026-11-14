"""待确认队列：低置信 / 未识别附件 + 类型建议 + 数量口径。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import MATERIAL_TYPE_LABELS, AttachmentStatus
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.services.case_service import case_stats, serialize_attachment

QUEUE_STATES = (AttachmentStatus.PENDING.value, AttachmentStatus.UNKNOWN.value)


def queue(db: Session) -> dict:
    rows = (
        db.execute(
            select(Attachment).where(Attachment.status.in_(QUEUE_STATES)).order_by(Attachment.scan_seq)
        )
        .scalars()
        .all()
    )
    cases = {str(case.id): case for case in db.execute(select(ClaimCase)).scalars().all()}
    all_attachments = db.execute(select(Attachment)).scalars().all()
    grouped: dict[str, list[Attachment]] = {}
    for att in all_attachments:
        if att.case_id:
            grouped.setdefault(str(att.case_id), []).append(att)

    pending_items: list[dict] = []
    unknown_items: list[dict] = []
    for att in rows:
        case = cases.get(str(att.case_id)) if att.case_id else None
        payload = serialize_attachment(att, case)
        payload["suggestions"] = payload["signals"][:2]
        payload["case_missing"] = case_stats(case, grouped.get(str(case.id), []))["missing_labels"] if case else []
        payload["bound"] = case is not None
        if att.status == AttachmentStatus.PENDING.value:
            pending_items.append(payload)
        else:
            unknown_items.append(payload)

    duplicate_rows = db.execute(
        select(Attachment).where(Attachment.status == AttachmentStatus.DUPLICATE.value)
    ).scalars().all()
    unbound = sum(1 for att in rows if att.case_id is None)
    return {
        "items": pending_items + unknown_items,
        "pending": pending_items,
        "unknown": unknown_items,
        "counts": {
            "pending": len(pending_items),
            "unknown": len(unknown_items),
            "duplicate": len(duplicate_rows),
            "unbound": unbound,
            "total": len(rows),
        },
        "material_labels": MATERIAL_TYPE_LABELS,
        "confirmable_types": [
            {"value": key, "label": label}
            for key, label in MATERIAL_TYPE_LABELS.items()
            if key != "unknown"
        ],
    }
