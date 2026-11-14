"""不变量/性质测试：比率区间、阈值单调、计数守恒、确定性、顺序无关。

这些性质比单点期望更耐改：只要口径不变，重构算法实现也必须过。
"""
from __future__ import annotations

import random

import pytest

from src.constants.enums import FEATURE_WEIGHTS
from src.services.material_classifier import MATERIAL_TYPES, classify
from src.services.naming_engine import DEFAULT_TEMPLATE, preview_rows

THRESHOLD = 0.60
SEED_SIZE = 210


def _classify_all(seed_cases: list[dict], seed_attachments: list[dict]) -> list[dict]:
    results = []
    for spec in seed_attachments:
        case = seed_cases[spec["case_index"]] if spec["case_index"] is not None else None
        result = classify(
            spec["original_name"],
            spec["content_sample"],
            spec["ext"],
            case["policy_no"] if case else "",
        )
        results.append({"spec": spec, "result": result})
    return results


def test_confidence_always_within_unit_interval(seed_cases, seed_attachments):
    """置信度 ∈ [0,1]，且每个分路得分也 ∈ [0,1]（210 件真实 seed 全量校验）。"""
    classified = _classify_all(seed_cases, seed_attachments)

    assert len(classified) == SEED_SIZE
    for row in classified:
        result = row["result"]
        assert 0.0 <= result.confidence <= 1.0, row["spec"]["original_name"]
        assert len(result.components) == len(MATERIAL_TYPES)
        for material_type, parts in result.components.items():
            for key in ("filename", "content", "regex", "extension", "score"):
                assert 0.0 <= parts[key] <= 1.0, f"{row['spec']['original_name']} {material_type} {key}"
            weighted = sum(FEATURE_WEIGHTS[name] * parts[name] for name in FEATURE_WEIGHTS)
            assert parts["score"] == pytest.approx(weighted, abs=2e-4)


def test_feature_weights_sum_to_one():
    """四路权重必须归一到 1.0，否则置信度不再是概率式分数。"""
    assert set(FEATURE_WEIGHTS) == {"filename", "content", "regex", "extension"}
    assert sum(FEATURE_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-12)
    assert FEATURE_WEIGHTS["filename"] == pytest.approx(0.45, abs=1e-12)
    assert FEATURE_WEIGHTS["content"] == pytest.approx(0.35, abs=1e-12)
    assert FEATURE_WEIGHTS["regex"] == pytest.approx(0.15, abs=1e-12)
    assert FEATURE_WEIGHTS["extension"] == pytest.approx(0.05, abs=1e-12)


def test_classification_is_deterministic(seed_cases, seed_attachments):
    """同一输入两次结果逐字段相同（seed 可复现的前提）。"""
    first = _classify_all(seed_cases, seed_attachments)
    second = _classify_all(seed_cases, seed_attachments)

    for left, right in zip(first, second):
        assert left["result"].to_dict() == right["result"].to_dict()


def test_status_is_consistent_with_confidence_threshold(classified_samples):
    """阈值单调：classified <=> confidence>=0.60；pending <=> 0<c<0.60；unknown <=> c==0。"""
    for sample in classified_samples:
        status, confidence = sample["status"], sample["confidence"]
        if status == "classified":
            assert confidence >= THRESHOLD, sample["original_name"]
        elif status == "pending":
            assert 0.0 < confidence < THRESHOLD, sample["original_name"]
        elif status == "unknown":
            assert confidence == 0.0, sample["original_name"]
            assert sample["material_type"] == "unknown"
        else:  # pragma: no cover - 状态机只有三种输出
            pytest.fail(f"未定义状态 {status}")


def test_seed_status_distribution_matches_contract(classified_samples):
    """真实 seed 210 件的状态分布 = 契约里的 已识别 199 / 待确认 7 / 未识别 4。"""
    counts = {"classified": 0, "pending": 0, "unknown": 0}
    for sample in classified_samples:
        counts[sample["status"]] += 1

    assert counts == {"classified": 199, "pending": 7, "unknown": 4}
    assert sum(counts.values()) == SEED_SIZE


def test_classification_is_order_independent(seed_cases, seed_attachments):
    """分类逐件独立：输入顺序打乱后，每件的结果不变。"""
    ordered = {
        spec["scan_seq"]: classify(
            spec["original_name"],
            spec["content_sample"],
            spec["ext"],
            seed_cases[spec["case_index"]]["policy_no"] if spec["case_index"] is not None else "",
        ).to_dict()
        for spec in seed_attachments
    }

    shuffled = list(seed_attachments)
    random.Random(20261112).shuffle(shuffled)
    assert [spec["scan_seq"] for spec in shuffled] != list(ordered)

    for spec in shuffled:
        result = classify(
            spec["original_name"],
            spec["content_sample"],
            spec["ext"],
            seed_cases[spec["case_index"]]["policy_no"] if spec["case_index"] is not None else "",
        )
        assert result.to_dict() == ordered[spec["scan_seq"]]


def test_naming_preview_conserves_count_and_names_are_unique(classified_samples):
    """命名规划计数守恒：归档 196 + 重复 9 + 无保单号 5 = 210，且归档名两两不冲突。"""
    rows = preview_rows(DEFAULT_TEMPLATE, classified_samples)

    actions = {"archive": 0, "duplicate": 0, "no_policy": 0}
    stored_names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        actions[row["action"]] += 1
        if row["action"] == "archive":
            assert row["stored_name"] not in seen, f"归档重名覆盖：{row['stored_name']}"
            seen.add(row["stored_name"])
            stored_names.append(row["stored_name"])
            assert row["sequence_no"] >= 1
            assert f"_{row['sequence_no']:02d}." in row["stored_name"]
        elif row["action"] == "duplicate":
            # 重复件必须回指一个「已经在本次规划里归档过」的名字
            assert row["stored_name"] in seen
            assert "重复件" in row["reason"]
        else:
            assert row["stored_name"] == ""
            assert "保单号" in row["reason"]

    assert len(rows) == SEED_SIZE
    assert actions == {"archive": 196, "duplicate": 9, "no_policy": 5}
    assert sum(actions.values()) == SEED_SIZE
    assert len(stored_names) == 196
    assert len(set(stored_names)) == 196  # 序号递增保证不重名覆盖


def test_naming_preview_action_multiset_is_order_independent(classified_samples):
    """命名规划的「动作构成」与输入顺序无关（多次覆盖同名会换谁胜出，但总数守恒）。"""
    forward = preview_rows(DEFAULT_TEMPLATE, classified_samples)
    reversed_rows = preview_rows(DEFAULT_TEMPLATE, list(reversed(classified_samples)))

    def tally(rows: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["action"]] = counts.get(row["action"], 0) + 1
        return counts

    assert tally(forward) == tally(reversed_rows) == {"archive": 196, "duplicate": 9, "no_policy": 5}
