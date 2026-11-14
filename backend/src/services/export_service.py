"""导出：移交清单 CSV（按案件）/ 稽核清单 CSV（审计日志）。"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import ATTACHMENT_STATUS_LABELS, CASE_STATUS_LABELS, INSURANCE_TYPE_LABELS, SOURCE_NAMES
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.services import audit_service, run_service
from src.services.case_service import serialize_case


def _csv_bytes(headers: list[str], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def handover_csv(db: Session) -> tuple[str, bytes]:
    cases = db.execute(select(ClaimCase).order_by(ClaimCase.case_no)).scalars().all()
    grouped: dict[str, list[Attachment]] = {}
    for att in db.execute(select(Attachment).order_by(Attachment.scan_seq)).scalars().all():
        if att.case_id:
            grouped.setdefault(str(att.case_id), []).append(att)
    latest = run_service.latest_run(db)
    latest_no = latest.run_no if latest else ""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    headers = [
        "案件号",
        "保单号",
        "客户",
        "险种",
        "案件状态",
        "投件源",
        "受理员",
        "附件数",
        "已归档",
        "重复件",
        "待确认",
        "未识别",
        "缺失材料",
        "底稿批次",
        "移交时间",
    ]
    rows: list[list[str]] = []
    for case in cases:
        payload = serialize_case(case, grouped.get(str(case.id), []))
        rows.append(
            [
                payload["case_no"],
                payload["policy_no"],
                payload["customer_name"],
                payload["insurance_label"],
                CASE_STATUS_LABELS.get(payload["status"], payload["status"]),
                SOURCE_NAMES.get(payload["channel"], payload["channel"]),
                payload["assignee"],
                str(payload["attachment_count"]),
                str(payload["archived_count"]),
                str(payload["duplicate_count"]),
                str(payload["pending_count"]),
                str(payload["unknown_count"]),
                "、".join(payload["missing_labels"]) or "无",
                latest_no,
                stamp,
            ]
        )
    filename = f"docflow-handover-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return filename, _csv_bytes(headers, rows)


def audit_csv(db: Session) -> tuple[str, bytes]:
    entries = audit_service.recent(db, limit=500)
    headers = ["时间", "动作", "操作人", "对象类型", "对象ID", "追踪号", "详情"]
    rows = [
        [
            entry["created_at"] or "",
            entry["action"],
            entry["actor_email"],
            entry["entity_type"],
            entry["entity_id"][:36],
            entry["trace_id"],
            str(entry["detail"])[:400],
        ]
        for entry in entries
    ]
    filename = f"docflow-audit-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return filename, _csv_bytes(headers, rows)


__all__ = ["handover_csv", "audit_csv", "ATTACHMENT_STATUS_LABELS"]
