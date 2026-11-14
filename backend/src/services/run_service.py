"""归档批次：创建、补扫（resume）、投递 Celery、序列化、列表。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import RUN_MODE_LABELS, RUN_STATUS_LABELS, RunMode, RunStatus
from src.constants.log_templates import ACTION_RUN_CREATE
from src.models.archive_run import ArchiveRun
from src.models.user import User
from src.services import archive_service, audit_service, rule_service, source_service
from src.services.source_coverage import STATUS_FAILED
from src.utils.errors import AppError
from src.utils.ids import as_uuid


def next_run_no(db: Session) -> str:
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"RUN-{today}-"
    count = (
        db.execute(select(ArchiveRun.run_no).where(ArchiveRun.run_no.like(prefix + "%"))).scalars().all()
    )
    return f"{prefix}{len(count) + 1:02d}"


def serialize(run: ArchiveRun, with_files: bool = False) -> dict:
    coverage = run.source_coverage or {}
    payload = {
        "id": str(run.id),
        "run_no": run.run_no,
        "mode": run.mode,
        "mode_label": RUN_MODE_LABELS.get(run.mode, run.mode),
        "status": run.status,
        "status_label": RUN_STATUS_LABELS.get(run.status, run.status),
        "rule_version": run.rule_version,
        "template_snapshot": run.template_snapshot,
        "triggered_by_email": run.triggered_by_email,
        "note": run.note,
        "root_run_id": str(run.root_run_id) if run.root_run_id else str(run.id),
        "root_run_no": run.root_run_no or run.run_no,
        "handover_version": run.handover_version,
        "source_coverage": coverage,
        "all_sources_covered": bool(coverage.get("all_covered", False)),
        "scanned": run.scanned,
        "new_files": run.new_files,
        "archived": run.archived,
        "duplicate": run.duplicate,
        "pending": run.pending,
        "unknown": run.unknown,
        "unchanged": run.unchanged,
        "failed": run.failed,
        "manual": run.manual,
        "auto_named": run.archived + run.duplicate,
        "log": list(run.log or []),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_ms": run.duration_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
    if with_files:
        payload["stored_files"] = archive_service.stored_file_count()
    return payload


def list_runs(db: Session, limit: int = 20) -> dict:
    runs = (
        db.execute(select(ArchiveRun).order_by(ArchiveRun.created_at.desc()).limit(limit)).scalars().all()
    )
    return {
        "items": [serialize(run) for run in runs],
        "stored_files": archive_service.stored_file_count(),
        "active": next(
            (serialize(run) for run in runs if run.status in (RunStatus.QUEUED.value, RunStatus.RUNNING.value)),
            None,
        ),
    }


def get_run(db: Session, run_id: str) -> dict:
    uid = as_uuid(run_id)
    run = db.get(ArchiveRun, uid) if uid else None
    if run is None:
        raise AppError(codes.NOT_FOUND, "批次不存在", f"run_id={run_id}")
    payload = serialize(run, with_files=True)
    # 以批次链实时覆盖为准（补扫后老批次的快照也能反映最新覆盖）
    payload["chain_coverage"] = source_service.serialize_coverage(source_service.chain_coverage(db, run))
    payload["publishes"] = source_service.list_publishes(db, root_run_id=run.root_run_id or run.id)
    return payload


def latest_run(db: Session) -> ArchiveRun | None:
    return db.execute(select(ArchiveRun).order_by(ArchiveRun.created_at.desc()).limit(1)).scalars().first()


def _assert_no_busy_run(db: Session) -> None:
    busy = (
        db.execute(
            select(ArchiveRun).where(ArchiveRun.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]))
        )
        .scalars()
        .first()
    )
    if busy is not None:
        raise AppError(codes.RUN_BUSY, "已有批次正在执行，请稍后再发起", f"run_no={busy.run_no}")


def create_run(db: Session, user: User, mode: str, note: str) -> dict:
    if mode not in (RunMode.DRY_RUN.value, RunMode.ARCHIVE.value):
        raise AppError(codes.VALIDATION_ERROR, "批次模式不合法", f"mode={mode}")
    _assert_no_busy_run(db)

    rule = rule_service.get_active(db)
    run = ArchiveRun(
        run_no=next_run_no(db),
        mode=mode,
        status=RunStatus.QUEUED.value,
        rule_version=rule.version,
        template_snapshot=rule.template,
        triggered_by_email=user.email,
        note=(note or "").strip()[:240],
    )
    db.add(run)
    db.flush()
    # 首次批次自成链根，分配新的移交版本号
    source_service.assign_chain_fields(db, run, None)
    audit_service.record(
        db,
        action=ACTION_RUN_CREATE,
        actor=user,
        entity_type="archive_run",
        entity_id=run.id,
        detail={
            "run_no": run.run_no,
            "mode": mode,
            "rule_version": rule.version,
            "root_run_no": run.root_run_no,
            "handover_version": run.handover_version,
        },
    )
    db.commit()

    _dispatch(db, run, mode=mode, only_sources=None)
    return get_run(db, str(run.id))


def resume_run(db: Session, user: User, run_id: str, note: str = "") -> dict:
    """来源恢复后的补扫：只重读失败来源，挂到同一批次链，移交版本号保持一致。"""
    _assert_no_busy_run(db)
    uid = as_uuid(run_id)
    parent = db.get(ArchiveRun, uid) if uid else None
    if parent is None:
        raise AppError(codes.NOT_FOUND, "批次不存在", f"run_id={run_id}")

    coverage = source_service.chain_coverage(db, parent)
    failed = tuple(
        row["source_code"] for row in coverage.sources if row["status"] == STATUS_FAILED
    )
    if not failed:
        raise AppError(
            codes.RUN_NOT_RESUMABLE,
            "该批次没有读取失败的投件源，全部来源已覆盖，无需补扫",
            f"run_no={parent.run_no}",
        )

    rule = rule_service.get_active(db)
    run = ArchiveRun(
        run_no=next_run_no(db),
        mode=RunMode.ARCHIVE.value,
        status=RunStatus.QUEUED.value,
        rule_version=rule.version,
        template_snapshot=parent.template_snapshot,
        triggered_by_email=user.email,
        note=(note or f"来源恢复补扫：{ '、'.join(failed) }")[:240],
    )
    db.add(run)
    db.flush()
    # 挂到同一根批次链，移交版本号不变
    source_service.assign_chain_fields(db, run, parent)
    audit_service.record(
        db,
        action=ACTION_RUN_CREATE,
        actor=user,
        entity_type="archive_run",
        entity_id=run.id,
        detail={
            "run_no": run.run_no,
            "mode": RunMode.ARCHIVE.value,
            "resume_of": parent.run_no,
            "root_run_no": run.root_run_no,
            "handover_version": run.handover_version,
            "only_sources": list(failed),
        },
    )
    db.commit()

    _dispatch(db, run, mode=RunMode.ARCHIVE.value, only_sources=failed)
    return get_run(db, str(run.id))


def _dispatch(
    db: Session,
    run: ArchiveRun,
    *,
    mode: str,
    only_sources: tuple[str, ...] | None,
) -> None:
    dispatched = False
    try:
        from src.config.celery_app import TASK_ARCHIVE_RUN, celery_app

        celery_app.send_task(
            TASK_ARCHIVE_RUN,
            args=[str(run.id)],
            kwargs={"mode": mode, "only_sources": list(only_sources) if only_sources else None},
        )
        dispatched = True
    except Exception as exc:  # noqa: BLE001 - broker 不可用时退化为进程内执行
        archive_service.append_log(run, f"Celery 投递失败（{exc}），改在 API 进程内同步执行")
        db.commit()

    if not dispatched:
        archive_service.execute_run(db, run, mode=mode, only_sources=only_sources)
