"""投件源容错 / 来源覆盖 / 移交阻断 / 版本一致性的纯规则测试。

规则全部在 source_coverage.py（仅标准库），不连数据库、不启 FastAPI；
DB 落库与端到端拦截见 test_source_coverage_db.py。
"""
from __future__ import annotations

import json

import pytest

from src.services import source_coverage as cov


class FakeReader:
    def __init__(self, data, raises=None):
        self._data = data
        self._raises = raises or {}
        self.called: list[str] = []

    def read(self, source_code: str) -> list:
        self.called.append(source_code)
        if source_code in self._raises:
            raise self._raises[source_code]
        return list(self._data.get(source_code, []))


class BoomReader:
    def read(self, source_code: str) -> list:
        raise RuntimeError("磁盘离线")


@pytest.fixture()
def source_data() -> dict[str, list]:
    return {
        "shared_drive": [{"id": 1}, {"id": 2}, {"id": 3}],
        "mailbox": [{"id": 4}, {"id": 5}],
        "portable": [{"id": 6}],
    }


def test_timeout_source_failed_with_reason_and_zero_count(source_data):
    faults = {"mailbox": cov.SourceReadError("mailbox", cov.REASON_TIMEOUT, "imap 5s 超时")}
    reader = FakeReader(source_data)
    result = cov.read_source("mailbox", reader, faults=faults)

    assert result.status == cov.STATUS_FAILED
    assert result.failure_reason == cov.REASON_TIMEOUT
    assert result.read_count == 0
    # 注入故障在读取器前短路：根本不读，天然不会产生附件/丢失记录
    assert reader.called == []


def test_other_sources_still_covered_when_one_fails(source_data):
    faults = {"mailbox": cov.SourceReadError("mailbox", cov.REASON_TIMEOUT, "timeout")}
    reader = FakeReader(source_data)
    results = [cov.read_source(code, reader, faults=faults) for code in cov.ALL_SOURCE_CODES]
    summary = cov.summarize(results)

    assert summary.covered_sources == 2
    assert summary.failed_sources == 1
    assert summary.all_covered is False
    assert cov.run_status_from_coverage(summary) == cov.RUN_PARTIAL
    assert cov.failed_codes(summary) == ("mailbox",)
    # 已扫到的部分照常统计：共享盘 3 + 移动盘 1
    assert summary.read_count == 4


def test_all_failed_marks_run_failed_not_succeeded():
    results = [
        cov.SourceReadResult(code, cov.STATUS_FAILED, failure_reason=cov.REASON_TIMEOUT)
        for code in cov.ALL_SOURCE_CODES
    ]
    summary = cov.summarize(results)
    assert cov.run_status_from_coverage(summary) == cov.RUN_FAILED


def test_all_covered_marks_run_succeeded(source_data):
    reader = FakeReader(source_data)
    results = [cov.read_source(code, reader) for code in cov.ALL_SOURCE_CODES]
    summary = cov.summarize(results)
    assert summary.all_covered is True
    assert cov.run_status_from_coverage(summary) == cov.RUN_SUCCEEDED
    assert summary.read_count == 6


def test_summary_always_keeps_three_source_rows_in_fixed_order():
    summary = cov.summarize([cov.SourceReadResult("shared_drive", cov.STATUS_COVERED, read_count=3)])
    assert [row["source_code"] for row in summary.sources] == list(cov.ALL_SOURCE_CODES)
    assert cov.pending_codes(summary) == ("mailbox", "portable")


def test_failed_source_never_emits_attachment_or_loss_record(source_data):
    faults = {"portable": cov.SourceReadError("portable", cov.REASON_NOT_MOUNTED, "E: 未挂载")}
    reader = FakeReader(source_data)
    result = cov.read_source("portable", reader, faults=faults)
    assert result.status == cov.STATUS_FAILED and result.read_count == 0


