"""解析/归一工具单元测试：保单号、日期族、身份证校验位、发票代码、安全文件名、大小归一。

这些工具是算法 1/2 的地基：保单号决定命名，日期决定 `YYYYMMDD`，校验位决定 regex 特征分。
"""
from __future__ import annotations

import hashlib
from datetime import date

import pytest

from scripts import fixtures
from src.utils import textutils as T


# --------------------------------------------------------------- 保单号 ----


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("P202600000001", ("P202600000001", "hit")),
        ("发票_P202600000001_20260902.pdf", ("P202600000001", "hit")),
        ("保单号：P202600000012；", ("P202600000012", "hit")),
        ("P20260000000", ("", "")),  # 11 位，不够
        ("P2026000000012", ("", "")),  # 13 位，后面还有数字 -> 不匹配
        ("XP202600000001", ("", "")),  # 前面是字母 -> 边界不通过
        ("", ("", "")),
        (None, ("", "")),
    ],
)
def test_extract_policy_no_boundaries(text, expected):
    """保单号必须是独立的 P+12 位数字（前后不能贴字母/数字）。"""
    assert T.extract_policy_no(text) == expected


# ----------------------------------------------------------------- 日期 ----


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("发票_20260902.pdf", date(2026, 9, 2)),  # 文件名 8 位连写
        ("诊断书_张伟_20261026.jpg", date(2026, 10, 26)),
        ("开票日期：2026年9月2日", date(2026, 9, 2)),  # 中文年月日
        ("日期 2026-9-2", date(2026, 9, 2)),  # 短横线 + 单位数
        ("日期 2026/10/26", date(2026, 10, 26)),  # 斜杠族
        ("日期 2026.11.03", date(2026, 11, 3)),  # 点号族
    ],
)
def test_extract_doc_date_families(text, expected):
    """日期族：8 位连写优先，其次 `YYYY年M月D日` / `-` / `/` / `.` 分隔。"""
    assert T.extract_doc_date(text) == expected


@pytest.mark.parametrize(
    "text",
    ["20261332", "2026-13-01", "2026年2月30日", "没有日期的一段文字", "", None],
)
def test_extract_doc_date_rejects_illegal_values(text):
    """非法日历值不抛异常、不返回脏日期，统一降级为 None。"""
    assert T.extract_doc_date(text) is None


# ------------------------------------------------------------- 身份证号 ----


def test_id_card_checksum_matches_gb11643(id_card_number):
    """GB 11643-1999 校验位：合法号 True，末位改错 False。"""
    assert len(id_card_number) == 18
    assert T.id_card_checksum_ok(id_card_number) is True
    broken = id_card_number[:-1] + ("0" if id_card_number[-1] != "0" else "1")
    assert T.id_card_checksum_ok(broken) is False
    # 含 X 的合法号也要认
    assert T.id_card_checksum_ok(fixtures.id_number("11010119800101123")) is True


@pytest.mark.parametrize(
    "bad",
    ["", "11010119900307123", "1101011990030712345", "X10101199003071234"],
)
def test_id_card_checksum_rejects_malformed_lengths(bad):
    """长度不是 18 / 前 17 位含非数字 -> 明确 False（不是抛异常）。"""
    assert T.id_card_checksum_ok(bad) is False


def test_extract_id_number_reports_checksum_state():
    """抽号时同时报告校验位结果：合法 -> (号, True)；非法 -> (号, False)；无号 -> ("", False)。"""
    valid = fixtures.id_number("11010119900307123")
    broken = valid[:-1] + ("0" if valid[-1] != "0" else "1")

    assert T.extract_id_number(f"公民身份号码 {valid}") == (valid, True)
    assert T.extract_id_number(f"公民身份号码 {broken}") == (broken, False)
    assert T.extract_id_number("没有号码") == ("", False)
    assert T.extract_id_number("") == ("", False)


# --------------------------------------------------------------- 发票代码 ----


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("发票代码：044001900001", "044001900001"),
        ("发票代码 044001900001\n发票号码 12345678", "044001900001"),
        ("发票代码：0440019000", ""),  # 只有 10 位
        ("发票号码 044001900001", ""),  # 缺「发票代码」标签
        ("", ""),
    ],
)
def test_extract_invoice_code_requires_twelve_digits(text, expected):
    """发票代码：必须带「发票代码」标签且正好 12 位数字。"""
    assert T.extract_invoice_code(text) == expected


# --------------------------------------------------------- 文件名与大小 ----


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a/b\\c:d*e?.pdf", "a_b_c_d_e_.pdf"),
        ("身份证_张伟_正面.jpg", "身份证_张伟_正面.jpg"),  # 中文保留
        ("", "unnamed"),
        ("   ", "unnamed"),
        ('发票<>|"x".pdf', "发票____x_.pdf"),
    ],
)
def test_safe_filename_strips_path_and_windows_chars(raw, expected):
    """安全文件名：路径分隔符与 Windows 非法字符替换成下划线，中文原样保留。"""
    assert T.safe_filename(raw) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0B"),
        (-5, "0B"),
        (1023, "1023B"),
        (1024, "1.0KB"),
        (1536, "1.5KB"),
        (1048576, "1.0MB"),
        (5 * 1024**3, "5.0GB"),
        (1024**4, "1024.0GB"),
    ],
)
def test_human_size_units(size, expected):
    """大小归一：B 取整、KB/MB/GB 保留一位小数，负数按 0 处理。"""
    assert T.human_size(size) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  a   b  ", "a b"), ("发票   代码", "发票 代码"), ("", ""), (None, "")],
)
def test_normalize_space_collapses_runs(raw, expected):
    """空白归一：去首尾、连续空白压成一个空格。"""
    assert T.normalize_space(raw) == expected


def test_sha256_helpers_match_known_vectors():
    """哈希是判重的唯一依据，向量必须钉死。"""
    assert T.sha256_text("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert T.sha256_text("") == hashlib.sha256(b"").hexdigest()
    assert T.sha256_bytes("发票".encode("utf-8")) == hashlib.sha256("发票".encode("utf-8")).hexdigest()
    assert len(T.sha256_text("同一份材料重复投递")) == 64


def test_now_stamp_matches_hh_mm_ss_shape():
    """批次日志时间戳形如 09:12:04。"""
    stamp = T.now_stamp()
    assert len(stamp) == 8
    parts = stamp.split(":")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
    assert 0 <= int(parts[0]) <= 23
