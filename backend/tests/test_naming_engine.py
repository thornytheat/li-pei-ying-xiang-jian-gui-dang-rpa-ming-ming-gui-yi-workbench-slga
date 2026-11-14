"""算法 2：命名归一与冲突消解（模板渲染 + SHA-256 判重 + 序号递增）单元测试。

口径来源：`batch-plan.md §5.4` 与 `src/services/naming_engine.py`
  模板 `{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}`（扩展名自动保留）
  目标名空闲 -> archive（序号从 01 起）
  目标名已存在且内容 SHA-256 相同 -> duplicate（不落盘）
  目标名已存在但内容不同 -> 序号 +1 直到找到空位
  序号耗尽 / 无保单号 -> seq_exhausted / no_policy
"""
from __future__ import annotations

from datetime import date

import pytest

from src.constants.enums import MaterialType
from src.constants.limits import REQUIRED_TEMPLATE_TOKENS
from src.services.naming_engine import (
    DEFAULT_TEMPLATE,
    PlanResult,
    missing_tokens,
    plan_target,
    preview_rows,
    render_name,
    validate_template,
)

DOC_DATE = date(2026, 9, 2)
POLICY = "P202600000001"


# ------------------------------------------------------- 模板渲染（正常） ----


def test_render_name_default_template_exact():
    """默认模板逐字渲染：保单号_材料类型_YYYYMMDD_序号.扩展名。"""
    assert render_name(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, 1, "pdf") == (
        "P202600000001_发票_20260902_01.pdf"
    )
    assert render_name(DEFAULT_TEMPLATE, POLICY, "discharge", DOC_DATE, 7, "jpg") == (
        "P202600000001_出院小结_20260902_07.jpg"
    )


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [(1, "P202600000001_发票_20260902_01.pdf"), (9, "P202600000001_发票_20260902_09.pdf"),
     (10, "P202600000001_发票_20260902_10.pdf"), (99, "P202600000001_发票_20260902_99.pdf")],
)
def test_render_name_sequence_padding_is_two_digits(sequence, expected):
    """序号两位补零：1->01、9->09、10->10、99->99。"""
    assert render_name(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, sequence, "pdf") == expected


@pytest.mark.parametrize(
    ("ext", "suffix"),
    [("pdf", ".pdf"), ("PDF", ".pdf"), (".jpg", ".jpg"), (".JPG", ".jpg"), ("", ""), (None, "")],
)
def test_render_name_extension_normalization(ext, suffix):
    """扩展名归一：去点、小写、空值不加后缀。"""
    rendered = render_name(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, 1, ext)
    assert rendered.endswith(suffix)
    assert rendered == f"P202600000001_发票_20260902_01{suffix}"


def test_render_name_unknown_material_label_falls_back():
    """未知材料类型落到「未识别」标签，不会渲染出裸英文 key。"""
    rendered = render_name(DEFAULT_TEMPLATE, POLICY, MaterialType.UNKNOWN.value, DOC_DATE, 1, "pdf")
    assert rendered == "P202600000001_未识别_20260902_01.pdf"
    assert "unknown" not in rendered


def test_render_name_sanitizes_path_separators_and_windows_chars():
    """模板渲染结果经 safe_filename：`/` `:` `*` `?` 全部替换为下划线。"""
    rendered = render_name(DEFAULT_TEMPLATE, "P2026/0001", "invoice", DOC_DATE, 1, "pdf")
    assert rendered == "P2026_0001_发票_20260902_01.pdf"

    rendered = render_name(DEFAULT_TEMPLATE, "P2026:0001*?", "invoice", DOC_DATE, 1, "pdf")
    assert "/" not in rendered and ":" not in rendered and "*" not in rendered and "?" not in rendered


# ------------------------------------------------- 模板校验（正常 + 边界） ----


@pytest.mark.parametrize(
    ("template", "expected_ok", "expected_missing", "expected_message"),
    [
        (DEFAULT_TEMPLATE, True, [], "模板合法"),
        ("", False, list(REQUIRED_TEMPLATE_TOKENS), "模板不能为空"),
        ("{材料类型}_{YYYYMMDD}", False, ["{保单号}", "{序号:02d}"], "模板缺少必需占位符：{保单号} {序号:02d}"),
        ("{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}" + "x" * 129, False, [], "模板过长（上限 160 字符）"),
        ("{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}" + "x" * 128, True, [], "模板合法"),  # 恰好 160 字符
    ],
)
def test_validate_template_matrix(template, expected_ok, expected_missing, expected_message):
    """模板校验：空 / 缺占位符 / 超长（161）/ 恰好 160 边界。"""
    ok, missing, message = validate_template(template)
    assert (ok, missing, message) == (expected_ok, expected_missing, expected_message)