def test_unexpected_exception_is_caught_as_failed_not_crash():
    result = cov.read_source("shared_drive", BoomReader())
    assert result.status == cov.STATUS_FAILED
    assert result.failure_reason == cov.REASON_UNKNOWN
    assert "磁盘离线" in result.failure_detail


def test_resume_only_reads_failed_sources_and_merges_to_covered(source_data):
    # 首轮：邮箱 + 移动盘失败
    first = [
        cov.SourceReadResult("shared_drive", cov.STATUS_COVERED, read_count=3),
        cov.SourceReadResult("mailbox", cov.STATUS_FAILED, failure_reason=cov.REASON_TIMEOUT),
        cov.SourceReadResult("portable", cov.STATUS_FAILED, failure_reason=cov.REASON_NOT_MOUNTED),
    ]
    # 恢复：只补两个失败来源
    reader = FakeReader({"mailbox": source_data["mailbox"], "portable": source_data["portable"]})
    resumed = [cov.read_source(code, reader) for code in ("mailbox", "portable")]
    assert reader.called == ["mailbox", "portable"]

    merged = cov.summarize(first + resumed)  # 同来源取最新一行
    assert merged.all_covered is True
    assert merged.covered_sources == 3
    assert merged.failed_sources == 0
    assert cov.run_status_from_coverage(merged) == cov.RUN_SUCCEEDED


def test_handover_gate_blocks_partial_and_allows_covered():
    partial = cov.summarize([
        cov.SourceReadResult("shared_drive", cov.STATUS_COVERED, read_count=1),
        cov.SourceReadResult("mailbox", cov.STATUS_FAILED, failure_reason=cov.REASON_TIMEOUT),
        cov.SourceReadResult("portable", cov.STATUS_COVERED, read_count=1),
    ])
    with pytest.raises(cov.HandoverBlocked):
        cov.assert_handover_publishable(partial)

    full = cov.summarize([
        cov.SourceReadResult(code, cov.STATUS_COVERED, read_count=1) for code in cov.ALL_SOURCE_CODES
    ])
    cov.assert_handover_publishable(full)  # 不抛即放行


def test_blocked_cases_only_those_touching_failed_sources():
    pairs = [
        ("C001", "shared_drive"),
        ("C002", "mailbox"),
        ("C003", "portable"),
        ("C002", "shared_drive"),
        ("C004", "shared_drive"),
    ]
    blocked = cov.handover_blocked_source_cases(("mailbox", "portable"), pairs)
    assert blocked == {"C002", "C003"}
    assert cov.handover_blocked_source_cases((), pairs) == set()


def test_handover_version_monotonic_and_resume_keeps_version():
    assert cov.next_handover_version([]) == 1
    assert cov.next_handover_version([1, 3, 2]) == 4
    assert cov.resume_keeps_version(7) == 7


def test_load_fault_config_merges_file_and_env(tmp_path):
    fault_file = tmp_path / "faults.json"
    fault_file.write_text(
        json.dumps({"portable": {"reason": "permission_denied", "detail": "只读"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    environ = {
        cov.ENV_FAULT_FILE: str(fault_file),
        cov.ENV_FAULTS: json.dumps({
            "mailbox": {"reason": "read_timeout", "detail": "超时"},
            "shared_drive": {"reason": "bogus"},
            "ghost": {"reason": "read_timeout"},
        }),
    }
    parsed = cov.load_fault_config(environ)
    assert set(parsed) == {"mailbox", "portable", "shared_drive"}
    assert parsed["shared_drive"].reason == cov.REASON_UNKNOWN
    assert parsed["mailbox"].detail == "超时"
    assert parsed["portable"].reason == cov.REASON_PERMISSION


def test_load_fault_config_ignores_invalid_json_and_missing_file():
    assert cov.load_fault_config({cov.ENV_FAULTS: "{bad", cov.ENV_FAULT_FILE: "/no/such/file"}) == {}
