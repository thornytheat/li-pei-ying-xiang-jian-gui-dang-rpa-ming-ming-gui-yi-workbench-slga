"""案件工作台：列表 / 概览 / 详情（含附件分类依据与重命名对照）。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import (
    ATTACHMENT_STATUS_LABELS,
    CASE_STATUS_LABELS,
    EXPECTED_MATERIALS,
    INSURANCE_TYPE_LABELS,
    MATERIAL_TYPE_LABELS,
    AttachmentStatus,
    CaseStatus,
    MaterialType,
)
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.utils.errors import AppError
from src.utils.ids import as_uuid
from src.utils.textutils import human_size

ARCHIVED_STATES = (AttachmentStatus.ARCHIVED.value, AttachmentStatus.DUPLICATE.value)
OPEN_STATES = (AttachmentStatus.PENDING.value, AttachmentStatus.UNKNOWN.value)


def serialize_attachment(att: Attachment, case: ClaimCase | None = None) -> dict:
    detail = att.match_detail or {}
    components = detail.get("components") or {}
    ranked = sorted(
        (
            {"material_type": key, "label": MATERIAL_TYPE_LABELS.get(key, key), **value}
            for key, value in components.items()
        ),
        key=lambda row: -float(row.get("score", 0)),
    )
    return {
        "id": str(att.id),
        "case_id": str(att.case_id) if att.case_id else None,
        "case_no": case.case_no if case else "",
        "customer_name": case.customer_name if case else "",
        "policy_no": att.policy_no,
        "policy_source": att.policy_source,
        "scan_seq": att.scan_seq,
        "source_code": att.source_code,
        "original_name": att.original_name,
        "stored_name": att.stored_name,
        "material_type": att.material_type,
        "material_label": MATERIAL_TYPE_LABELS.get(att.material_type, att.material_type),
        "confidence": round(float(att.confidence), 4),
        "status": att.status,
        "status_label": ATTACHMENT_STATUS_LABELS.get(att.status, att.status),
        "sha256": att.sha256,
        "sha256_short": att.sha256[:12],
        "size_bytes": att.size_bytes,
        "size_human": human_size(att.size_bytes),
        "ext": att.ext,
        "doc_date": att.doc_date.isoformat() if att.doc_date else None,
        "sequence_no": att.sequence_no,
        "duplicate_of": str(att.duplicate_of) if att.duplicate_of else None,
        "manual_note": att.manual_note,
        "content_preview": (att.content_sample or "")[:220],
        "signals": ranked,
        "reason": detail.get("reason", ""),
        "runner_up": detail.get("runner_up", ""),
        "weights": detail.get("weights", {}),
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }


def case_stats(case: ClaimCase, attachments: list[Attachment]) -> dict:
    archived_types = {
        att.material_type for att in attachments if att.status in ARCHIVED_STATES and att.material_type != "unknown"
    }
    expected = list(EXPECTED_MATERIALS.get(case.insurance_type, ()))
    missing = [material for material in expected if material not in archived_types]
    return {
        "attachment_count": len(attachments),
        "archived_count": sum(1 for att in attachments if att.status == AttachmentStatus.ARCHIVED.value),
        "duplicate_count": sum(1 for att in attachments if att.status == AttachmentStatus.DUPLICATE.value),
        "pending_count": sum(1 for att in attachments if att.status == AttachmentStatus.PENDING.value),
        "unknown_count": sum(1 for att in attachments if att.status == AttachmentStatus.UNKNOWN.value),
        "classified_count": sum(1 for att in attachments if att.status == AttachmentStatus.CLASSIFIED.value),
        "expected_materials": [
            {"material_type": material, "label": MATERIAL_TYPE_LABELS.get(material, material)} for material in expected
        ],
        "archived_materials": [
            {"material_type": material, "label": MATERIAL_TYPE_LABELS.get(material, material)}
            for material in expected
            if material in archived_types
        ],
        "missing_materials": [
            {"material_type": material, "label": MATERIAL_TYPE_LABELS.get(material, material)} for material in missing
        ],
        "missing_labels": [MATERIAL_TYPE_LABELS.get(material, material) for material in missing],
    }


def serialize_case(case: ClaimCase, attachments: list[Attachment]) -> dict:
    stats = case_stats(case, attachments)
    return {
        "id": str(case.id),
        "case_no": case.case_no,
        "policy_no": case.policy_no,
        "customer_name": case.customer_name,
        "insurance_type": case.insurance_type,
        "insurance_label": INSURANCE_TYPE_LABELS.get(case.insurance_type, case.insurance_type),
        "status": case.status,
        "status_label": CASE_STATUS_LABELS.get(case.status, case.status),
        "channel": case.channel,
        "assignee": case.assignee,
        "incident_date": case.incident_date.isoformat() if case.incident_date else None,
        "claim_amount": float(case.claim_amount or 0),
        "note": case.note,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        **stats,
    }


def _attachments_by_case(db: Session) -> dict[str, list[Attachment]]:
    rows = db.execute(select(Attachment).order_by(Attachment.scan_seq)).scalars().all()
    grouped: dict[str, list[Attachment]] = {}
    for att in rows:
        if att.case_id is None:
            continue
        grouped.setdefault(str(att.case_id), []).append(att)
    return grouped


def list_cases(db: Session, status: str = "", query: str = "", page: int = 1, page_size: int = 20) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    stmt = select(ClaimCase)
    if status:
        stmt = stmt.where(ClaimCase.status == status)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                ClaimCase.case_no.ilike(like),
                ClaimCase.policy_no.ilike(like),
                ClaimCase.customer_name.ilike(like),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    cases = (
        db.execute(stmt.order_by(ClaimCase.case_no).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    )
    grouped = _attachments_by_case(db)
    items = [serialize_case(case, grouped.get(str(case.id), [])) for case in cases]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def summary(db: Session) -> dict:
    cases = db.execute(select(ClaimCase)).scalars().all()
    grouped = _attachments_by_case(db)
    status_counts = {status: 0 for status in CASE_STATUS_LABELS}
    exception_cases: list[dict] = []
    for case in cases:
        status_counts[case.status] = status_counts.get(case.status, 0) + 1
    for case in cases:
        if case.status == CaseStatus.EXCEPTION.value:
            attachments = grouped.get(str(case.id), [])
            exception_cases.append(
                {
                    "id": str(case.id),
                    "case_no": case.case_no,
                    "customer_name": case.customer_name,
                    "missing_labels": case_stats(case, attachments)["missing_labels"],
                    "pending_count": sum(1 for att in attachments if att.status in OPEN_STATES),
                }
            )
    all_attachments = db.execute(select(Attachment)).scalars().all()
    attachment_counts = {status: 0 for status in ATTACHMENT_STATUS_LABELS}
    material_counts: dict[str, int] = {}
    for att in all_attachments:
        attachment_counts[att.status] = attachment_counts.get(att.status, 0) + 1
        material_counts[att.material_type] = material_counts.get(att.material_type, 0) + 1
    return {
        "case_status": status_counts,
        "case_total": len(cases),
        "attachment_status": attachment_counts,
        "attachment_total": len(all_attachments),
        "material_distribution": [
            {
                "material_type": material,
                "label": MATERIAL_TYPE_LABELS.get(material, material),
                "count": material_counts.get(material, 0),
            }
            for material in (
                MaterialType.INVOICE.value,
                MaterialType.DIAGNOSIS.value,
                MaterialType.ID_CARD.value,
                MaterialType.BANK_CARD.value,
                MaterialType.DISCHARGE.value,
                MaterialType.UNKNOWN.value,
            )
        ],
        "exceptions": exception_cases[:6],
        "exception_total": len(exception_cases),
        "archived_attachments": attachment_counts.get(AttachmentStatus.ARCHIVED.value, 0),
        "duplicate_attachments": attachment_counts.get(AttachmentStatus.DUPLICATE.value, 0),
        "pending_attachments": attachment_counts.get(AttachmentStatus.PENDING.value, 0),
        "unknown_attachments": attachment_counts.get(AttachmentStatus.UNKNOWN.value, 0),
    }


def detail(db: Session, case_id: str) -> dict:
    uid = as_uuid(case_id)
    case = db.get(ClaimCase, uid) if uid else None
    if case is None:
        raise AppError(codes.CASE_NOT_FOUND, "案件不存在", f"case_id={case_id}")
    attachments = (
        db.execute(select(Attachment).where(Attachment.case_id == case.id).order_by(Attachment.scan_seq))
        .scalars()
        .all()
    )
    payload = serialize_case(case, attachments)
    payload["attachments"] = [serialize_attachment(att, case) for att in attachments]
    payload["materials"] = sorted(
        {att.material_type for att in attachments if att.material_type != "unknown"}
    )
    return payload
