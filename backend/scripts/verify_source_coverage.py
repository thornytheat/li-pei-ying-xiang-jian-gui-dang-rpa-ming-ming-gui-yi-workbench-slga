#!/usr/bin/env python3
"""来源容错核心规则的离线验证（仅标准库，python3 -I 运行，不碰 DB / 第三方包）。

覆盖需求点：
  1. 来源读取超时 -> 该来源 failed 且记录原因，其他来源照常 covered，批次 partial；
  2. 全部来源失败 -> failed；全部成功 -> succeeded；
  3. 未读到的材料不产生附件、更不记丢失（read_count=0，无附件返回）；
  4. 恢复补扫只重读失败来源，合并历史覆盖后 all_covered=True；
  5. 来源未全覆盖时 handover 发布被阻断，全覆盖放行；
  6. 阻断案件集合只包含「材料来自失败来源」的案件；
  7. 同批次链移交版本号补扫/重试保持一致，新链版本递增；
  8. 故障注入配置解析（env / 文件 / 非法配置忽略）。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.services import source_coverage as cov  # noqa: E402


class FakeReader:
    """按来源返回预设附件；可对指定来源抛 SourceReadError 模拟真实读取异常。"""

    def __init__(self, data: dict[str, list], raises: dict[str, cov.SourceReadError] | None = None):
        self._data = data
        self._raises = raises or {}
        self.called: list[str] = []

    def read(self, source_code: str) -> list:
        self.called.append(source_code)
        if source_code in self._raises:
            raise self._raises[source_code]
        return list(self._data.get(source_code, []))


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"FAIL {name} {detail}")
    print(f"PASS {name}")


def main() -> int:
    data = {
        "shared_drive": [{"id": 1}, {"id": 2}, {"id": 3}],
        "mailbox": [{"id": 4}, {"id": 5}],
        "portable": [{"id": 6}],
    }

    # 1) 邮箱超时：注入故障 + 真实抛错双路径都应落成 failed/read_count=0
    faults = {"mailbox": cov.SourceReadError("mailbox", cov.REASON_TIMEOUT, "imap 5s 超时")}
    reader = FakeReader(
        data,
        raises={"portable": cov.SourceReadError("portable", cov.REASON_NOT_MOUNTED, "E: 未挂载")},
    )
    results = []
    for code in cov.ALL_SOURCE_CODES:
        results.append(cov.read_source(code, reader, faults=faults))
    by_code = {r.source_code: r for r in results}

    check("covered-source-read-count", by_code["shared_drive"].status == cov.STATUS_COVERED
          and by_code["shared_drive"].read_count == 3)
    check("injected-timeout-failed", by_code["mailbox"].status == cov.STATUS_FAILED
          and by_code["mailbox"].failure_reason == cov.REASON_TIMEOUT
          and "imap" in by_code["mailbox"].failure_detail
          and by_code["mailbox"].read_count == 0)
    check("real-exception-not-mounted", by_code["portable"].status == cov.STATUS_FAILED
          and by_code["portable"].failure_reason == cov.REASON_NOT_MOUNTED)
    # 注入故障在读取器之前短路：读取器根本没被调用，天然不会产生附件，更不会记丢失
    check("injected-fault-never-calls-reader", "mailbox" not in reader.called)
    check("real-exception-source-was-attempted", reader.called.count("portable") == 1)

    # 2) 汇总：部分失败 -> partial；全失败 -> failed；全成功 -> succeeded
    summary = cov.summarize(results)
    check("partial-summary", summary.covered_sources == 1 and summary.failed_sources == 2
          and summary.all_covered is False and summary.read_count == 3)
    check("three-source-rows-always-present", len(summary.sources) == 3
          and [s["source_code"] for s in summary.sources] == list(cov.ALL_SOURCE_CODES))
    check("status-partial", cov.run_status_from_coverage(summary) == cov.RUN_PARTIAL)
    check("failed-codes", cov.failed_codes(summary) == ("mailbox", "portable"))

    all_failed = cov.summarize([
        cov.SourceReadResult(code, cov.STATUS_FAILED, failure_reason=cov.REASON_TIMEOUT)
        for code in cov.ALL_SOURCE_CODES
    ])
    check("status-failed-when-all-fail", cov.run_status_from_coverage(all_failed) == cov.RUN_FAILED)

    all_ok = cov.summarize([
        cov.SourceReadResult(code, cov.STATUS_COVERED, read_count=1) for code in cov.ALL_SOURCE_CODES
    ])
    check("status-succeeded-when-all-covered", cov.run_status_from_coverage(all_ok) == cov.RUN_SUCCEEDED
          and all_ok.all_covered and all_ok.read_count == 3)

    # 缺行来源按 pending 占位（补扫链里本轮没读到的来源）
    gap = cov.summarize([cov.SourceReadResult("shared_drive", cov.STATUS_COVERED, read_count=3)])
    check("missing-source-pending-placeholder", cov.pending_codes(gap) == ("mailbox", "portable")
          and gap.all_covered is False)

    # 3) 未读到不记丢失：失败来源的附件永远不交给下游（FakeReader 数据不变，失败行 read_count=0）
    check("no-fabricated-loss-record", all(
        r.read_count == 0 for r in results if r.status == cov.STATUS_FAILED
    ))

    # 4) 恢复补扫：只重读失败来源，合并历史 -> 全覆盖
    resume_reader = FakeReader({"mailbox": data["mailbox"], "portable": data["portable"]})
    resume_results = [cov.read_source(code, resume_reader) for code in ("mailbox", "portable")]
    check("resume-only-touches-failed-sources", resume_reader.called == ["mailbox", "portable"])
    merged_rows = list(results) + resume_results
    merged = cov.summarize(merged_rows)  # 同来源多行时 summarize 取最后一条
    check("resume-merge-all-covered", merged.all_covered is True
          and merged.covered_sources == 3 and merged.failed_sources == 0
          and merged.read_count == 6)
    check("resume-status-succeeded", cov.run_status_from_coverage(merged) == cov.RUN_SUCCEEDED)

    # 5) 发布闸门：partial 阻断、全覆盖放行
    blocked = False
    try:
        cov.assert_handover_publishable(summary)
    except cov.HandoverBlocked:
        blocked = True
    check("handover-blocked-when-partial", blocked)
    cov.assert_handover_publishable(merged)  # 不抛异常即放行
    check("handover-publishable-when-covered", True)

    # 6) 阻断案件：只有材料来自失败来源的案件进集合
    pairs = [
        ("C001", "shared_drive"),  # 来源正常 -> 不阻断
        ("C002", "mailbox"),       # 邮箱失败 -> 阻断
        ("C003", "portable"),      # 移动盘失败 -> 阻断
        ("C002", "shared_drive"),  # 同案另有正常来源，仍因失败来源阻断
        ("C004", "shared_drive"),
    ]
    blocked_cases = cov.handover_blocked_source_cases(("mailbox", "portable"), pairs)
    check("blocked-cases-precision", blocked_cases == {"C002", "C003"}, str(blocked_cases))
    check("no-blocked-when-no-failure", cov.handover_blocked_source_cases((), pairs) == set())

    # 7) 移交版本：新链递增，同链补扫/重试不变
    check("first-version-starts-at-1", cov.next_handover_version([]) == 1)
    check("version-monotonic", cov.next_handover_version([1, 3, 2]) == 4)
    check("resume-keeps-version", cov.resume_keeps_version(7) == 7)

    # 8) 故障注入配置解析
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as handle:
        json.dump({"portable": {"reason": "permission_denied", "detail": "只读"}}, handle)
        fault_file = handle.name
    environ = {
        cov.ENV_FAULT_FILE: fault_file,
        cov.ENV_FAULTS: json.dumps({
            "mailbox": {"reason": "read_timeout", "detail": "超时"},
            "shared_drive": {"reason": "bogus_reason"},   # 非法 reason 归一成 unknown_error
            "ghost_source": {"reason": "read_timeout"},   # 未知来源忽略
        }),
    }
    parsed = cov.load_fault_config(environ)
    check("fault-file-and-env-merge", set(parsed) == {"mailbox", "portable", "shared_drive"})
    check("fault-unknown-reason-normalized", parsed["shared_drive"].reason == cov.REASON_UNKNOWN)
    check("fault-detail-preserved", parsed["mailbox"].detail == "超时"
          and parsed["portable"].reason == cov.REASON_PERMISSION)

    bad_env = {cov.ENV_FAULTS: "{not json", cov.ENV_FAULT_FILE: "/no/such/file.json"}
    check("invalid-fault-config-ignored", cov.load_fault_config(bad_env) == {})

    # 9) 读取器抛非 SourceReadError 的意外异常时，统一收敛为 failed/unknown_error，不炸整批
    class BoomReader:
        def read(self, source_code: str) -> list:
            raise RuntimeError("磁盘离线")

    boom = cov.read_source("shared_drive", BoomReader())
    check("unexpected-error-caught-as-failed", boom.status == cov.STATUS_FAILED
          and boom.failure_reason == cov.REASON_UNKNOWN and "磁盘离线" in boom.failure_detail)

    print("\nALL SOURCE-COVERAGE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
