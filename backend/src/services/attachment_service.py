"""附件：序列化、人工改判（待确认 -> 已归档/重复）。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import MATERIAL_TYPE_LABELS, AttachmentStatus, MaterialType
from src.constants.log_templates import ACTION_ATTACHMENT_CONFIRM
from src.models.archive_run import ArchiveRun
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.models.user import User
from src.services import archive_service, audit_service, rule_service
from src.services.case_service import serialize_attachment
from src.services.naming_engine import plan_target
from src.utils.errors import AppError
from src.utils.ids import as_uuid
from src.utils.textutils import POLICY_RE

CONFIRMABLE = (
    AttachmentStatus.PENDING.value,
    AttachmentStatus.UNKNOWN.value,
    AttachmentStatus.CLASSIFIED.value,
)


def get_attachment(db: Session, attachment_id: str) -> Attachment:
    uid = as_uuid(attachment_id)
    att = db.get(Attachment, uid) if uid else None
    if att is None:
        raise AppError(codes.ATTACHMENT_NOT_FOUND, "附件不存在", f"attachment_id={attachment_id}")
    return att


def confirm(
    db: Session,
    attachment_id: str,
    user: User,
    material_type: str,
    policy_no: str,
    note: str,
) -> dict:
    att = get_attachment(db, attachment_id)
    if att.status not in CONFIRMABLE:
        raise AppError(
            codes.ATTACHMENT_NOT_PENDING,
            "该附件不在待确认状态，无法改判",
            f"status={att.status}",
        )
    if material_type not in {item.value for item in MaterialType if item != MaterialType.UNKNOWN}:
        raise AppError(codes.VALIDATION_ERROR, "材料类型不合法", f"material_type={material_type}")

    policy = (policy_no or "").strip().upper()
    case = db.get(ClaimCase, att.case_id) if att.case_id else None
    if not policy:
        policy = att.policy_no or (case.policy_no if case else "")
    if not policy or not POLICY_RE.fullmatch(policy):
        raise AppError(codes.POLICY_NO_INVALID, "请填写 P + 12 位数字的保单号", f"policy_no={policy}")
    if case is None:
        case = db.execute(select(ClaimCase).where(ClaimCase.policy_no == policy)).scalars().first()
        if case is None:
            raise AppError(codes.CASE_NOT_FOUND, f"保单号 {policy} 没有对应案件", f"policy_no={policy}")
        att.case_id = case.id

    rule = rule_service.get_active(db)
    used, owners = archive_service.build_name_maps(db)
    doc_date = att.doc_date or (case.incident_date if case else None) or date.today()
    previous_confidence = round(float(att.confidence), 4)

    att.material_type = material_type
    att.confidence = 1.0
    att.policy_no = policy
    att.policy_source = "manual"
    att.manual_note = (note or f"{user.display_name} 人工判为{MATERIAL_TYPE_LABELS[material_type]}")[:240]
    att.match_detail = {
        **(att.match_detail or {}),
        "manual": {
            "actor": user.email,
            "material_type": material_type,
            "previous_confidence": previous_confidence,
            "note": att.manual_note,
        },
    }

    result = plan_target(
        template=rule.template,
        policy_no=policy,
        material_type=material_type,
        doc_date=doc_date,
        ext=att.ext,
        content_sha256=att.sha256,
        used=used,
    )
    if result.action == "archive":
        att.stored_name = result.stored_name
        att.sequence_no = result.sequence_no
        att.status = AttachmentStatus.ARCHIVED.value
        archive_service.write_payload(result.stored_name, att.content_sample)
    elif result.action == "duplicate":
        att.status = AttachmentStatus.DUPLICATE.value
        att.duplicate_of = owners.get(result.duplicate_name)
        att.stored_name = None
    else:
        raise AppError(
            codes.ATTACHMENT_NOT_PENDING,
            f"人工改判未能生成可用文件名：{result.reason}",
            result.action,
        )

    run = db.get(ArchiveRun, att.last_run_id) if att.last_run_id else None
    if run is not None:
        run.pending = max(0, run.pending - 1)
        run.manual = run.manual + 1
        if result.action == "archive":
            run.archived = run.archived + 1
        else:
            run.duplicate = run.duplicate + 1
        archive_service.append_log(
            run,
            f"人工改判 {att.original_name} -> {att.stored_name or result.duplicate_name}"
            f"（{MATERIAL_TYPE_LABELS[material_type]}，提单 {policy}）",
        )

    archive_service.recompute_case_statuses(db)
    audit_service.record(
        db,
        action=ACTION_ATTACHMENT_CONFIRM,
        actor=user,
        entity_type="attachment",
        entity_id=att.id,
        detail={
            "original_name": att.original_name,
            "stored_name": att.stored_name,
            "material_type": material_type,
            "policy_no": policy,
            "action": result.action,
        },
    )
    db.commit()
    return serialize_attachment(att, case)
