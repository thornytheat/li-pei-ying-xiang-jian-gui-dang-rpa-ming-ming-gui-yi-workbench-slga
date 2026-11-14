"""算法 2：命名归一与冲突消解（纯函数，便于 seed 试算与单测）。

模板：`{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}`（可在命名规则页改，按版本落库）。
保单号抽取优先级：文件名 > 内容抽样 > 案件绑定（见 material_classifier）。
冲突策略：
  1. 目标名未被占用                     -> archive，序号从 01 开始
  2. 目标名已存在且内容 SHA-256 相同      -> duplicate，不落盘（保留被重复的那件的名字）
  3. 目标名已存在但内容不同              -> 序号 +1 继续找，直到找到空位
  4. 序号耗尽 / 无保单号                 -> pending，保留原名并进人工队列
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.config.settings import settings
from src.constants.enums import MATERIAL_TYPE_FILE_TOKENS, MaterialType
from src.constants.limits import REQUIRED_TEMPLATE_TOKENS, SUPPORTED_TEMPLATE_TOKENS
from src.utils.textutils import safe_filename

DEFAULT_TEMPLATE = "{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}"
TEMPLATE_HELP = "可用占位符：{保单号} {材料类型} {YYYYMMDD} {序号:02d}；扩展名自动保留"
REQUIRED_TOKENS: tuple[str, ...] = REQUIRED_TEMPLATE_TOKENS


@dataclass
class PlanResult:
    action: str  # archive | duplicate | no_policy | seq_exhausted
    stored_name: str = ""
    duplicate_name: str = ""
    sequence_no: int | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.action in ("archive", "duplicate")


def missing_tokens(template: str) -> list[str]:
    text = template or ""
    return [token for token in REQUIRED_TEMPLATE_TOKENS if token not in text]


def validate_template(template: str) -> tuple[bool, list[str], str]:
    """返回 (是否合法, 缺失占位符, 提示)。"""
    text = (template or "").strip()
    if not text:
        return False, list(REQUIRED_TEMPLATE_TOKENS), "模板不能为空"
    unknown = [token for token in SUPPORTED_TEMPLATE_TOKENS if token not in text]
    if unknown:
        return False, unknown, "模板缺少必需占位符：" + " ".join(unknown)
    if len(text) > 160:
        return False, [], "模板过长（上限 160 字符）"
    return True, [], "模板合法"


def render_name(
    template: str,
    policy_no: str,
    material_type: str,
    doc_date: date,
    sequence_no: int,
    ext: str = "",
) -> str:
    label = MATERIAL_TYPE_FILE_TOKENS.get(material_type, MATERIAL_TYPE_FILE_TOKENS[MaterialType.UNKNOWN.value])
    rendered = (template or DEFAULT_TEMPLATE)
    rendered = rendered.replace("{保单号}", policy_no or "无保单号")
    rendered = rendered.replace("{材料类型}", label)
    rendered = rendered.replace("{YYYYMMDD}", doc_date.strftime("%Y%m%d"))
    rendered = rendered.replace("{序号:02d}", f"{sequence_no:02d}")
    rendered = safe_filename(rendered)
    suffix = (ext or "").lower().lstrip(".")
    return f"{rendered}.{suffix}" if suffix else rendered


def plan_target(
    template: str,
    policy_no: str,
    material_type: str,
    doc_date: date,
    ext: str,
    content_sha256: str,
    used: dict[str, str],
    limit: int | None = None,
) -> PlanResult:
    """在已占用名字表（name -> sha256）上求目标名。"""
    if not policy_no:
        return PlanResult(action="no_policy", reason="无法抽取保单号，保留原名进待确认")
    max_seq = limit or settings.duplicate_seq_limit
    for seq in range(1, max_seq + 1):
        name = render_name(template, policy_no, material_type, doc_date, seq, ext)
        existing_sha = used.get(name)
        if existing_sha is None:
            return PlanResult(action="archive", stored_name=name, sequence_no=seq, reason="目标名可用")
        # 空内容哈希不得参与判重：宁可多占一个序号，也不能把不同文件当重复件丢掉
        if content_sha256 and existing_sha == content_sha256:
            return PlanResult(
                action="duplicate",
                stored_name=name,
                duplicate_name=name,
                sequence_no=seq,
                reason="目标名已存在且内容 SHA-256 相同，判定重复件不落盘",
            )
    return PlanResult(action="seq_exhausted", reason=f"序号 {max_seq} 内没有可用目标名")


def preview_rows(
    template: str,
    samples: list[dict],
    used: dict[str, str] | None = None,
) -> list[dict]:
    """规则页「模板预览」：用真实附件样例走一遍算法，展示新旧名对照。"""
    used = dict(used or {})
    rows: list[dict] = []
    for sample in samples:
        doc_date = sample.get("doc_date") or date(2026, 11, 10)
        result = plan_target(
            template=template,
            policy_no=sample.get("policy_no", ""),
            material_type=sample.get("material_type", MaterialType.UNKNOWN.value),
            doc_date=doc_date,
            ext=sample.get("ext", ""),
            content_sha256=sample.get("sha256", ""),
            used=used,
        )
        if result.action == "archive":
            used[result.stored_name] = sample.get("sha256", "")
        rows.append(
            {
                "attachment_id": sample.get("attachment_id"),
                "original_name": sample.get("original_name", ""),
                "material_type": sample.get("material_type", ""),
                "confidence": sample.get("confidence", 0),
                "policy_no": sample.get("policy_no", ""),
                "doc_date": doc_date.isoformat(),
                "stored_name": result.stored_name,
                "sequence_no": result.sequence_no,
                "action": result.action,
                "reason": result.reason,
            }
        )
    return rows
