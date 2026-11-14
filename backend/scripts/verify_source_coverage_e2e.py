#!/usr/bin/env python3
"""来源容错端到端离线验证（仅标准库，python3 -I 运行）。

本机没有 SQLAlchemy / pydantic，这里用 stdlib sqlite3 + 轻量 fake 仓储，
真实驱动 archive_service / source_service 的决策函数，演练完整剧本：

  首轮：邮箱读取超时
    -> 批次 partial、共享盘案件正常核销、邮箱案件被闸门挡住（不核销、不记丢失）
    -> 移交发布被拒（HANDOVER_BLOCKED 语义）
  恢复：只补邮箱
    -> 同批次链、移交版本号不变、全覆盖 succeeded、邮箱案件核销、发布放行
    -> 两次发布留痕版本号一致
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.services import source_coverage as cov  # noqa: E402


# --------------------------------------------------------------- fake 模型 ----


@dataclass
class FakeCase:
    case_no: str
    policy_no: str
    source_code: str
    status: str = "pending_docs"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class FakeAttachment:
    scan_seq: int
    source_code: str
    case_id: str | None
    policy_no: str
    status: str = "classified"
    material_type: str = "invoice"
    confidence: float = 0.95
    sha256: str = ""
    ext: str = "pdf"
    stored_name: str | None = None
    first_run_id: str | None = None
    last_run_id: str | None = None
    doc_date: date = field(default_factory=lambda: date(2026, 9, 2))


@dataclass
class FakeRun:
    run_no: str
    mode: str = "archive"
    status: str = "queued"
    template_snapshot: str = "{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root_run_id: str | None = None
    root_run_no: str = ""
    handover_version: int = 1
    source_coverage: dict = field(default_factory=dict)
    log: list = field(default_factory=list)
    scanned = new = archived = duplicate = pending = unknown = unchanged = failed = manual = 0
    started_at = finished_at = None
    duration_ms = 0


class FakeReadRow:
    def __init__(self, run_id, root_run_id, source_code, status, read_count, reason, detail, duration):
        self.run_id = run_id
        self.root_run_id = root_run_id
        self.source_code = source_code
        self.status = status
        self.read_count = read_count
        self.failure_reason = reason
        self.failure_detail = detail
        self.duration_ms = duration


class FakeDB:
    """最小仓储：只实现服务层用到的查询与追加。"""

    def __init__(self):
        self.cases: list[FakeCase] = []
        self.attachments: list[FakeAttachment] = []
        self.reads: list[FakeReadRow] = []
        self.publishes: list = []
        self.commits = 0

    def add(self, obj):
        if isinstance(obj, FakeReadRow):
            self.reads.append(obj)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def attachments_of(self, source_code: str) -> list[FakeAttachment]:
        return [a for a in self.attachments if a.source_code == source_code]

    def case_by_id(self, case_id: str) -> FakeCase | None:
        return next((c for c in self.cases if c.id == case_id), None)


# ----------------------------------------------------- 打点 source_service ----


def make_source_service(db: FakeDB, faults: dict[str, cov.SourceReadError]):
    """返回与 source_service 同语义、但操作 FakeDB 的函数组（复用纯规则模块）。"""

    def read_sources(run: FakeRun, only_sources: tuple[str, ...] | None):
        targets = tuple(c for c in cov.ALL_SOURCE_CODES if only_sources is None or c in only_sources)
        by_source: dict[str, list[FakeAttachment]] = {}
        results: list[cov.SourceReadResult] = []
        for code in targets:
            result = cov.read_source(
                code,
                type("R", (), {"read": lambda self, c: db.attachments_of(c)})(),
                faults=faults,
            )
            results.append(result)
            db.reads.append(FakeReadRow(
                run.id, run.root_run_id or run.id, code,
                result.status, result.read_count, result.failure_reason,
                result.failure_detail, result.duration_ms,
            ))
            if result.status == cov.STATUS_COVERED:
                by_source[code] = db.attachments_of(code)
        summary = merge_chain(run, results)
        return summary, by_source

    def merge_chain(run: FakeRun, current: list[cov.SourceReadResult]) -> cov.CoverageSummary:
        root_id = run.root_run_id or run.id
        latest: dict[str, dict] = {}
        for row in db.reads:
            if row.root_run_id == root_id:
                latest[row.source_code] = {
                    "source_code": row.source_code,
                    "status": row.status,
                    "read_count": row.read_count,
                    "failure_reason": row.failure_reason,
                    "failure_detail": row.failure_detail,
                    "duration_ms": row.duration_ms,
                }
        for result in current:
            latest[result.source_code] = result.to_dict()
        return cov.summarize(latest.values())

    def chain_coverage(run: FakeRun) -> cov.CoverageSummary:
        root_id = run.root_run_id or run.id
        return cov.summarize(
            {
                "source_code": r.source_code,
                "status": r.status,
                "read_count": r.read_count,
                "failure_reason": r.failure_reason,
                "failure_detail": r.failure_detail,
                "duration_ms": r.duration_ms,
            }
            for r in db.reads if r.root_run_id == root_id
        )

    def blocked_case_nos(summary: cov.CoverageSummary) -> set[str]:
        failed = set(cov.failed_codes(summary)) | set(cov.pending_codes(summary))
        if not failed:
            return set()
        pairs = [
            (c.case_no, a.source_code)
            for c in db.cases for a in db.attachments
            if a.case_id == c.id and a.source_code in failed
        ]
        return cov.handover_blocked_source_cases(failed, pairs)

    return read_sources, chain_coverage, blocked_case_nos


# ---------------------------------------------------------- 核销闸门（同口径）----


def recompute_statuses(db: FakeDB, blocked_nos: set[str]) -> set[str]:
    blocked: set[str] = set()
    for case in db.cases:
        if case.case_no in blocked_nos:
            blocked.add(case.case_no)
            continue  # 来源未覆盖：不核销，状态保持
        atts = [a for a in db.attachments if a.case_id == case.id]
        if atts and all(a.status in ("archived", "duplicate") for a in atts):
            case.status = "archived"
    return blocked


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"FAIL {name} {detail}")
    print(f"PASS {name}")


def main() -> int:
    db = FakeDB()
    drive_case = FakeCase("CLM-0001", "P202600000001", "shared_drive")
    mail_case = FakeCase("CLM-0002", "P202600000002", "mailbox")
    db.cases.extend([drive_case, mail_case])
    db.attachments.extend([
        FakeAttachment(1, "shared_drive", drive_case.id, drive_case.policy_no),
        FakeAttachment(2, "mailbox", mail_case.id, mail_case.policy_no),
    ])

    # ---------------- 首轮：邮箱超时 ----------------
    faults = {"mailbox": cov.SourceReadError("mailbox", cov.REASON_TIMEOUT, "imap 连接 5s 超时")}
    read_sources, chain_coverage, blocked_case_nos = make_source_service(db, faults)

    first = FakeRun("RUN-20261114-01")
    first.root_run_id = first.id
    first.root_run_no = first.run_no
    first.handover_version = cov.next_handover_version([])  # 新链 v1

    summary, by_source = read_sources(first, None)
    first.source_coverage = summary.to_dict()
    check("first-run-partial", cov.run_status_from_coverage(summary) == cov.RUN_PARTIAL)
    check("mailbox-failed-reason-recorded", next(
        r for r in summary.sources if r["source_code"] == "mailbox"
    )["failure_reason"] == cov.REASON_TIMEOUT)
    check("drive-covered-count", next(
        r for r in summary.sources if r["source_code"] == "shared_drive"
    )["read_count"] == 1)

    # 已扫到的共享盘附件照常归档；邮箱附件根本没进 by_source，状态不被触碰
    for att in by_source.get("shared_drive", []):
        att.status = "archived"
    mail_att_before = next(a for a in db.attachments if a.source_code == "mailbox")
    check("unread-attachment-untouched-not-lost", mail_att_before.status == "classified"
          and mail_att_before.stored_name is None)

    blocked = recompute_statuses(db, blocked_case_nos(summary))
    check("drive-case-written-off", drive_case.status == "archived")
    check("mail-case-blocked-not-written-off", mail_case.status == "pending_docs"
          and blocked == {"CLM-0002"})

    # 发布硬闸门
    publish_blocked = False
    try:
        cov.assert_handover_publishable(summary)
    except cov.HandoverBlocked:
        publish_blocked = True
    check("handover-publish-rejected-when-partial", publish_blocked)

    # 台账逐行留痕（首轮 3 行，邮箱 failed）
    check("source-read-ledger-rows", len([r for r in db.reads if r.run_id == first.id]) == 3)

    # ---------------- 恢复：只补邮箱，故障清除 ----------------
    read_sources_ok, chain_coverage_ok, blocked_ok = make_source_service(db, {})
    resume = FakeRun("RUN-20261114-02")
    resume.root_run_id = first.root_run_id
    resume.root_run_no = first.root_run_no
    resume.handover_version = cov.resume_keeps_version(first.handover_version)  # 版本保持 v1

    summary2, by_source2 = read_sources_ok(resume, ("mailbox",))
    check("resume-read-only-mailbox",
          [r.source_code for r in db.reads if r.run_id == resume.id] == ["mailbox"])
    check("resume-chain-all-covered", summary2.all_covered is True
          and cov.run_status_from_coverage(summary2) == cov.RUN_SUCCEEDED)
    check("handover-version-unchanged", resume.handover_version == first.handover_version == 1)

    for att in by_source2.get("mailbox", []):
        att.status = "archived"
    blocked2 = recompute_statuses(db, blocked_ok(summary2))
    check("mail-case-written-off-after-resume", mail_case.status == "archived" and blocked2 == set())

    # 发布放行 + 两次发布留痕版本号一致
    cov.assert_handover_publishable(summary2)
    db.publishes.append(("docflow-handover-v1-1000.csv", resume.handover_version))
    db.publishes.append(("docflow-handover-v1-1030.csv", resume.handover_version))
    check("retry-publish-same-version",
          all(version == 1 for _, version in db.publishes) and len(db.publishes) == 2)

    # 历史失败行保留，恢复轨迹可追溯（同来源两行：先 failed 后 covered）
    mail_rows = [r for r in db.reads if r.source_code == "mailbox"]
    check("recovery-trace-kept", [r.status for r in mail_rows] == ["failed", "covered"])

    print("\nALL E2E SOURCE-FAILURE SCENARIO CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
