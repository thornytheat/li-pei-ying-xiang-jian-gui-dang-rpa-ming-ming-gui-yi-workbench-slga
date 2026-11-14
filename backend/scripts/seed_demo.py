"""幂等演示数据入口：`python -m scripts.seed_demo`（容器启动 SEED_DEMO=true 自动跑一次）。

自然键：
  User.email / ClaimCase.case_no / Attachment.scan_seq / NamingRule.version / ArchiveRun.run_no

首次结果：
  3 账号 / 1 条命名规则 v1 / 60 案件 / 210 附件 / 2 个历史批次（1 次试运行 + 1 次失败）
  - 210 件里 9 件是重复投递（同案件同 SHA-256）、7 件低置信待确认、4 件未识别；
  - 附件已按算法 1 完成分类落库（status=classified/pending/unknown），命名与落盘留给正式批次。

末尾 SEED_SUMMARY 行的 7 个键名与顺序是批次契约，两次执行必须逐字一致：
  SEED_SUMMARY brand=docflow cases=60 attachments=210 duplicates=9 pending=7 rules=1 users=3
其中 duplicates 用「同案件同 SHA-256 的多余份数」口径、pending 用 match_detail.initial_status='
pending' 口径，两者都不随批次执行变化，因此正式归档后再跑 seed 也能得到同一行。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from src.config.database import session_scope
from src.constants.enums import RunMode, RunStatus
from src.models.archive_run import ArchiveRun
from src.models.attachment import Attachment
from src.models.claim_case import ClaimCase
from src.models.naming_rule import NamingRule
from src.models.user import User
from src.services import archive_service
from src.services.material_classifier import classify
from src.utils.password import hash_password
from scripts import fixtures

CREATED = 0
SKIPPED = 0
LABEL = "docflow"
SEED_DRY_RUN_NO = "RUN-20261111-01"
SEED_FAILED_RUN_NO = "RUN-20261111-02"
SEED_STAMP = datetime(2026, 11, 11, 9, 12, 4, tzinfo=timezone.utc)
EXPECTED_SUMMARY = {
    "brand": LABEL,
    "cases": 60,
    "attachments": 210,
    "duplicates": 9,
    "pending": 7,
    "rules": 1,
    "users": 3,
}


def _log(kind: str, entity: str, key: str) -> None:
    global CREATED, SKIPPED
    if kind == "SEED_CREATED":
        CREATED += 1
    else:
        SKIPPED += 1
    print(f"{kind} entity={entity} key={key}", flush=True)


def _created(entity: str, key: str) -> None:
    _log("SEED_CREATED", entity, key)


def _skipped(entity: str, key: str) -> None:
    _log("SEED_SKIPPED", entity, key)


# ------------------------------------------------------------------ 账号 ----


def seed_users(db) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, display_name, role in fixtures.DEMO_USERS:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(fixtures.DEMO_PASSWORD),
                display_name=display_name,
                role=role,
                is_active=True,
            )
            db.add(user)
            db.flush()
            _created("User", email)
        else:
            _skipped("User", email)
        users[role] = user
    return users


# ------------------------------------------------------------------ 规则 ----


def seed_rule(db) -> NamingRule:
    spec = fixtures.RULE_V1
    rule = db.execute(select(NamingRule).where(NamingRule.version == spec["version"])).scalars().first()
    if rule is None:
        rule = NamingRule(
            version=spec["version"],
            template=spec["template"],
            conflict_policy=spec["conflict_policy"],
            date_source=spec["date_source"],
            is_active=True,
            note=spec["note"],
            created_by_email="admin@docflow.io",
        )
        db.add(rule)
        db.flush()
        _created("NamingRule", f"v{spec['version']}")
    else:
        _skipped("NamingRule", f"v{spec['version']}")
    return rule


# ------------------------------------------------------------------ 案件 ----


def seed_cases(db) -> dict[int, ClaimCase]:
    cases: dict[int, ClaimCase] = {}
    specs, _ = fixtures.build_all()
    for spec in specs:
        case = db.execute(select(ClaimCase).where(ClaimCase.case_no == spec["case_no"])).scalars().first()
        if case is None:
            case = ClaimCase(
                case_no=spec["case_no"],
                policy_no=spec["policy_no"],
                customer_name=spec["customer_name"],
                insurance_type=spec["insurance_type"],
                status="pending_docs",
                channel=spec["channel"],
                assignee=spec["assignee"],
                incident_date=spec["incident_date"],
                claim_amount=spec["claim_amount"],
                note=spec["note"],
            )
            db.add(case)
            db.flush()
            _created("ClaimCase", spec["case_no"])
        else:
            _skipped("ClaimCase", spec["case_no"])
        cases[spec["index"]] = case
    return cases


# ------------------------------------------------------------------ 附件 ----


def seed_attachments(db, cases: dict[int, ClaimCase]) -> dict[int, Attachment]:
    _, attachment_specs = fixtures.build_all()
    created: dict[int, Attachment] = {}
    for spec in attachment_specs:
        existing = db.execute(
            select(Attachment).where(Attachment.scan_seq == spec["scan_seq"])
        ).scalars().first()
        if existing is not None:
            _skipped("Attachment", f"seq={spec['scan_seq']:03d}")
            created[spec["scan_seq"]] = existing
            continue

        case = cases.get(spec["case_index"]) if spec["case_index"] is not None else None
        case_policy = case.policy_no if case else ""
        result = classify(spec["original_name"], spec["content_sample"], spec["ext"], case_policy)
        detail = result.to_dict()
        detail["initial_status"] = result.status
        doc_date = spec["doc_date"]
        attachment = Attachment(
            case_id=case.id if case else None,
            scan_seq=spec["scan_seq"],
            source_code=spec["source_code"],
            original_name=spec["original_name"],
            stored_name=None,
            material_type=result.material_type,
            confidence=result.confidence,
            status=result.status,
            sha256=spec["sha256"],
            size_bytes=spec["size_bytes"],
            ext=spec["ext"],
            content_sample=spec["content_sample"],
            match_detail=detail,
            policy_no=result.policy_no,
            policy_source=result.policy_source,
            doc_date=datetime.fromisoformat(doc_date).date(),
            sequence_no=None,
            manual_note="",
        )
        db.add(attachment)
        db.flush()
        created[spec["scan_seq"]] = attachment
        _created("Attachment", f"seq={spec['scan_seq']:03d} {spec['original_name']}")
    return created


# ------------------------------------------------------------------ 批次 ----


def seed_runs(db, users: dict[str, User], rule: NamingRule) -> None:
    if db.execute(select(ArchiveRun).where(ArchiveRun.run_no == SEED_DRY_RUN_NO)).scalars().first() is None:
        dry = ArchiveRun(
            run_no=SEED_DRY_RUN_NO,
            mode=RunMode.DRY_RUN.value,
            status=RunStatus.QUEUED.value,
            rule_version=rule.version,
            template_snapshot=rule.template,
            triggered_by_email=users["admin"].email,
            note="晨间试运行：先看 190 件能否落到正确名字，确认后再正式归档",
            created_at=SEED_STAMP - timedelta(minutes=6),
        )
        db.add(dry)
        db.flush()
        archive_service.execute_run(db, dry, mode=RunMode.DRY_RUN.value)
        dry.started_at = SEED_STAMP - timedelta(minutes=6)
        dry.finished_at = SEED_STAMP - timedelta(minutes=5)
        dry.duration_ms = 4180
        _created("ArchiveRun", SEED_DRY_RUN_NO)
    else:
        _skipped("ArchiveRun", SEED_DRY_RUN_NO)

    if db.execute(select(ArchiveRun).where(ArchiveRun.run_no == SEED_FAILED_RUN_NO)).scalars().first() is None:
        failed = ArchiveRun(
            run_no=SEED_FAILED_RUN_NO,
            mode=RunMode.ARCHIVE.value,
            status=RunStatus.FAILED.value,
            rule_version=rule.version,
            template_snapshot=rule.template,
            triggered_by_email=users["analyst"].email,
            note="正式归档前挂载检查失败",
            scanned=0,
            failed=1,
            started_at=SEED_STAMP,
            finished_at=SEED_STAMP,
            duration_ms=1260,
            created_at=SEED_STAMP,
            log=[
                "[09:12:04] 扫描投件源 共享盘 / 邮箱 / 移动盘",
                "[09:12:04] 挂载点 \\\\fileserver\\claims-drop 只读（0o755 -> 无法重命名），批次中止",
                "[09:12:05] 建议：由 IT 给 docflow 服务账号开写权限后重试",
            ],
        )
        db.add(failed)
        db.flush()
        _created("ArchiveRun", SEED_FAILED_RUN_NO)
    else:
        _skipped("ArchiveRun", SEED_FAILED_RUN_NO)


# --------------------------------------------------------------- 汇总口径 ----


def duplicate_count(db) -> int:
    """同案件同 SHA-256 的多余份数（不随批次执行变化）。"""
    groups = db.execute(
        select(Attachment.case_id, Attachment.sha256, func.count(Attachment.id))
        .where(Attachment.case_id.is_not(None))
        .group_by(Attachment.case_id, Attachment.sha256)
        .having(func.count(Attachment.id) > 1)
    ).all()
    return sum(int(row[2]) - 1 for row in groups)


def pending_count(db) -> int:
    """seed 阶段的低置信件（match_detail.initial_status='pending'），人工改判后仍可复现。"""
    return int(
        db.execute(
            select(func.count(Attachment.id)).where(
                Attachment.match_detail.op("->>")("initial_status") == "pending"
            )
        ).scalar_one()
    )


def summary_counts(db) -> dict[str, Any]:
    return {
        "brand": LABEL,
        "cases": int(db.execute(select(func.count(ClaimCase.id))).scalar_one()),
        "attachments": int(db.execute(select(func.count(Attachment.id))).scalar_one()),
        "duplicates": duplicate_count(db),
        "pending": pending_count(db),
        "rules": int(db.execute(select(func.count(NamingRule.id))).scalar_one()),
        "users": int(db.execute(select(func.count(User.id))).scalar_one()),
    }


def format_summary(counts: dict[str, Any]) -> str:
    return (
        f"SEED_SUMMARY brand={counts['brand']} cases={counts['cases']} "
        f"attachments={counts['attachments']} duplicates={counts['duplicates']} "
        f"pending={counts['pending']} rules={counts['rules']} users={counts['users']}"
    )


def seed_all() -> dict[str, Any]:
    with session_scope() as db:
        users = seed_users(db)
        rule = seed_rule(db)
        cases = seed_cases(db)
        seed_attachments(db, cases)
        seed_runs(db, users, rule)
        archive_service.recompute_case_statuses(db)
        db.flush()
        counts = summary_counts(db)

        fixture_ok = all(counts[key] == value for key, value in EXPECTED_SUMMARY.items())
        print(
            "SEED_CHECK "
            + " ".join(f"{key}={counts[key]}" for key in ("cases", "attachments", "duplicates", "pending", "rules", "users"))
            + f" expected_ok={str(fixture_ok).lower()}",
            flush=True,
        )
        print(format_summary(counts), flush=True)
        return {"created": CREATED, "skipped": SKIPPED, "counts": counts}


if __name__ == "__main__":
    result = seed_all()
    print(f"SEED_DONE created={result['created']} skipped={result['skipped']}", flush=True)
    sys.exit(0)
