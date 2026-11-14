"""归档批次执行：按投件源读取 -> 分类复核 -> 命名归一 -> 落盘/重复标记 -> 案件状态回写。

来源容错口径（本文件是需求的核心落点）：
  - 每个投件源（共享盘/邮箱/移动盘）单独读取并写 run_source_reads，读取超时/不可达只让该来源
    记 failed，批次按已扫到的部分继续处理，整体状态置为 partial（全失败才 failed）；
  - 来源未全部覆盖时，材料来自失败来源的案件不得核销为「已归档」，移交清单发布在导出层硬拦截；
  - 失败来源的附件不会被读到，因此不产生任何附件行，更不会记成「丢失」；
  - 补扫（resume）只重读失败来源，已覆盖来源的附件原样不动；
  - 已 archived 的附件再跑只计入 unchanged，不重复落盘、不改名；已 duplicate 再跑仍计 duplicate；
  - 试运行（dry_run）只统计，不写附件字段、不写磁盘（来源覆盖台账仍如实记录）。
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
from src.services import audit_service, source_service
from src.services.naming_engine import plan_target
from src.services.source_coverage import CoverageSummary
from src.utils.logger import get_logger
from src.utils.textutils import now_stamp

logger = get_logger("docflow.archive")
LOG_LIMIT = 120


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


def recompute_case_statuses(db: Session, blocked_case_nos: set[str] | None = None) -> set[str]:
    """回写案件状态，返回本轮被「来源未覆盖」挡住核销的案件号集合。

    核销闸门：案件只要有材料来自未覆盖来源，就保持原状（通常是待收件/异常），
    不允许在来源没核对完时被算成「已交齐」。
    """
    blocked_case_nos = blocked_case_nos or set()
    grouped: dict[str, list[Attachment]] = {}
    for att in db.execute(select(Attachment)).scalars().all():
        if att.case_id is None:
            continue
        grouped.setdefault(str(att.case_id), []).append(att)
    blocked: set[str] = set()
    for case in db.execute(select(ClaimCase)).scalars().all():
        if case.case_no in blocked_case_nos:
            # 未覆盖来源未核对完：不核销，维持当前状态，仅在返回集合里标记给工作台
            blocked.add(case.case_no)
            continue
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
    return blocked


def _source_tally(attachments: list[Attachment]) -> str:
    tally: dict[str, int] = {}
    for att in attachments:
        tally[att.source_code] = tally.get(att.source_code, 0) + 1
    order = ("shared_drive", "mailbox", "portable")
    labels = {"shared_drive": "共享盘", "mailbox": "邮箱", "portable": "移动盘"}
    return " / ".join(f"{labels.get(code, code)} {tally.get(code, 0)}" for code in order)


def _log_coverage(run: ArchiveRun, summary: CoverageSummary) -> None:
    from src.constants.enums import SOURCE_FAILURE_LABELS, SOURCE_NAMES, SOURCE_READ_STATUS_LABELS

    for row in summary.sources:
        name = SOURCE_NAMES.get(row["source_code"], row["source_code"])
        if row["status"] == "covered":
            append_log(run, f"来源 {name} 读取成功：覆盖 {row['read_count']} 件（{row['duration_ms']} ms）")
        elif row["status"] == "failed":
            reason = SOURCE_FAILURE_LABELS.get(row["failure_reason"], row["failure_reason"])
            append_log(
                run,
                f"来源 {name} 读取失败：{reason}｜{row['failure_detail'] or '无补充信息'}"
                f"（该来源本轮未覆盖，材料不计丢失，恢复后只补本来源）",
            )
        else:
            append_log(run, f"来源 {name} 本轮未读取（{SOURCE_READ_STATUS_LABELS.get(row['status'], row['status'])}）")
    if summary.all_covered:
        append_log(run, "三个投件源已全部核对完成，案件核销与移交发布闸门放行")
    else:
        failed = "、".join(
            SOURCE_NAMES.get(row["source_code"], row["source_code"])
            for row in summary.sources
            if row["status"] == "failed"
        )
        append_log(
            run,
            f"投件源未全部核对完成（失败：{failed or '无'}）：相关案件暂不核销、移交清单暂不能发布",
        )


def execute_run(
    db: Session,
    run: ArchiveRun,
    mode: str | None = None,
    *,
    only_sources: tuple[str, ...] | None = None,
) -> ArchiveRun:
    """执行批次。only_sources=None 读全部来源；补扫时只传失败来源。"""
    source_mode = (mode or run.mode or RunMode.ARCHIVE.value).strip()
    dry_run = source_mode == RunMode.DRY_RUN.value
    resumed = only_sources is not None
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
        # 1) 逐来源读取（失败只影响该来源，不炸整批），并落 run_source_reads 台账
        summary, attachments_by_source = source_service.read_sources(db, run, only_sources=only_sources)
        run.source_coverage = source_service.serialize_coverage(summary)
        scope_label = "补扫来源 " + "、".join(only_sources) if resumed else "全部投件源"
        append_log(run, f"开始读取{scope_label}（试运行={str(dry_run).lower()}）")
        _log_coverage(run, summary)

        attachments = [att for code in summary.sources for att in attachments_by_source.get(code["source_code"], [])]
        attachments.sort(key=lambda att: att.scan_seq)
        cases = {str(case.id): case for case in db.execute(select(ClaimCase)).scalars().all()}
        used, owners = build_name_maps(db)
        counters["scanned"] = len(attachments)
        append_log(run, f"本轮实际扫描 {_source_tally(attachments)}，共 {len(attachments)} 件")
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

        # 2) 来源覆盖决定批次状态与案件核销闸门
        blocked_nos = source_service.blocked_case_nos(db, summary)
        if dry_run:
            # 试运行不落盘、不改附件与案件状态，只把闸门预演结果写进日志
            if blocked_nos:
                append_log(
                    run,
                    f"试运行预演：{len(blocked_nos)} 个案件在正式归档时会被核销闸门拦截"
                    "（材料来自未覆盖来源，暂时不能移交）",
                )
            append_log(run, "试运行结束：附件状态与落盘目录均未改动；来源覆盖台账已记录")
        else:
            blocked = recompute_case_statuses(db, blocked_nos)
            if blocked:
                append_log(
                    run,
                    f"核销闸门拦截 {len(blocked)} 个案件（材料来自未覆盖来源，暂时不能移交，状态不改写）",
                )
            append_log(run, f"落盘目录 archive_store 现有 {stored_file_count()} 个文件，案件状态已按覆盖结果回写")

        run.status = _status_from_coverage(summary)
        if run.status == RunStatus.PARTIAL.value:
            append_log(run, "批次按已扫到的部分结束：状态置为 partial，待来源恢复后发起补扫")
        run.source_coverage = source_service.serialize_coverage(summary)
        audit_service.record(
            db,
            action=ACTION_RUN_EXECUTE,
            entity_type="archive_run",
            entity_id=run.id,
            detail={
                "run_no": run.run_no,
                "mode": source_mode,
                "resumed": resumed,
                "scanned": run.scanned,
                "archived": run.archived,
                "duplicate": run.duplicate,
                "pending": run.pending,
                "unknown": run.unknown,
                "coverage": summary.to_dict(),
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


def _status_from_coverage(summary: CoverageSummary) -> str:
    """覆盖汇总 -> 批次状态：全覆盖 succeeded / 部分 partial / 全失败 failed。"""
    from src.services import source_coverage as cov

    mapping = {
        cov.RUN_SUCCEEDED: RunStatus.SUCCEEDED.value,
        cov.RUN_PARTIAL: RunStatus.PARTIAL.value,
        cov.RUN_FAILED: RunStatus.FAILED.value,
    }
    return mapping[cov.run_status_from_coverage(summary)]
