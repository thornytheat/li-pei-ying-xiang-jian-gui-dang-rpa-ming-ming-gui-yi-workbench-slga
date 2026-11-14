"""算法 1：材料类型识别（四路特征加权 + 正则校验）单元测试。

口径来源：`batch-plan.md §5.4` 与 `src/services/material_classifier.py`
  特征加权 = 文件名关键词 0.45 + 内容抽样关键词 0.35 + 正则校验 0.15 + 扩展名先验 0.05
  `confidence < 0.60` -> pending；三路（除扩展名）全零 -> unknown 不自动归档。

本文件不用 mock：输入全部来自 `scripts.fixtures`（真实 seed 切片）或手工构造，
期望值全部手算，写死成具体数字。
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts import fixtures
from src.constants.enums import FEATURE_WEIGHTS, MaterialType
from src.services.material_classifier import (
    DEFAULT_AFFINITY,
    EXTENSION_AFFINITY,
    MATERIAL_TYPES,
    classify,
    content_score,
    extension_score,
    filename_score,
    regex_score,
)

THRESHOLD = 0.60


# --------------------------------------------------------------- 正常路径 ----


def test_invoice_real_seed_hits_all_four_channels(pick_regular_by_hint, seed_cases):
    """真实 seed 发票：文件名/内容/发票代码/扩展名四路满分，置信度 1.0。"""
    spec = pick_regular_by_hint(MaterialType.INVOICE.value)
    case = seed_cases[spec["case_index"]]

    result = classify(spec["original_name"], spec["content_sample"], spec["ext"], case["policy_no"])

    assert result.material_type == "invoice"
    assert result.status == "classified"
    assert result.confidence == pytest.approx(1.0, abs=1e-9)
    # 四路分量手算：文件名强命中 1.0 / 内容 0.80+0.06*4+0.04*2=1.12 截断 1.0 / 发票代码 12 位 1.0 / pdf 1.0
    assert result.components["invoice"] == {
        "filename": 1.0,
        "content": 1.0,
        "regex": 1.0,
        "extension": 1.0,
        "score": 1.0,
    }
    # 加权和必须等于四路分量按权重相加：0.45+0.35+0.15+0.05 = 1.0
    assert sum(FEATURE_WEIGHTS[key] * result.components["invoice"][key] for key in FEATURE_WEIGHTS) == pytest.approx(
        1.0, abs=1e-9
    )
    # 保单号优先级：文件名里的 P+12 位优先；日期取文件名 8 位戳
    assert result.policy_no == case["policy_no"]
    assert result.policy_source == "filename"
    assert result.doc_date is not None and result.doc_date.isoformat() == spec["doc_date"]


def test_diagnosis_real_seed_icd_regex_and_content_policy(pick_regular_by_hint):
    """真实 seed 诊断书：ICD-10 正则命中 → regex 分量 1.0；保单号只能从内容取。"""
    spec = pick_regular_by_hint(MaterialType.DIAGNOSIS.value)

    result = classify(spec["original_name"], spec["content_sample"], spec["ext"])

    # 扩展名先验：pdf=0.9 / jpg=0.8，其余三路满分 => 0.95 + 0.05*先验
    expected_extension = {"pdf": 0.9, "jpg": 0.8}[spec["ext"]]
    assert result.material_type == "diagnosis"
    assert result.status == "classified"
    assert result.components["diagnosis"]["filename"] == 1.0
    assert result.components["diagnosis"]["content"] == 1.0  # 三强三弱 => 1.04 截断到 1.0
    assert result.components["diagnosis"]["regex"] == 1.0  # ICD-10 J18.x
    assert result.confidence == pytest.approx(0.95 + 0.05 * expected_extension, abs=1e-4)
    # 文件名不含保单号 -> 落到内容抽样
    assert result.policy_source == "content"
    assert result.policy_no.startswith("P") and len(result.policy_no) == 13


def test_id_card_valid_checksum_weighted_score(id_card_number):
    """身份证：18 位校验位通过 => regex 1.0，总分手算 0.965。"""
    content = (
        f"公民身份号码 {id_card_number}\n"
        "签发机关 某某市公安局某某分局\n"
        "有效期限 2019.05.12-2039.05.12\n"
        "保单号：P202600000777\n"
    )

    result = classify("身份证_张伟_正面.jpg", content, "jpg")

    # 0.45*1.0(文件名"身份证") + 0.35*0.90(内容 2 强 1 弱) + 0.15*1.0(校验位) + 0.05*1.0(jpg)
    assert result.material_type == "id_card"
    assert result.components["id_card"]["content"] == pytest.approx(0.90, abs=1e-9)
    assert result.components["id_card"]["regex"] == 1.0
    assert result.confidence == pytest.approx(0.9650, abs=1e-4)
    assert result.status == "classified"
    assert result.runner_up == "bank_card"
    assert result.policy_no == "P202600000777"
    # 口径：取第一个可解析日期；18 位号码里的连写数字不算日期，命中「有效期限」起点
    assert result.doc_date == date(2019, 5, 12)


def test_id_card_bad_checksum_downgrades_regex_component(id_card_number):
    """校验位不通过 => regex 只给 0.40（不是 0，也不是 1），总分 0.875，仍可自动归档。"""
    broken = id_card_number[:-1] + ("0" if id_card_number[-1] != "0" else "1")
    assert fixtures.id_number(id_card_number[:17]) == id_card_number  # 前置断言：原始号确实合法
    content = f"公民身份号码 {broken}\n签发机关 某某市公安局\n有效期限 2019.05.12-2039.05.12\n"

    result = classify("身份证_李静_正面.jpg", content, "jpg")

    assert result.components["id_card"]["regex"] == pytest.approx(0.40, abs=1e-9)
    assert result.confidence == pytest.approx(0.8750, abs=1e-4)
    assert result.status == "classified"


def test_bank_card_regex_and_case_bound_policy():
    """银行卡：卡号正则命中；文件名/内容都没有保单号时回落到案件绑定。"""
    content = (
        "招商银行 一卡通\n"
        "账户名 张伟\n"
        "卡号 6214 8300 1234 5678\n"
        "开户行 招商银行某某分行营业部\n"
        "银联 借记卡\n"
    )

    result = classify("银行卡_张伟_招行.jpg", content, "jpg", case_policy_no="P202600000123")

    assert result.material_type == "bank_card"
    assert result.components["bank_card"]["content"] == 1.0  # 四强一弱 => 1.02 截断
    assert result.components["bank_card"]["regex"] == 1.0
    assert result.confidence == pytest.approx(1.0, abs=1e-9)
    assert result.policy_no == "P202600000123"
    assert result.policy_source == "case"


def test_discharge_summary_hits_regx_channel():
    """出院小结：`住院天数：N 天` 必须被正则特征识别（否则四路特征里有一路恒为 0）。"""
    content = (
        "某某市中心医院 出院小结\n"
        "姓名：李静   住院号：ZY2026100501\n"
        "入院日期：2026年10月1日\n"
        "出院日期：入院后数日\n"
        "住院天数：7 天\n"
        "出院诊断：社区获得性肺炎（ICD10 J18.9）\n"
        "出院医嘱：继续口服抗生素一周，门诊复查；注意休息。\n"
        "保单号：P202600000002\n"
    )

    result = classify("出院小结_李静_20261005.pdf", content, "pdf")

    assert result.material_type == "discharge"
    assert result.components["discharge"]["filename"] == 1.0
    assert result.components["discharge"]["content"] == 1.0
    assert regex_score(f"出院小结\n{content}", MaterialType.DISCHARGE.value) == 1.0
    assert result.confidence == pytest.approx(1.0, abs=1e-9)
    assert result.status == "classified"
    assert result.runner_up == "diagnosis"  # ICD10 让诊断书拿到 0.15 正则分


# ----------------------------------------------------------------- 边界 ----


def test_empty_inputs_yield_unknown_without_crash():
    """空输入：三路全零 -> unknown，置信度 0.0，只剩扩展名兜底分 0.05*0.3=0.015。"""
    result = classify("", "", "", "")

    assert result.material_type == "unknown"
    assert result.status == "unknown"
    assert result.confidence == 0.0
    assert result.policy_no == ""
    assert result.doc_date is None
    assert result.runner_up == ""
    for material_type in MATERIAL_TYPES:
        assert result.components[material_type]["score"] == pytest.approx(
            FEATURE_WEIGHTS["extension"] * DEFAULT_AFFINITY, abs=1e-9
        )


def test_single_unknown_seed_file_still_extracts_doc_date(seed_attachments):
    """单条无特征文件：unknown 不自动归档，但内容里的日期仍被抽出来给人工参考。"""
    spec = next(spec for spec in seed_attachments if spec["original_name"] == "扫描件_0007.pdf")

    result = classify(spec["original_name"], spec["content_sample"], spec["ext"])

    assert result.material_type == "unknown"
    assert result.status == "unknown"
    assert result.confidence == 0.0
    assert result.policy_no == ""
    assert result.doc_date is None  # 该页内容没有任何日期

    dated = next(spec for spec in seed_attachments if spec["original_name"] == "IMG_8891.jpg")
    dated_result = classify(dated["original_name"], dated["content_sample"], dated["ext"])
    assert dated_result.status == "unknown"
    assert dated_result.doc_date is not None
    assert dated_result.doc_date.isoformat() == "2026-10-30"


def test_weak_only_content_falls_below_threshold_to_pending():
    """弱特征单条：文件名无关键词、内容只有弱命中 -> 0.2985 < 0.60 -> pending。"""
    name = "扫描件_0012.pdf"
    content = "开票日期 2026年10月18日\n税额 84.00\n合计金额 1,284.00\n备注：门诊费用\n"

    result = classify(name, content, "pdf")

    # 0.45*0 + 0.35*0.71(3 弱) + 0.15*0 + 0.05*1.0(pdf 对发票)
    assert result.material_type == "invoice"
    assert result.confidence == pytest.approx(0.2985, abs=1e-4)
    assert result.confidence < THRESHOLD
    assert result.status == "pending"
    assert result.runner_up == "diagnosis"
    assert result.components["invoice"]["content"] == pytest.approx(0.71, abs=1e-9)
    assert "低于阈值" in result.reason


def test_unknown_extension_uses_default_affinity():
    """未知扩展名（zip/tar）走 DEFAULT_AFFINITY=0.3，不会静默变成 0。"""
    assert extension_score("zip", MaterialType.INVOICE.value) == pytest.approx(0.3, abs=1e-9)
    assert extension_score("", MaterialType.INVOICE.value) == pytest.approx(0.3, abs=1e-9)
    assert extension_score(None, MaterialType.ID_CARD.value) == pytest.approx(0.3, abs=1e-9)

    result = classify("发票_报销.zip", "", "zip")
    assert result.components["invoice"]["extension"] == pytest.approx(0.3, abs=1e-9)
    # 文件名强命中 1.0 权重 0.45，其余两路为 0，扩展名兜底 0.015 => 0.465 -> pending
    assert result.confidence == pytest.approx(0.4650, abs=1e-4)
    assert result.status == "pending"


def test_tie_break_follows_material_types_order():
    """并列（身份证 vs 银行卡同分 0.50）：按 MATERIAL_TYPES 声明顺序取先者。"""
    result = classify("身份证银行卡.jpg", "", "jpg")

    # 0.45*1.0(文件名) + 0.35*0 + 0.15*0 + 0.05*1.0(jpg) = 0.50，两型完全同分
    assert result.components["id_card"]["score"] == pytest.approx(0.50, abs=1e-9)
    assert result.components["bank_card"]["score"] == pytest.approx(0.50, abs=1e-9)
    assert MATERIAL_TYPES.index("id_card") < MATERIAL_TYPES.index("bank_card")
    assert result.material_type == "id_card"
    assert result.runner_up == "bank_card"
    assert result.confidence == pytest.approx(0.50, abs=1e-9)
    assert result.status == "pending"  # 同分但整体 0.50 < 0.60，仍然要人工确认


# ------------------------------------------------------------ 解析/归一 ----


@pytest.mark.parametrize(
    ("name", "content", "case_policy", "expected_policy", "expected_source"),
    [
        ("发票_P202600000009.pdf", "保单号：P202600000001", "P202600000003", "P202600000009", "filename"),
        ("扫描件_0007.pdf", "保单号：P202600000001", "P202600000003", "P202600000001", "content"),
        ("扫描件_0007.pdf", "本页无保单号", "P202600000003", "P202600000003", "case"),
        ("扫描件_0007.pdf", "保单号：P2026000000", "", "", ""),  # 11 位不算保单号
    ],
)
def test_policy_no_priority_and_strict_format(name, content, case_policy, expected_policy, expected_source):
    """保单号抽取优先级：文件名 > 内容 > 案件绑定；格式必须是 P+12 位。"""
    result = classify(name, content, "pdf", case_policy_no=case_policy)

    assert result.policy_no == expected_policy
    assert result.policy_source == expected_source


def test_score_helpers_match_documented_formula():
    """四路打分函数的口径（供上面用例复用，单独钉住权重公式）。"""
    stem = "增值税电子普通发票"
    assert filename_score(stem, MaterialType.INVOICE.value) == 1.0
    assert filename_score("票据_2026", MaterialType.INVOICE.value) == pytest.approx(0.55, abs=1e-9)
    assert filename_score("随便", MaterialType.INVOICE.value) == 0.0
    # 内容：1 强 => 0.80；2 强 => 0.86；3 强 1 弱 => 0.80+0.12+0.04 = 0.96
    assert content_score("发票代码", MaterialType.INVOICE.value) == pytest.approx(0.80, abs=1e-9)
    assert content_score("发票代码 发票号码", MaterialType.INVOICE.value) == pytest.approx(0.86, abs=1e-9)
    assert content_score("发票代码 发票号码 增值税 税额", MaterialType.INVOICE.value) == pytest.approx(0.96, abs=1e-9)
    # 只有弱特征：0.55 + 0.08*(n-1)，上限 0.85
    assert content_score("税额", MaterialType.INVOICE.value) == pytest.approx(0.55, abs=1e-9)
    assert content_score("税额 开票日期 销售方 合计金额", MaterialType.INVOICE.value) == pytest.approx(0.79, abs=1e-9)


def test_extension_affinity_table_is_complete_for_known_types():
    """扩展名先验表：发票在 pdf/tif/ofd 高，身份证/银行卡在 jpg/png/heic 高。"""
    assert EXTENSION_AFFINITY["pdf"][MaterialType.INVOICE.value] == 1.0
    assert EXTENSION_AFFINITY["ofd"] == {MaterialType.INVOICE.value: 0.9}
    assert EXTENSION_AFFINITY["jpg"][MaterialType.ID_CARD.value] == 1.0
    assert extension_score(".PDF", MaterialType.INVOICE.value) == 1.0  # 大小写与点号都归一
    assert extension_score("TIF", MaterialType.DISCHARGE.value) == pytest.approx(0.9, abs=1e-9)
