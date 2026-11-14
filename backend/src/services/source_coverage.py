"""投件源读取覆盖与移交阻断的核心规则（纯函数 / 仅标准库）。

业务口径（对应需求）：
  1. 共享盘 / 邮箱 / 移动盘任一来源读取超时或不可达时，批次只能按「已扫到的部分」结束，
     状态记为 partial，并逐来源记录读取覆盖与失败原因；
  2. 来源未全部核对完成（partial）时，不得核销案件、不得发布移交清单；
  3. 来源恢复后只补失败来源；未读到的材料不产生任何附件行，更不能记成「丢失」；
  4. 同一条批次链（root_run_id 相同）的移交版本号保持一致，重试发布不升版。

本模块不 import SQLAlchemy / pydantic / settings，保证在最小 Python 环境下可独立验证；
DB 落库与读取实现放在 source_service.py，这里只定义数据形状与判定规则。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol

# 与 constants.enums 保持同值；此处字面量定义以切断对 settings/pydantic 的导入链
STATUS_PENDING = "pending"
STATUS_COVERED = "covered"
STATUS_FAILED = "failed"

REASON_TIMEOUT = "read_timeout"
REASON_NOT_MOUNTED = "not_mounted"
REASON_PERMISSION = "permission_denied"
REASON_UNKNOWN = "unknown_error"
VALID_REASONS = frozenset(
    (REASON_TIMEOUT, REASON_NOT_MOUNTED, REASON_PERMISSION, REASON_UNKNOWN)
)

RUN_PARTIAL = "partial"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"

ALL_SOURCE_CODES = ("shared_drive", "mailbox", "portable")

# 环境变量：SOURCE_FAULTS / SOURCE_FAULT_FILE
# 形如 {"mailbox": {"reason": "read_timeout", "detail": "imap 连接 5s 超时"}}
ENV_FAULTS = "SOURCE_FAULTS"
ENV_FAULT_FILE = "SOURCE_FAULT_FILE"


class SourceReadError(Exception):
    """单个投件源读取失败（超时 / 未挂载 / 权限）。绝不代表「材料丢失」。"""

    def __init__(self, source_code: str, reason: str, detail: str = "") -> None:
        if reason not in VALID_REASONS:
            reason = REASON_UNKNOWN
        super().__init__(f"source {source_code} read failed: {reason} {detail}".strip())
        self.source_code = source_code
        self.reason = reason
        self.detail = (detail or "")[:300]


@dataclass(frozen=True)
class SourceReadResult:
    """单个来源一次读取的结果（落 run_source_reads 一行）。"""

    source_code: str
    status: str                       # covered / failed
    read_count: int = 0               # 本轮实际读到的附件数（失败时为 0）
    failure_reason: str = ""          # 失败原因码，成功为空
    failure_detail: str = ""          # 失败原文（截断 300 字）
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_code": self.source_code,
            "status": self.status,
            "read_count": self.read_count,
            "failure_reason": self.failure_reason,
            "failure_detail": self.failure_detail,
            "duration_ms": self.duration_ms,
        }


@dataclass
class CoverageSummary:
    """批次维度的来源覆盖汇总（序列化进 run.source_coverage）。"""

    total_sources: int
    covered_sources: int
    failed_sources: int
    read_count: int
    all_covered: bool
    sources: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sources": self.total_sources,
            "covered_sources": self.covered_sources,
            "failed_sources": self.failed_sources,
            "read_count": self.read_count,
            "all_covered": self.all_covered,
            "sources": list(self.sources),
        }


# --------------------------------------------------------------- 故障注入 ----


def _coerce_fault(raw: Any, source_code: str) -> SourceReadError | None:
    """把 env / 文件里的故障配置转成 SourceReadError；非法配置返回 None（不注入）。"""
    if not isinstance(raw, dict):
        return None
    reason = str(raw.get("reason", REASON_UNKNOWN))
    if reason not in VALID_REASONS:
        reason = REASON_UNKNOWN
    detail = str(raw.get("detail", ""))[:300]
    return SourceReadError(source_code, reason, detail)


def load_fault_config(
    environ: dict[str, str] | None = None,
    *,
    file_reader: Callable[[str], str] | None = None,
) -> dict[str, SourceReadError]:
    """解析故障注入配置：先读 SOURCE_FAULT_FILE（JSON 文件），再用 SOURCE_FAULTS 覆盖。

    非法 JSON / 未知来源一律忽略，不影响正常读取（演示环境的故障开关不能把系统搞挂）。
    """
    env = environ if environ is not None else dict(os.environ)
    reader = file_reader or _read_text_file
    faults: dict[str, SourceReadError] = {}

    file_path = (env.get(ENV_FAULT_FILE) or "").strip()
    if file_path:
        try:
            payload = json.loads(reader(file_path))
        except (OSError, ValueError):
            payload = None
        if isinstance(payload, dict):
            for code, raw in payload.items():
                if code in ALL_SOURCE_CODES:
                    fault = _coerce_fault(raw, code)
                    if fault is not None:
                        faults[code] = fault

    inline = (env.get(ENV_FAULTS) or "").strip()
    if inline:
        try:
            payload = json.loads(inline)
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            for code, raw in payload.items():
                if code in ALL_SOURCE_CODES:
                    fault = _coerce_fault(raw, code)
                    if fault is not None:
                        faults[code] = fault
    return faults


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


# --------------------------------------------------------------- 读取协议 ----


class SourceReader(Protocol):
    """来源读取器协议：source_service 提供 DB 实现，测试可传 fake。"""

    def read(self, source_code: str) -> list[Any]:
        """成功返回该来源的附件列表；失败抛 SourceReadError。"""
        ...


def read_source(
    source_code: str,
    reader: SourceReader,
    *,
    faults: dict[str, SourceReadError] | None = None,
    timer: Callable[[], float] | None = None,
) -> SourceReadResult:
    """读取单个来源，把成功/失败统一收敛成 SourceReadResult。

    失败时 read_count=0 且不带任何附件 —— 调用方不得据此创建「丢失」记录。
    """
    clock = timer or _monotonic
    started = clock()
    injected = (faults or {}).get(source_code)
    if injected is not None:
        return SourceReadResult(
            source_code=source_code,
            status=STATUS_FAILED,
            read_count=0,
            failure_reason=injected.reason,
            failure_detail=injected.detail,
            duration_ms=int((clock() - started) * 1000),
        )
    try:
        attachments = list(reader.read(source_code))
    except SourceReadError as exc:
        return SourceReadResult(
            source_code=source_code,
            status=STATUS_FAILED,
            read_count=0,
            failure_reason=exc.reason,
            failure_detail=exc.detail,
            duration_ms=int((clock() - started) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 - 任何来源异常都要落成「读取失败」而不是炸掉整批
        return SourceReadResult(
            source_code=source_code,
            status=STATUS_FAILED,
            read_count=0,
            failure_reason=REASON_UNKNOWN,
            failure_detail=str(exc)[:300],
            duration_ms=int((clock() - started) * 1000),
        )
    return SourceReadResult(
        source_code=source_code,
        status=STATUS_COVERED,
        read_count=len(attachments),
        duration_ms=int((clock() - started) * 1000),
    )


def _monotonic() -> float:
    import time

    return time.perf_counter()


# --------------------------------------------------------------- 覆盖汇总 ----


def summarize(results: Iterable[SourceReadResult | dict[str, Any]]) -> CoverageSummary:
    """按固定来源顺序汇总覆盖情况；缺读的来源按 pending 占位，保证三来源永远齐行。"""
    normalized: dict[str, dict[str, Any]] = {}
    for result in results:
        row = result.to_dict() if isinstance(result, SourceReadResult) else dict(result)
        code = row.get("source_code", "")
        if code in ALL_SOURCE_CODES:
            normalized[code] = row

    sources: list[dict[str, Any]] = []
    covered = failed = read_total = 0
    for code in ALL_SOURCE_CODES:
        row = normalized.get(
            code,
            {
                "source_code": code,
                "status": STATUS_PENDING,
                "read_count": 0,
                "failure_reason": "",
                "failure_detail": "",
                "duration_ms": 0,
            },
        )
        sources.append(row)
        if row["status"] == STATUS_COVERED:
            covered += 1
        elif row["status"] == STATUS_FAILED:
            failed += 1
        read_total += int(row.get("read_count", 0) or 0)

    return CoverageSummary(
        total_sources=len(ALL_SOURCE_CODES),
        covered_sources=covered,
        failed_sources=failed,
        read_count=read_total,
        all_covered=covered == len(ALL_SOURCE_CODES) and failed == 0,
        sources=sources,
    )


def run_status_from_coverage(summary: CoverageSummary) -> str:
    """全来源覆盖 -> succeeded；有失败但至少一个来源覆盖 -> partial；全失败 -> failed。"""
    if summary.all_covered:
        return RUN_SUCCEEDED
    if summary.covered_sources == 0:
        return RUN_FAILED
    return RUN_PARTIAL


def failed_codes(summary: CoverageSummary) -> tuple[str, ...]:
    return tuple(row["source_code"] for row in summary.sources if row["status"] == STATUS_FAILED)


def pending_codes(summary: CoverageSummary) -> tuple[str, ...]:
    return tuple(row["source_code"] for row in summary.sources if row["status"] == STATUS_PENDING)


# ----------------------------------------------------------- 移交阻断判定 ----


def handover_blocked_source_cases(
    failed_source_codes: Iterable[str],
    case_source_codes: Iterable[str],
) -> set[str]:
    """案件只要有材料来自未覆盖来源，就暂时不能移交（返回被阻断的案件号集合）。

    入参 case_source_codes 为 (case_no, source_code) 序列；来源未覆盖不改变案件本身状态，
    只在工作台/移交清单上标注「暂时不能移交」，材料从未被读到，绝不记为丢失。
    """
    blocked_sources = set(failed_source_codes)
    if not blocked_sources:
        return set()
    blocked_cases: set[str] = set()
    for case_no, source_code in case_source_codes:
        if source_code in blocked_sources:
            blocked_cases.add(case_no)
    return blocked_cases


def assert_handover_publishable(summary: CoverageSummary) -> None:
    """发布前硬闸门：来源未全部核对完成时直接拒绝（由服务层包成 AppError 409）。"""
    if not summary.all_covered:
        codes = "、".join(failed_codes(summary) + pending_codes(summary))
        raise HandoverBlocked(
            f"投件源未全部核对完成（{codes or '未知来源'}），移交清单暂不能发布"
        )


class HandoverBlocked(Exception):
    """来源覆盖不完整时禁止发布移交（服务层转 HANDOVER_BLOCKED / 409）。"""


# ------------------------------------------------------------- 移交版本号 ----


def next_handover_version(existing_versions: Iterable[int]) -> int:
    """新批次链的移交版本号 = 现存最大版本 + 1（从 1 起）。"""
    versions = [int(value) for value in existing_versions]
    return (max(versions) + 1) if versions else 1


def resume_keeps_version(root_version: int) -> int:
    """补扫/重试发布同一条批次链时版本保持一致（恒等函数，显式表达口径并供测试锁定）。"""
    return int(root_version)
