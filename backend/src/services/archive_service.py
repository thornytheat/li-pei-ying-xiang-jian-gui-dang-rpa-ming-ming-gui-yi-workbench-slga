"""归档批次执行：扫描投件源 -> 分类复核 -> 命名归一 -> 落盘/重复标记 -> 案件状态回写。

幂等口径：
  - 已 archived 的附件再跑只计入 unchanged，不重复落盘、不改名；
  - 已 duplicate 的附件再跑仍计入 duplicate（不落盘）；
  - 试运行（dry_run）只统计，不写库字段、不写磁盘。
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import AttachmentStatus, CaseStatus, RunMode, RunStatus
from src.constants.log_templates import ACTION_RUN_EXECUTE, ACTION_RUN_FAILED
from src.models.archive_run import ArchiveRun
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.services import audit_service
from src.services.naming_engine import plan_target
from src.utils.logger import get_logger
from src.utils.textutils import now_stamp

logger = get_logger("docflow.archive")
LOG_LIMIT = 80


def archive_dir() -> str:
    path = os.path.abspath(settings.archive_store)
    os.makedirs(path, exist_ok=True)
    return path


def stored_file_count() -> int:
    try:
        return sum(1 for name in os.listdir(archive_dir()) if os.path.isfile(os.path.join(archive_dir(), name)))
    except OSError:
        return 0


def write_payload(stored_name: str, content_sample: str) -> str:
    """把重命名后的材料落到共享产物卷（demo 用内容抽样代替二进制原件）。"""
    target = os.path.join(archive_dir(), os.path.basename(stored_name))
    with open(target, "wb") as handle:
        handle.write((content_sample or "").encode("utf-8"))
    return target


def append_log(run: ArchiveRun, message: str) -> None:
    line = f"[{now_stamp()}] {message}"
    lines = list(run.log or [])
    lines.append(line)
    run.log = lines[-LOG_LIMIT:]
    print(f"[run {run.run_no}] {message}", flush=True)


def build_name_maps(db: Session) -> tuple[dict[str, str], dict[str, str]]:
    """已占用名字表：name -> sha256，以及 name -> 附件ID（重复件回指用）。"""
    rows = db.execute(select(Attachment).where(Attachment.stored_name.is_not(None))).scalars().all()
    used = {row.stored_name: row.sha256 for row in rows if row.stored_name}
    owners = {row.stored_name: str(row.id) for row in rows if row.stored_name}
    return used, owners


def recompute_case_statuses(db: Session) -> None:
    grouped: dict[str, list[Attachment]] = {}
    for att in db.execute(select(Attachment)).scalars().all():
        if att.case_id is None:
            continue
        grouped.setdefault(str(att.case_id), []).append(att)
    for case in db.execute(select(ClaimCase)).scalars().all():
        attachments = grouped.get(str(case.id), [])
        if not attachments:
            new_status = CaseStatus.PENDING_DOCS.value
        elif any(
            att.status in (AttachmentStatus.PENDING.value, AttachmentStatus.UNKNOWN.value) for att in attachments
        ):
            new_status = CaseStatus.EXCEPTION.value
        elif all(
            att.status in (AttachmentStatus.ARCHIVED.value, AttachmentStatus.DUPLICATE.value)
            for att in attachments
        ):
            new_status = CaseStatus.ARCHIVED.value
        else:
            new_status = CaseStatus.PENDING_DOCS.value
        if case.status != new_status:
            case.status = new_status


def _source_tally(attachments: list[Attachment]) -> str:
    tally: dict[str, int] = {}
    for att in attachments:
        tally[att.source_code] = tally.get(att.source_code, 0) + 1
    order = ("shared_drive", "mailbox", "portable")
    labels = {"shared_drive": "共享盘", "mailbox": "邮箱", "portable": "移动盘"}
    return " / ".join(f"{labels.get(code, code)} {tally.get(code, 0)}" for code in order)


def execute_run(db: Session, run: ArchiveRun, mode: str | None = None) -> ArchiveRun:
    source_mode = (mode or run.mode or RunMode.ARCHIVE.value).strip()
    dry_run = source_mode == RunMode.DRY_RUN.value
    started = time.perf_counter()
    run.mode = source_mode
    run.status = RunStatus.RUNNING.value
    run.started_at = datetime.now(timezone.utc)
    run.log = []
    run.scanned = run.new_files = run.archived = 0
    run.duplicate = run.pending = run.unknown = 0
    run.unchanged = run.failed = 0
    db.commit()

    counters = {
        "scanned": 0,
        "new_files": 0,
        "archived": 0,
        "duplicate": 0,
        "pending": 0,
        "unknown": 0,
        "unchanged": 0,
        "failed": 0,
    }
    try:
        attachments = db.execute(select(Attachment).order_by(Attachment.scan_seq)).scalars().all()
        cases = {str(case.id): case for case in db.execute(select(ClaimCase)).scalars().all()}
        used, owners = build_name_maps(db)
        counters["scanned"] = len(attachments)
        append_log(run, f"扫描投件源 {_source_tally(attachments)}，共 {len(attachments)} 件")
        if dry_run:
            append_log(run, "试运行模式：只统计分类与命名结果，不改名、不落盘")

        threshold = settings.pending_confidence_threshold
        classified = pending = unknown = 0
        for att in attachments:
            case = cases.get(str(att.case_id)) if att.case_id else None
            if att.first_run_id is None:
                counters["new_files"] += 1
                if not dry_run:
                    att.first_run_id = run.id

            if att.material_type == "unknown" or att.status == AttachmentStatus.UNKNOWN.value:
                counters["unknown"] += 1
                unknown += 1
                if not dry_run:
                    att.last_run_id = run.id
                continue
            if att.status == AttachmentStatus.PENDING.value or float(att.confidence) < threshold:
                counters["pending"] += 1
                pending += 1
                if not dry_run:
                    att.last_run_id = run.id
                continue

            classified += 1
            if att.status == AttachmentStatus.ARCHIVED.value:
                counters["unchanged"] += 1
                continue
            if att.status == AttachmentStatus.DUPLICATE.value:
                counters["duplicate"] += 1
                continue

            policy = att.policy_no or (case.policy_no if case else "")
            doc_date = att.doc_date or (case.incident_date if case else None) or date.today()
            if not policy:
                counters["pending"] += 1
                pending += 1
                if not dry_run:
                    att.status = AttachmentStatus.PENDING.value
                    att.last_run_id = run.id
                continue

            result = plan_target(
                template=run.template_snapshot,
                policy_no=policy,
                material_type=att.material_type,
                doc_date=doc_date,
                ext=att.ext,
                content_sha256=att.sha256,
                used=used,
            )
            if result.action == "archive":
                counters["archived"] += 1
                used[result.stored_name] = att.sha256
                owners[result.stored_name] = str(att.id)
                if not dry_run:
                    att.stored_name = result.stored_name
                    att.sequence_no = result.sequence_no
                    att.policy_no = policy
                    att.status = AttachmentStatus.ARCHIVED.value
                    att.last_run_id = run.id
                    write_payload(result.stored_name, att.content_sample)
            elif result.action == "duplicate":
                counters["duplicate"] += 1
                if not dry_run:
                    att.status = AttachmentStatus.DUPLICATE.value
                    att.duplicate_of = owners.get(result.duplicate_name)
                    att.stored_name = None
                    att.last_run_id = run.id
            else:
                counters["pending"] += 1
                pending += 1
                if not dry_run:
                    att.status = AttachmentStatus.PENDING.value
                    att.last_run_id = run.id

        run.scanned = counters["scanned"]
        run.new_files = counters["new_files"]
        run.archived = counters["archived"]
        run.duplicate = counters["duplicate"]
        run.pending = counters["pending"]
        run.unknown = counters["unknown"]
        run.unchanged = counters["unchanged"]
        run.failed = counters["failed"]

        append_log(
            run,
            f"分类复核：可自动归档 {classified} 件 / 待确认 {pending} 件 / 未识别 {unknown} 件",
        )
        append_log(
            run,
            "命名归一：归档 {archived} 件 / 重复 {duplicate} 件（内容 SHA-256 相同，不落盘）/ "
            "待确认 {pending} / 未识别 {unknown} / 已归档未变 {unchanged}".format(**counters),
        )
        if dry_run:
            append_log(run, "试运行结束：附件状态与落盘目录均未改动")
        else:
            recompute_case_statuses(db)
            append_log(run, f"落盘目录 archive_store 现有 {stored_file_count()} 个文件，案件状态已回写")
        run.status = RunStatus.SUCCEEDED.value
        audit_service.record(
            db,
            action=ACTION_RUN_EXECUTE,
            entity_type="archive_run",
            entity_id=run.id,
            detail={
                "run_no": run.run_no,
                "mode": source_mode,
                "scanned": run.scanned,
                "archived": run.archived,
                "duplicate": run.duplicate,
                "pending": run.pending,
                "unknown": run.unknown,
            },
        )
    except Exception as exc:  # noqa: BLE001 - 失败要落日志并让批次可见
        logger.error("run %s failed: %s", run.run_no, exc, exc_info=True)
        run.status = RunStatus.FAILED.value
        run.failed = counters["failed"] + 1
        append_log(run, f"批次执行失败：{exc}")
        audit_service.record(
            db,
            action=ACTION_RUN_FAILED,
            entity_type="archive_run",
            entity_id=run.id,
            detail={"run_no": run.run_no, "error": str(exc)[:300]},
        )
    finally:
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
    return run
