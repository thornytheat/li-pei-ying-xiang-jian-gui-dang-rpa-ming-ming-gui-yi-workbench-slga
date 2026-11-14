"""导出：移交清单 CSV（按案件）/ 稽核清单 CSV（审计日志）。

移交发布口径：
  - 发布前硬校验批次链上三个投件源必须全部 covered，否则抛 HANDOVER_BLOCKED（409），不出文件；
  - 文件名与「底稿批次」列携带批次链移交版本号，同链重试发布版本号保持一致；
  - 每次发布写 handover_publishes 留痕；
  - 「移交状态」列区分「可移交 / 暂时不能移交（来源未覆盖）」，未读到的材料只字不提「丢失」。
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import ATTACHMENT_STATUS_LABELS, CASE_STATUS_LABELS, INSURANCE_TYPE_LABELS, SOURCE_NAMES
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.services import audit_service, source_service
from src.services.case_service import serialize_case


def _csv_bytes(headers: list[str], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def handover_csv(db: Session, *, actor_email: str = "") -> tuple[str, bytes]:
    # 1) 发布硬闸门：以最近一条真正执行过来源读取的批次链为准，未全覆盖直接拒绝（409，不出文件）
    latest = source_service.latest_coverage_run(db)
    if latest is None:
        from src.constants import error_codes as codes
        from src.utils.errors import AppError

        raise AppError(codes.RUN_NOT_READY, "还没有完成来源读取的归档批次，暂不能发布移交清单")
    coverage = source_service.ensure_publishable(db, latest)
    blocked_nos = source_service.blocked_case_nos(db, coverage)  # 全覆盖时为空集合

    cases = db.execute(select(ClaimCase).order_by(ClaimCase.case_no)).scalars().all()
    grouped: dict[str, list[Attachment]] = {}
    for att in db.execute(select(Attachment).order_by(Attachment.scan_seq)).scalars().all():
        if att.case_id:
            grouped.setdefault(str(att.case_id), []).append(att)

    root_no = latest.root_run_no or latest.run_no
    version = latest.handover_version
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
        "移交状态",
        "底稿批次",
        "移交版本",
        "移交时间",
    ]
    rows: list[list[str]] = []
    for case in cases:
        payload = serialize_case(case, grouped.get(str(case.id), []))
        if case.case_no in blocked_nos:
            handover_state = "暂时不能移交（投件源未覆盖）"
        else:
            handover_state = "可移交"
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
                handover_state,
                root_no,
                f"v{version}",
                stamp,
            ]
        )
    content = _csv_bytes(headers, rows)
    # 文件名带版本号：同批次链重试发布文件名一致（仅时间戳区分导出时刻）
    filename = f"docflow-handover-v{version}-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"

    # 2) 发布留痕（同链重试发布版本号不变，每次各一行）
    source_service.record_publish(
        db,
        latest,
        actor_email=actor_email,
        file_name=filename,
        row_count=len(rows),
        byte_count=len(content),
    )
    return filename, content


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
