"""投件源读取服务：DB 读取器 + 覆盖台账持久化 + 移交阻断/版本/发布留痕。

与 source_coverage.py（纯函数规则）分工：
  - source_coverage 只负责判定规则与故障注入，不碰数据库；
  - 本模块负责从 attachments 表读取、写 run_source_reads / handover_publishes、算阻断案件。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import (
    ALL_SOURCE_CODES,
    SOURCE_FAILURE_LABELS,
    SOURCE_NAMES,
    SOURCE_READ_STATUS_LABELS,
)
from src.models.archive_run import ArchiveRun
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.models.handover_publish import HandoverPublish
from src.models.run_source_read import RunSourceRead
from src.services import source_coverage as cov


class DbSourceReader:
    """默认来源读取器：投件源已由采集侧落成 attachments 行，按 source_code 取回。

    演示环境不直连共享盘/IMAP，来源故障通过 SOURCE_FAULTS / SOURCE_FAULT_FILE 注入；
    真实部署把这里替换成目录扫描 / IMAP 拉取即可，超时时抛 SourceReadError(read_timeout)。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._cache: dict[str, list[Attachment]] = {}

    def read(self, source_code: str) -> list[Attachment]:
        # 同一批次内缓存：覆盖判定与后续归档复用同一份结果，不重复查库
        if source_code not in self._cache:
            self._cache[source_code] = (
                self.db.execute(
                    select(Attachment)
                    .where(Attachment.source_code == source_code)
                    .order_by(Attachment.scan_seq)
                )
                .scalars()
                .all()
            )
        return self._cache[source_code]


def load_faults() -> dict[str, cov.SourceReadError]:
    """读取当前进程的故障注入配置（env 优先，文件可在不重启的情况下切换）。"""
    from src.config.settings import settings

    environ = {
        cov.ENV_FAULTS: settings.source_faults,
        cov.ENV_FAULT_FILE: settings.source_fault_file,
    }
    return cov.load_fault_config(environ)


def read_sources(
    db: Session,
    run: ArchiveRun,
    *,
    only_sources: tuple[str, ...] | None = None,
) -> tuple[cov.CoverageSummary, dict[str, list[Attachment]]]:
    """读取指定来源并落 run_source_reads 行，返回覆盖汇总与「本来源 -> 附件」映射。

    only_sources 为 None 时读全部 3 个来源（首次批次）；
    补扫时只传失败来源，其他来源不重读、附件不触碰（未读到的材料不会被记成丢失）。
    """
    targets = tuple(code for code in ALL_SOURCE_CODES if only_sources is None or code in only_sources)
    reader = DbSourceReader(db)
    faults = load_faults()
    attachments_by_source: dict[str, list[Attachment]] = {}
    results: list[cov.SourceReadResult] = []

    for code in targets:
        result = cov.read_source(code, reader, faults=faults)
        results.append(result)
        row = RunSourceRead(
            run_id=run.id,
            root_run_id=run.root_run_id or run.id,
            source_code=code,
            status=result.status,
            read_count=result.read_count,
            failure_reason=result.failure_reason,
            failure_detail=result.failure_detail,
            duration_ms=result.duration_ms,
        )
        db.add(row)
        if result.status == cov.STATUS_COVERED:
            attachments_by_source[code] = reader.read(code)
        # 失败来源：不放入映射 -> 下游完全不处理，绝不产生「丢失」附件记录
    db.flush()

    # 补扫时把同一批次链上历史读取结果合并进汇总（之前已覆盖的来源保持 covered）
    summary = _merge_chain_coverage(db, run, results)
    return summary, attachments_by_source


def _merge_chain_coverage(
    db: Session,
    run: ArchiveRun,
    current_results: list[cov.SourceReadResult],
) -> cov.CoverageSummary:
    """合并同批次链所有 run_source_reads：每个来源取最新一行（本轮结果优先）。"""
    root_id = run.root_run_id or run.id
    rows = (
        db.execute(
            select(RunSourceRead).where(RunSourceRead.root_run_id == root_id)
        )
        .scalars()
        .all()
    )
    latest: dict[str, dict] = {}
    for row in rows:
        latest[row.source_code] = {
            "source_code": row.source_code,
            "status": row.status,
            "read_count": row.read_count,
            "failure_reason": row.failure_reason,
            "failure_detail": row.failure_detail,
            "duration_ms": row.duration_ms,
        }
    for result in current_results:
        latest[result.source_code] = result.to_dict()
    return cov.summarize(latest.values())


def chain_coverage(db: Session, run: ArchiveRun) -> cov.CoverageSummary:
    """批次链当前的来源覆盖汇总（供发布校验、工作台展示）。"""
    root_id = run.root_run_id or run.id
    rows = (
        db.execute(
            select(RunSourceRead).where(RunSourceRead.root_run_id == root_id)
        )
        .scalars()
        .all()
    )
    return cov.summarize(
        {
            "source_code": row.source_code,
            "status": row.status,
            "read_count": row.read_count,
            "failure_reason": row.failure_reason,
            "failure_detail": row.failure_detail,
            "duration_ms": row.duration_ms,
        }
        for row in rows
    )