def test_missing_tokens_lists_only_absent_placeholders():
    """缺少占位符判定与声明顺序一致。"""
    assert missing_tokens(DEFAULT_TEMPLATE) == []
    assert missing_tokens("{保单号}_{材料类型}") == ["{YYYYMMDD}", "{序号:02d}"]
    assert missing_tokens(None) == list(REQUIRED_TEMPLATE_TOKENS)


# --------------------------------------------- 冲突消解（算法 2 正常路径） ----


def test_plan_target_free_name_archives_at_sequence_one():
    """目标名未被占用：archive，序号从 01 开始，不含重复标记。"""
    result = plan_target(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, "pdf", "sha-a", used={})

    assert isinstance(result, PlanResult)
    assert result.action == "archive"
    assert result.stored_name == "P202600000001_发票_20260902_01.pdf"
    assert result.sequence_no == 1
    assert result.duplicate_name == ""
    assert result.reason == "目标名可用"
    assert result.ok is True


def test_plan_target_same_sha256_marks_duplicate_without_new_name():
    """同名且内容 SHA-256 相同 -> duplicate，不落盘、不占新序号。"""
    used = {"P202600000001_发票_20260902_01.pdf": "sha-a"}

    result = plan_target(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, "pdf", "sha-a", used=used)

    assert result.action == "duplicate"
    assert result.stored_name == "P202600000001_发票_20260902_01.pdf"
    assert result.duplicate_name == "P202600000001_发票_20260902_01.pdf"
    assert result.sequence_no == 1
    assert result.ok is True


def test_plan_target_conflict_with_different_content_increments_sequence():
    """同名但内容不同 -> 序号 +1，直到找到空位（01 被占 -> 02）。"""
    used = {
        "P202600000001_发票_20260902_01.pdf": "sha-a",
        "P202600000001_发票_20260902_02.pdf": "sha-b",
    }

    result = plan_target(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, "pdf", "sha-c", used=used)

    assert result.action == "archive"
    assert result.stored_name == "P202600000001_发票_20260902_03.pdf"
    assert result.sequence_no == 3


def test_plan_target_without_policy_no_keeps_original_name():
    """无法抽到保单号 -> no_policy，进人工队列并保留原名（不产出任何新名）。"""
    result = plan_target(DEFAULT_TEMPLATE, "", "invoice", DOC_DATE, "pdf", "sha-a", used={})

    assert result.action == "no_policy"
    assert result.stored_name == ""
    assert result.sequence_no is None
    assert result.duplicate_name == ""
    assert result.ok is False
    assert "保留原名" in result.reason


def test_plan_target_sequence_exhausted_reports_limit():
    """序号用满（limit=2 且 01/02 都被不同内容占用）-> seq_exhausted。"""
    used = {
        "P202600000001_发票_20260902_01.pdf": "sha-a",
        "P202600000001_发票_20260902_02.pdf": "sha-b",
    }

    result = plan_target(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, "pdf", "sha-c", used=used, limit=2)

    assert result.action == "seq_exhausted"
    assert result.stored_name == ""
    assert result.sequence_no is None
    assert result.ok is False
    assert result.reason == "序号 2 内没有可用目标名"


def test_plan_target_does_not_mutate_used_map():
    """plan_target 是纯函数：不写调用方传入的已占用名字表。"""
    used = {"P202600000001_发票_20260902_01.pdf": "sha-a"}
    snapshot = dict(used)

    plan_target(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, "pdf", "sha-b", used=used)

    assert used == snapshot


# ------------------------------------------------------ 冲突消解（边界） ----


def test_plan_target_empty_hash_is_not_treated_as_duplicate():
    """内容哈希缺失（空串）时不得判重：宁可多占一个序号，也不能丢件。"""
    used = {"P202600000001_发票_20260902_01.pdf": ""}

    result = plan_target(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, "pdf", "", used=used)

    assert result.action == "archive"
    assert result.stored_name == "P202600000001_发票_20260902_02.pdf"
    assert result.sequence_no == 2


