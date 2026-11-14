"""来源容错端到端（SQLAlchemy + SQLite 内存库）：核销闸门 / 补扫 / 发布拦截 / 版本一致。

运行环境：容器或装好 requirements.txt 的开发机（pytest）。
本机若无 SQLAlchemy 会自动 skip；同口径的纯 stdlib 验证见 scripts/verify_source_coverage_e2e.py。
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic")

from datetime import date  # noqa: E402

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.constants.enums import AttachmentStatus, CaseStatus, RunMode, RunStatus  # noqa: E402
from src.models import Base  # noqa: E402
from src.models.archive_run import ArchiveRun  # noqa: E402
from src.models.attachment import Attachment  # noqa: E402
from src.models.claim_case import ClaimCase  # noqa: E402
from src.services import archive_service, source_service  # noqa: E402
from src.utils.errors import AppError  # noqa: E402


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    # SQLite 不支持 PostgreSQL schema：测试内把表临时建到默认命名空间
    # （仅本测试模块使用；CI 若接 PostgreSQL 可改回带 schema 的引擎）
    original_schemas = {table.name: table.schema for table in Base.metadata.sorted_tables}
    original_meta_schema = Base.metadata.schema
    for table in Base.metadata.sorted_tables:
        table.schema = None
    Base.metadata.schema = None
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()

    # 故障注入：邮箱读取超时
    monkeypatch.setattr(
        source_service,
        "load_faults",
        lambda: {"mailbox": source_service.cov.SourceReadError(
            "mailbox", source_service.cov.REASON_TIMEOUT, "imap 5s 超时"
        )},
    )
    yield session
    session.close()
    engine.dispose()
    for table in Base.metadata.sorted_tables:
        table.schema = original_schemas[table.name]
    Base.metadata.schema = original_meta_schema


def _make_case(db, case_no: str, source: str) -> ClaimCase:
    case = ClaimCase(
        case_no=case_no,
        policy_no=f"P2026{case_no[-4:]}000000",
        customer_name="测试客户",
        insurance_type="medical",
        status=CaseStatus.PENDING_DOCS.value,
        channel=source,
        assignee="林嘉",
        incident_date=date(2026, 9, 1),
    )
    db.add(case)
    db.flush()
    return case


def _make_attachment(db, case: ClaimCase | None, source: str, seq: int, *, status: str) -> Attachment:
    att = Attachment(
        case_id=case.id if case else None,
        scan_seq=seq,
        source_code=source,
        original_name=f"发票_{seq}.pdf",
        material_type="invoice",
        confidence=0.95,
        status=status,
        sha256=f"sha-{seq}",
        ext="pdf",
        policy_no=case.policy_no if case else "",
        doc_date=date(2026, 9, 2),
    )
    db.add(att)
    db.flush()
    return att


def _new_run(db) -> ArchiveRun:
    run = ArchiveRun(
        run_no="RUN-T-01",
        mode=RunMode.ARCHIVE.value,
        status="queued",
        template_snapshot="{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}",
    )
    db.add(run)
    db.flush()
    source_service.assign_chain_fields(db, run, None)
    db.commit()
    return run


def test_partial_run_blocks_case_writeoff_and_handover(db_session, monkeypatch):
    db = db_session
    drive_case = _make_case(db, "CLM-0001", "shared_drive")
    mail_case = _make_case(db, "CLM-0002", "mailbox")
    _make_attachment(db, drive_case, "shared_drive", 1, status=AttachmentStatus.CLASSIFIED.value)
    _make_attachment(db, mail_case, "mailbox", 2, status=AttachmentStatus.CLASSIFIED.value)
    db.commit()

    run = _new_run(db)
    archive_service.execute_run(db, run, mode=RunMode.ARCHIVE.value)

    # 批次状态 partial，覆盖台账记录邮箱失败原因
    assert run.status == RunStatus.PARTIAL.value
    coverage = source_service.chain_coverage(db, run)
    assert coverage.failed_sources == 1
    mail_row = next(row for row in coverage.sources if row["source_code"] == "mailbox")
    assert mail_row["status"] == "failed"
    assert mail_row["failure_reason"] == "read_timeout"

    # 共享盘案件正常核销；邮箱案件因来源未覆盖不得核销
    db.refresh(drive_case)
    db.refresh(mail_case)
    assert drive_case.status == CaseStatus.ARCHIVED.value
    assert mail_case.status == CaseStatus.PENDING_DOCS.value
    assert source_service.blocked_case_nos(db, coverage) == {"CLM-0002"}

    # 移交发布被硬拦截
    with pytest.raises(AppError) as exc:
        source_service.ensure_publishable(db, run)
    assert exc.value.code == "HANDOVER_BLOCKED"


def test_resume_only_reads_failed_source_and_unblocks_with_same_version(db_session, monkeypatch):
    db = db_session
    drive_case = _make_case(db, "CLM-0001", "shared_drive")
    mail_case = _make_case(db, "CLM-0002", "mailbox")
    _make_attachment(db, drive_case, "shared_drive", 1, status=AttachmentStatus.CLASSIFIED.value)
    _make_attachment(db, mail_case, "mailbox", 2, status=AttachmentStatus.CLASSIFIED.value)
    db.commit()

    first = _new_run(db)
    archive_service.execute_run(db, first, mode=RunMode.ARCHIVE.value)
    assert first.status == RunStatus.PARTIAL.value
    first_version = first.handover_version

    # 来源恢复：清除故障并补扫，只重读邮箱
    monkeypatch.setattr(source_service, "load_faults", lambda: {})
    resume = ArchiveRun(
        run_no="RUN-T-02",
        mode=RunMode.ARCHIVE.value,
        status="queued",
        template_snapshot=first.template_snapshot,
    )
    db.add(resume)
    db.flush()
    source_service.assign_chain_fields(db, resume, first)
    db.commit()
    archive_service.execute_run(db, resume, only_sources=("mailbox",))

    assert resume.root_run_id == first.root_run_id
    assert resume.handover_version == first_version  # 同链版本保持一致
    assert resume.status == RunStatus.SUCCEEDED.value
    coverage = source_service.chain_coverage(db, resume)
    assert coverage.all_covered is True

    db.refresh(mail_case)
    assert mail_case.status == CaseStatus.ARCHIVED.value  # 闸门放行后正常核销
    source_service.ensure_publishable(db, resume)  # 不再抛异常


def test_resume_without_failure_is_rejected(db_session, monkeypatch):
    db = db_session
    run = _new_run(db)
    # 无故障跑一次全覆盖
    monkeypatch.setattr(source_service, "load_faults", lambda: {})
    archive_service.execute_run(db, run, mode=RunMode.ARCHIVE.value)
    assert run.status == RunStatus.SUCCEEDED.value

    from src.models.user import User
    from src.services.run_service import resume_run

    actor = User(email="analyst@docflow.io", display_name="林嘉", role="analyst")
    with pytest.raises(AppError) as exc:
        resume_run(db, actor, str(run.id))
    assert exc.value.code == "RUN_NOT_RESUMABLE"


def test_publish_records_keep_same_version_across_retries(db_session, monkeypatch):
    db = db_session
    run = _new_run(db)
    monkeypatch.setattr(source_service, "load_faults", lambda: {})
    archive_service.execute_run(db, run, mode=RunMode.ARCHIVE.value)
    source_service.ensure_publishable(db, run)

    first = source_service.record_publish(
        db, run, actor_email="a@x.io", file_name="f1.csv", row_count=2, byte_count=100
    )
    second = source_service.record_publish(
        db, run, actor_email="a@x.io", file_name="f2.csv", row_count=2, byte_count=100
    )
    assert first.handover_version == second.handover_version == run.handover_version
    # 发布记录按批次链隔离，只返回当前链的两条
    rows = source_service.list_publishes(db, root_run_id=run.root_run_id or run.id)
    assert len(rows) == 2
    assert {row["handover_version"] for row in rows} == {run.handover_version}


def test_latest_coverage_run_ignores_runs_without_source_reads(db_session, monkeypatch):
    db = db_session
    # 没有任何读取行的批次（模拟 seed 手工登记的历史失败批次）不应被当作闸门依据
    ghost = ArchiveRun(
        run_no="RUN-GHOST",
        mode=RunMode.ARCHIVE.value,
        status=RunStatus.FAILED.value,
        template_snapshot="{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}",
    )
    db.add(ghost)
    db.flush()
    source_service.assign_chain_fields(db, ghost, None)
    db.commit()
    assert source_service.latest_coverage_run(db) is None

    # 真正执行过来源读取后，该批次成为闸门依据
    run = _new_run(db)
    monkeypatch.setattr(source_service, "load_faults", lambda: {})
    archive_service.execute_run(db, run, mode=RunMode.ARCHIVE.value)
    assert source_service.latest_coverage_run(db) is not None
    source_service.ensure_publishable(db, run)  # 全覆盖放行


def test_export_service_blocks_when_no_coverage_run(db_session):
    from src.services import export_service
    from src.utils.errors import AppError

    with pytest.raises(AppError) as exc:
        export_service.handover_csv(db_session)
    assert exc.value.code == "RUN_NOT_READY"