def latest_root_run(db: Session, root_run_id) -> ArchiveRun | None:
    """批次链上最新的一个批次（补扫链可能有多个 run）。"""
    return (
        db.execute(
            select(ArchiveRun)
            .where(ArchiveRun.root_run_id == root_run_id)
            .order_by(ArchiveRun.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def latest_coverage_run(db: Session) -> ArchiveRun | None:
    """最近一条真正执行过来源读取（run_source_reads 有行）的批次。

    seed 中手工登记的历史失败批次没有读取行，不参与移交闸门，避免新环境在未跑批次时被死锁。
    """
    return (
        db.execute(
            select(ArchiveRun)
            .join(RunSourceRead, RunSourceRead.run_id == ArchiveRun.id)
            .order_by(ArchiveRun.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def blocked_case_nos(db: Session, summary: cov.CoverageSummary) -> set[str]:
    """材料来自未覆盖来源的案件号集合 —— 这些案件只是「暂时不能移交」，不算丢失、不改状态。"""
    failed = set(cov.failed_codes(summary)) | set(cov.pending_codes(summary))
    if not failed:
        return set()
    pairs = (
        db.execute(
            select(ClaimCase.case_no, Attachment.source_code)
            .join(Attachment, Attachment.case_id == ClaimCase.id)
            .where(Attachment.source_code.in_(tuple(failed)))
            .distinct()
        )
        .all()
    )
    return cov.handover_blocked_source_cases(failed, pairs)


def serialize_coverage(summary: cov.CoverageSummary) -> dict:
    """对外序列化：补中文标签与可读原因，工作台直接渲染。"""
    payload = summary.to_dict()
    payload["sources"] = [
        {
            **row,
            "name": SOURCE_NAMES.get(row["source_code"], row["source_code"]),
            "status_label": SOURCE_READ_STATUS_LABELS.get(row["status"], row["status"]),
            "failure_label": (
                SOURCE_FAILURE_LABELS.get(row["failure_reason"], row["failure_reason"])
                if row["failure_reason"]
                else ""
            ),
        }
        for row in payload["sources"]
    ]
    payload["failed_codes"] = list(cov.failed_codes(summary))
    payload["pending_codes"] = list(cov.pending_codes(summary))
    return payload


# ------------------------------------------------------------- 批次链版本 ----


def assign_chain_fields(db: Session, run: ArchiveRun, parent: ArchiveRun | None) -> None:
    """首次批次自成链根并取新版本号；补扫批次挂到同一根链、版本号保持一致。"""
    if parent is None:
        existing = db.execute(select(ArchiveRun.handover_version)).scalars().all()
        version = cov.next_handover_version(existing)
        run.root_run_id = run.id
        run.root_run_no = run.run_no
        run.handover_version = version
    else:
        root_id = parent.root_run_id or parent.id
        run.root_run_id = root_id
        run.root_run_no = parent.root_run_no or parent.run_no
        run.handover_version = cov.resume_keeps_version(parent.handover_version)


def ensure_publishable(db: Session, run: ArchiveRun) -> cov.CoverageSummary:
    """发布移交前硬闸门：来源未全部核对完成直接抛业务异常（409）。"""
    summary = chain_coverage(db, run)
    try:
        cov.assert_handover_publishable(summary)
    except cov.HandoverBlocked as exc:
        from src.constants import error_codes as codes
        from src.utils.errors import AppError

        blocked = sorted(blocked_case_nos(db, summary))
        raise AppError(
            codes.HANDOVER_BLOCKED,
            str(exc),
            f"root_run_no={run.root_run_no or run.run_no}; blocked_cases={len(blocked)}",
            extra={"blocked_case_nos": blocked[:100], "coverage": serialize_coverage(summary)},
        ) from exc
    return summary


def record_publish(
    db: Session,
    run: ArchiveRun,
    *,
    actor_email: str,
    file_name: str,
    row_count: int,
    byte_count: int,
) -> HandoverPublish:
    """记录一次移交发布（同链重试发布版本号不变，每次发布各留一行审计轨迹）。"""
    entry = HandoverPublish(
        root_run_id=run.root_run_id or run.id,
        root_run_no=run.root_run_no or run.run_no,
        handover_version=run.handover_version,
        run_id=run.id,
        run_no=run.run_no,
        triggered_by_email=actor_email,
        file_name=file_name,
        row_count=row_count,
        byte_count=byte_count,
    )
    db.add(entry)
    db.flush()
    return entry


def list_publishes(db: Session, root_run_id=None, limit: int = 20) -> list[dict]:
    stmt = select(HandoverPublish).order_by(HandoverPublish.created_at.desc()).limit(limit)
    if root_run_id is not None:
        stmt = select(HandoverPublish).where(HandoverPublish.root_run_id == root_run_id).order_by(
            HandoverPublish.created_at.desc()
        ).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": str(row.id),
            "root_run_id": str(row.root_run_id),
            "root_run_no": row.root_run_no,
            "handover_version": row.handover_version,
            "run_no": row.run_no,
            "triggered_by_email": row.triggered_by_email,
            "file_name": row.file_name,
            "row_count": row.row_count,
            "byte_count": row.byte_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
