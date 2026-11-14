"""异常/非法输入测试：明确异常或明确降级，禁止静默返回脏值。"""
from __future__ import annotations

from datetime import date

import pytest

from src.services.material_classifier import classify, content_score, filename_score, regex_score
from src.services.naming_engine import DEFAULT_TEMPLATE, plan_target, render_name


def test_filename_score_rejects_unknown_material_type():
    """非法材料类型不能被静默接受：KeyError（而不是返回 0 混进加权）。"""
    with pytest.raises(KeyError):
        filename_score("发票_2026.pdf", "receipt")
    with pytest.raises(KeyError):
        content_score("发票代码", "unknown")


def test_regex_score_degrades_to_zero_for_unscored_type():
    """没有正则规则的类型（unknown）明确返回 0.0，不抛异常、不返回 None。"""
    assert regex_score("任何文本", "unknown") == 0.0
    assert regex_score("", "invoice") == 0.0
    assert regex_score(None, "id_card") == 0.0


def test_classify_none_inputs_degrades_to_unknown():
    """None 输入按空串处理 -> unknown / 0.0 / 不抛异常（采集侧脏数据兜底）。"""
    result = classify(None, None, None)

    assert result.material_type == "unknown"
    assert result.status == "unknown"
    assert result.confidence == 0.0
    assert result.policy_no == ""
    assert result.doc_date is None
    assert result.to_dict()["confidence"] == 0.0


def test_classify_name_without_extension_keeps_stem():
    """没有扩展名的文件名不报错：stem 取原名，扩展名先验走默认 0.3。"""
    result = classify("增值税普通发票", "", "")

    assert result.material_type == "invoice"
    assert result.components["invoice"]["filename"] == 1.0
    assert result.components["invoice"]["extension"] == pytest.approx(0.3, abs=1e-9)
    assert result.confidence == pytest.approx(0.4650, abs=1e-4)
    assert result.status == "pending"


def test_render_name_requires_resolved_date():
    """日期未解析时必须显式失败，不能渲染出 `None` 或空日期段的名字。"""
    with pytest.raises(AttributeError):
        render_name(DEFAULT_TEMPLATE, "P202600000001", "invoice", None, 1, "pdf")


def test_plan_target_negative_limit_degrades_to_exhausted():
    """序号上限为负（配置/入参非法）时明确返回 seq_exhausted，不产出 `_00`/`_-1` 这类脏名。"""
    result = plan_target(DEFAULT_TEMPLATE, "P202600000001", "invoice", date(2026, 9, 2), "pdf", "sha", {}, limit=-1)

    assert result.action == "seq_exhausted"
    assert result.stored_name == ""
    assert result.sequence_no is None
    assert result.ok is False