def test_plan_target_zero_limit_falls_back_to_default_sequence_limit():
    """limit=0 视为未指定（`limit or default`），退化到配置上限而不是直接耗尽。"""
    result = plan_target(DEFAULT_TEMPLATE, POLICY, "invoice", DOC_DATE, "pdf", "sha-a", used={}, limit=0)

    assert result.action == "archive"
    assert result.sequence_no == 1


def test_plan_target_five_distinct_contents_take_consecutive_sequences():
    """同保单号同类型同日期的 5 件不同内容：序号连续占 01..05，互不覆盖。"""
    used: dict[str, str] = {}
    names: list[str] = []
    for index in range(5):
        result = plan_target(DEFAULT_TEMPLATE, POLICY, "id_card", DOC_DATE, "jpg", f"sha-{index}", used=used)
        assert result.action == "archive"
        assert result.sequence_no == index + 1
        used[result.stored_name] = f"sha-{index}"
        names.append(result.stored_name)

    assert names == [
        "P202600000001_身份证_20260902_01.jpg",
        "P202600000001_身份证_20260902_02.jpg",
        "P202600000001_身份证_20260902_03.jpg",
        "P202600000001_身份证_20260902_04.jpg",
        "P202600000001_身份证_20260902_05.jpg",
    ]
    assert len(set(names)) == 5
    # 已经落过盘的内容重投一次 -> 判重
    again = plan_target(DEFAULT_TEMPLATE, POLICY, "id_card", DOC_DATE, "jpg", "sha-3", used=used)
    assert (again.action, again.sequence_no) == ("duplicate", 4)


# ---------------------------------------------------- 规则页预览 preview ----


def test_preview_rows_sequences_and_preserves_input_order():
    """预览按输入顺序出 6 行以内，同键不同内容依次 01/02/03。"""
    samples = [
        {"attachment_id": "a1", "original_name": "发票1.pdf", "material_type": "invoice",
         "confidence": 1.0, "policy_no": POLICY, "doc_date": DOC_DATE, "ext": "pdf", "sha256": "s1"},
        {"attachment_id": "a2", "original_name": "发票2.pdf", "material_type": "invoice",
         "confidence": 0.9, "policy_no": POLICY, "doc_date": DOC_DATE, "ext": "pdf", "sha256": "s2"},
        {"attachment_id": "a3", "original_name": "发票1 (1).pdf", "material_type": "invoice",
         "confidence": 1.0, "policy_no": POLICY, "doc_date": DOC_DATE, "ext": "pdf", "sha256": "s1"},
    ]

    rows = preview_rows(DEFAULT_TEMPLATE, samples)

    assert [row["original_name"] for row in rows] == ["发票1.pdf", "发票2.pdf", "发票1 (1).pdf"]
    assert [row["stored_name"] for row in rows] == [
        "P202600000001_发票_20260902_01.pdf",
        "P202600000001_发票_20260902_02.pdf",
        "P202600000001_发票_20260902_01.pdf",
    ]
    assert [row["action"] for row in rows] == ["archive", "archive", "duplicate"]
    assert [row["sequence_no"] for row in rows] == [1, 2, 1]
    assert rows[2]["reason"] == "目标名已存在且内容 SHA-256 相同，判定重复件不落盘"


def test_preview_rows_defaults_doc_date_and_keeps_caller_map_clean():
    """样例缺 doc_date 时用 2026-11-10 兜底；预览不写调用方传入的 used 表。"""
    used = {"P202600000001_发票_20261110_01.pdf": "old"}
    snapshot = dict(used)
    samples = [
        {"attachment_id": "a1", "original_name": "发票.pdf", "material_type": "invoice",
         "confidence": 1.0, "policy_no": POLICY, "doc_date": None, "ext": "pdf", "sha256": "new"},
    ]

    rows = preview_rows(DEFAULT_TEMPLATE, samples, used=used)

    assert rows[0]["doc_date"] == "2026-11-10"
    assert rows[0]["stored_name"] == "P202600000001_发票_20261110_02.pdf"
    assert rows[0]["action"] == "archive"
    assert used == snapshot
