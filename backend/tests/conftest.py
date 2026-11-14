"""pytest 公共夹具：保证 `src` / `scripts` 可导入，并暴露确定性 seed 切片。

本文件只做两件事：
  1. 把 backend 根目录（含 `src/`、`scripts/`）放进 sys.path，使 `python -m pytest tests` 可直接跑；
  2. 用 `scripts.fixtures`（纯函数、random.Random(580) 确定）提供「真实 seed 里的一小段」，
     供算法单测直接复用，避免测试里另造一套与生产不一致的样例。

注意：这里不连数据库、不启 FastAPI、不 mock 算法。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import fixtures  # noqa: E402
from src.constants.enums import MaterialType  # noqa: E402
from src.services.material_classifier import classify  # noqa: E402


@pytest.fixture(scope="session")
def seed_bundle() -> tuple[list[dict], list[dict]]:
    """600+ 行 seed 数据的纯函数来源：60 案件 / 210 附件，逐字节可复现。"""
    return fixtures.build_all()


@pytest.fixture(scope="session")
def seed_cases(seed_bundle: tuple[list[dict], list[dict]]) -> list[dict]:
    return seed_bundle[0]


@pytest.fixture(scope="session")
def seed_attachments(seed_bundle: tuple[list[dict], list[dict]]) -> list[dict]:
    return seed_bundle[1]


@pytest.fixture(scope="session")
def regular_attachments(seed_attachments: list[dict]) -> list[dict]:
    """正常材料件：非弱特征、非重复投递（用来验证四路特征的真实命中）。"""
    return [
        spec
        for spec in seed_attachments
        if not spec["weak"] and spec["duplicate_of_seq"] is None
    ]


@pytest.fixture(scope="session")
def pick_regular_by_hint(regular_attachments: list[dict]):
    """按材料类型取一条正常件（材料类型来自 fixtures 的 material_hint）。"""

    def _pick(material_type: str) -> dict:
        return next(spec for spec in regular_attachments if spec["material_hint"] == material_type)

    return _pick


@pytest.fixture(scope="session")
def classified_samples(
    seed_cases: list[dict], seed_attachments: list[dict]
) -> list[dict]:
    """按 seed 的方式（classify + 案件绑定保单号）把 210 件附件跑成命名规划样例。"""
    samples: list[dict] = []
    for spec in seed_attachments:
        case = seed_cases[spec["case_index"]] if spec["case_index"] is not None else None
        result = classify(
            spec["original_name"],
            spec["content_sample"],
            spec["ext"],
            case["policy_no"] if case else "",
        )
        samples.append(
            {
                "attachment_id": f"scan-{spec['scan_seq']:03d}",
                "original_name": spec["original_name"],
                "material_type": result.material_type,
                "confidence": result.confidence,
                "policy_no": result.policy_no,
                "doc_date": result.doc_date or date.fromisoformat(spec["doc_date"]),
                "ext": spec["ext"],
                "sha256": spec["sha256"],
                "status": result.status,
            }
        )
    return samples


@pytest.fixture(scope="session")
def id_card_number() -> str:
    """按 GB 11643 生成一个校验位正确的 18 位身份证号。"""
    return fixtures.id_number("11010119900307123")


@pytest.fixture(scope="session")
def unknown_material_type() -> str:
    return MaterialType.UNKNOWN.value
