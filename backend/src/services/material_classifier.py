"""算法 1：理赔材料类型识别（特征加权 + 正则校验）。

四路特征（权重见 constants/enums.FEATURE_WEIGHTS，后端真算，前端只展示回传值）：
  1. 文件名关键词    w=0.45   强命中 1.0 / 弱命中 0.55
  2. 内容抽样关键词  w=0.35   强命中 0.80 起、弱命中 0.55 起，带边际递减
  3. 正则校验        w=0.15   发票代码 12 位 / 身份证 18 位校验位 / 卡号 / ICD / 住院天数
  4. 扩展名先验      w=0.05   pdf·jpg·tif 对不同材料的可信度

判定：
  - 除扩展名外三路全零                -> unknown（不自动归档）
  - 最高分 < 0.60（settings 阈值）     -> pending（进待确认队列）
  - 否则                                -> classified（可进入命名归一）
计算过程完全确定性：同一文件名 + 同一内容抽样 => 同一结果（seed 可复现）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from src.config.settings import settings
from src.constants.enums import FEATURE_WEIGHTS, MATERIAL_TYPE_LABELS, MaterialType
from src.utils import textutils as T

MATERIAL_TYPES: tuple[str, ...] = (
    MaterialType.INVOICE.value,
    MaterialType.DIAGNOSIS.value,
    MaterialType.ID_CARD.value,
    MaterialType.BANK_CARD.value,
    MaterialType.DISCHARGE.value,
)

# 文件名关键词：strong 直接 1.0，weak 0.55
FILENAME_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    MaterialType.INVOICE.value: {
        "strong": ("发票", "增值税", "电子发票", "专用发票", "普通发票", "invoice", "fapiao"),
        "weak": ("票据", "报销", "收费"),
    },
    MaterialType.DIAGNOSIS.value: {
        "strong": ("诊断书", "诊断证明", "诊断", "病历", "病情证明", "diagnosis"),
        "weak": ("医嘱", "就诊", "门诊", "复查", "影像", "报告医师"),
    },
    MaterialType.ID_CARD.value: {
        "strong": ("身份证", "身份证明", "证件", "idcard", "id_card"),
        "weak": ("正反面", "复印件", "居民"),
    },
    MaterialType.BANK_CARD.value: {
        "strong": ("银行卡", "bankcard", "储蓄卡", "借记卡", "银行"),
        "weak": ("卡面", "开户", "账号"),
    },
    MaterialType.DISCHARGE.value: {
        "strong": ("出院小结", "出院记录", "出院", "discharge"),
        "weak": ("住院", "病房", "护理"),
    },
}

# 内容抽样关键词（来自 OCR/文本层抽样，前端详情页展示原文抽段）
CONTENT_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    MaterialType.INVOICE.value: {
        "strong": ("发票代码", "发票号码", "增值税", "价税合计", "购买方"),
        "weak": ("税额", "开票日期", "销售方", "合计金额"),
    },
    MaterialType.DIAGNOSIS.value: {
        "strong": ("诊断意见", "诊断证明", "临床诊断", "主诉", "现病史"),
        "weak": ("影像", "复查", "报告医师", "门诊", "病历", "医嘱"),
    },
    MaterialType.ID_CARD.value: {
        "strong": ("公民身份号码", "签发机关", "居民身份证"),
        "weak": ("有效期限", "住址", "出生", "性别"),
    },
    MaterialType.BANK_CARD.value: {
        "strong": ("卡号", "开户行", "银联", "账户名"),
        "weak": ("储蓄", "借记", "有效"),
    },
    MaterialType.DISCHARGE.value: {
        "strong": ("出院诊断", "出院医嘱", "出院小结", "住院天数"),
        "weak": ("入院日期", "出院日期", "住院", "护理"),
    },
}

EXTENSION_AFFINITY: dict[str, dict[str, float]] = {
    "pdf": {
        MaterialType.INVOICE.value: 1.0,
        MaterialType.DISCHARGE.value: 1.0,
        MaterialType.DIAGNOSIS.value: 0.9,
        MaterialType.ID_CARD.value: 0.5,
        MaterialType.BANK_CARD.value: 0.5,
    },
    "jpg": {
        MaterialType.ID_CARD.value: 1.0,
        MaterialType.BANK_CARD.value: 1.0,
        MaterialType.DIAGNOSIS.value: 0.8,
        MaterialType.DISCHARGE.value: 0.6,
        MaterialType.INVOICE.value: 0.5,
    },
    "jpeg": {
        MaterialType.ID_CARD.value: 1.0,
        MaterialType.BANK_CARD.value: 1.0,
        MaterialType.DIAGNOSIS.value: 0.8,
        MaterialType.DISCHARGE.value: 0.6,
        MaterialType.INVOICE.value: 0.5,
    },
    "png": {
        MaterialType.ID_CARD.value: 1.0,
        MaterialType.BANK_CARD.value: 1.0,
        MaterialType.DIAGNOSIS.value: 0.8,
        MaterialType.DISCHARGE.value: 0.6,
        MaterialType.INVOICE.value: 0.5,
    },
    "heic": {
        MaterialType.ID_CARD.value: 1.0,
        MaterialType.BANK_CARD.value: 1.0,
        MaterialType.DIAGNOSIS.value: 0.8,
        MaterialType.DISCHARGE.value: 0.6,
        MaterialType.INVOICE.value: 0.4,
    },
    "tif": {
        MaterialType.INVOICE.value: 0.9,
        MaterialType.DISCHARGE.value: 0.9,
        MaterialType.DIAGNOSIS.value: 0.8,
        MaterialType.ID_CARD.value: 0.6,
        MaterialType.BANK_CARD.value: 0.6,
    },
    "tiff": {
        MaterialType.INVOICE.value: 0.9,
        MaterialType.DISCHARGE.value: 0.9,
        MaterialType.DIAGNOSIS.value: 0.8,
        MaterialType.ID_CARD.value: 0.6,
        MaterialType.BANK_CARD.value: 0.6,
    },
    "ofd": {MaterialType.INVOICE.value: 0.9},
    "xlsx": {MaterialType.INVOICE.value: 0.6},
}

DEFAULT_AFFINITY = 0.3

_BANK_CARD_RE = re.compile(r"(?:卡号|账号)[:：]?\s*((?:\d[ -]?){15,19}\d)")
_ICD_RE = re.compile(r"ICD[- ]?(?:10)?[- ]?[A-Z]\d{2}(?:\.\d+)?")
# 住院天数：真实影像件/OA 文本里写「住院天数：7 天」或「住院 7 天」两种都算
_DISCHARGE_RE = re.compile(r"住院(?:天数)?\s*[:：]?\s*\d+\s*天")


@dataclass
class Classification:
    material_type: str
    confidence: float
    status: str
    policy_no: str
    policy_source: str
    doc_date: date | None
    components: dict[str, dict[str, float]] = field(default_factory=dict)
    reason: str = ""
    runner_up: str = ""

    def to_dict(self) -> dict:
        return {
            "material_type": self.material_type,
            "confidence": round(self.confidence, 4),
            "status": self.status,
            "policy_no": self.policy_no,
            "policy_source": self.policy_source,
            "doc_date": self.doc_date.isoformat() if self.doc_date else None,
            "components": self.components,
            "reason": self.reason,
            "runner_up": self.runner_up,
            "weights": FEATURE_WEIGHTS,
        }


def _hits(text: str, table: dict[str, tuple[str, ...]]) -> tuple[list[str], list[str]]:
    lowered = (text or "").lower()
    strong = [kw for kw in table["strong"] if kw.lower() in lowered]
    weak = [kw for kw in table["weak"] if kw.lower() in lowered]
    return strong, weak


def filename_score(filename: str, material_type: str) -> float:
    strong, weak = _hits(filename, FILENAME_KEYWORDS[material_type])
    if strong:
        return 1.0
    if weak:
        return 0.55
    return 0.0


def content_score(content: str, material_type: str) -> float:
    strong, weak = _hits(content, CONTENT_KEYWORDS[material_type])
    if strong:
        return min(1.0, 0.80 + 0.06 * (len(strong) - 1) + 0.04 * len(weak))
    if weak:
        return min(0.85, 0.55 + 0.08 * (len(weak) - 1))
    return 0.0


def regex_score(text: str, material_type: str) -> float:
    raw = text or ""
    if material_type == MaterialType.INVOICE.value:
        return 1.0 if T.extract_invoice_code(raw) else 0.0
    if material_type == MaterialType.ID_CARD.value:
        number, ok = T.extract_id_number(raw)
        if not number:
            return 0.0
        return 1.0 if ok else 0.40
    if material_type == MaterialType.BANK_CARD.value:
        return 1.0 if _BANK_CARD_RE.search(raw) else 0.0
    if material_type == MaterialType.DIAGNOSIS.value:
        return 1.0 if _ICD_RE.search(raw) else 0.0
    if material_type == MaterialType.DISCHARGE.value:
        return 1.0 if (_DISCHARGE_RE.search(raw) and "出院" in raw) else 0.0
    return 0.0


def extension_score(ext: str, material_type: str) -> float:
    normalized = (ext or "").lower().lstrip(".")
    return EXTENSION_AFFINITY.get(normalized, {}).get(material_type, DEFAULT_AFFINITY)


def classify(
    original_name: str,
    content_sample: str,
    ext: str,
    case_policy_no: str = "",
) -> Classification:
    """对单个附件做类型识别 + 保单号/日期抽取。纯函数，无 IO。"""
    stem = (original_name or "").rsplit(".", 1)[0]
    content = content_sample or ""
    text_for_regex = f"{stem}\n{content}"

    components: dict[str, dict[str, float]] = {}
    for material_type in MATERIAL_TYPES:
        f = filename_score(stem, material_type)
        c = content_score(content, material_type)
        r = regex_score(text_for_regex, material_type)
        e = extension_score(ext, material_type)
        total = (
            FEATURE_WEIGHTS["filename"] * f
            + FEATURE_WEIGHTS["content"] * c
            + FEATURE_WEIGHTS["regex"] * r
            + FEATURE_WEIGHTS["extension"] * e
        )
        components[material_type] = {
            "filename": round(f, 4),
            "content": round(c, 4),
            "regex": round(r, 4),
            "extension": round(e, 4),
            "score": round(total, 4),
        }

    ranked = sorted(components.items(), key=lambda item: (-item[1]["score"], MATERIAL_TYPES.index(item[0])))
    winner, best = ranked[0]
    runner_up = ranked[1][0]
    signal_present = any(
        score_part["filename"] > 0 or score_part["content"] > 0 or score_part["regex"] > 0
        for score_part in components.values()
    )

    policy_no, policy_source = "", ""
    hit_name, _ = T.extract_policy_no(stem)
    if hit_name:
        policy_no, policy_source = hit_name, "filename"
    else:
        hit_content, _ = T.extract_policy_no(content)
        if hit_content:
            policy_no, policy_source = hit_content, "content"
        elif case_policy_no:
            policy_no, policy_source = case_policy_no, "case"

    doc_date = T.extract_doc_date(stem) or T.extract_doc_date(content)

    if not signal_present:
        return Classification(
            material_type=MaterialType.UNKNOWN.value,
            confidence=0.0,
            status="unknown",
            policy_no=policy_no,
            policy_source=policy_source,
            doc_date=doc_date,
            components=components,
            reason="文件名/内容/正则三路均无材料特征命中，判定未识别，不自动归档",
            runner_up="",
        )

    confidence = best["score"]
    if confidence < settings.pending_confidence_threshold:
        return Classification(
            material_type=winner,
            confidence=confidence,
            status="pending",
            policy_no=policy_no,
            policy_source=policy_source,
            doc_date=doc_date,
            components=components,
            reason=(
                f"最高分 {confidence:.2f} 低于阈值 {settings.pending_confidence_threshold:.2f}"
                f"（候选 {MATERIAL_TYPE_LABELS.get(winner, winner)}），转人工确认"
            ),
            runner_up=runner_up,
        )

    return Classification(
        material_type=winner,
        confidence=confidence,
        status="classified",
        policy_no=policy_no,
        policy_source=policy_source,
        doc_date=doc_date,
        components=components,
        reason=(
            f"{MATERIAL_TYPE_LABELS.get(winner, winner)} 特征加权 {confidence:.2f} ≥ 阈值，可自动命名归档"
        ),
        runner_up=runner_up,
    )
