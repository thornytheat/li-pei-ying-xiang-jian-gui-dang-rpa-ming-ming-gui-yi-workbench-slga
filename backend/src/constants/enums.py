"""共享枚举（后端定义）。

前端镜像文件：frontend/src/constants/enums.ts（两份必须一致，README 列出全部出现位置）。
"""
from __future__ import annotations

from enum import Enum


class MaterialType(str, Enum):
    """材料类型（算法 1 的输出）。"""

    INVOICE = "invoice"          # 发票
    DIAGNOSIS = "diagnosis"      # 诊断书
    ID_CARD = "id_card"          # 身份证
    BANK_CARD = "bank_card"      # 银行卡
    DISCHARGE = "discharge"      # 出院小结
    UNKNOWN = "unknown"          # 未识别


class CaseStatus(str, Enum):
    """案件状态（工作台三个抽屉）。"""

    PENDING_DOCS = "pending_docs"  # 待收件
    ARCHIVED = "archived"          # 已归档
    EXCEPTION = "exception"        # 异常


class AttachmentStatus(str, Enum):
    """附件状态。"""

    CLASSIFIED = "classified"  # 已识别，待归档
    PENDING = "pending"        # 待确认（置信不足或缺保单号）
    UNKNOWN = "unknown"        # 未识别类型
    ARCHIVED = "archived"      # 已重命名落盘
    DUPLICATE = "duplicate"    # 内容重复，不落盘


class RunStatus(str, Enum):
    """归档批次状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"  # 部分投件源读取失败：已扫到的部分照常处理，但不得核销/移交
    FAILED = "failed"


class SourceReadStatus(str, Enum):
    """批次内单个投件源的读取覆盖状态。"""

    PENDING = "pending"    # 本轮尚未读取
    COVERED = "covered"    # 读取成功，本来源已核对完成
    FAILED = "failed"      # 读取超时/挂载缺失等：本轮未覆盖，恢复后只补这一来源


# 读取失败原因码（写入 run_source_reads.failure_reason，前端映射中文）
class SourceFailureReason(str, Enum):
    TIMEOUT = "read_timeout"        # 来源读取超时
    NOT_MOUNTED = "not_mounted"     # 挂载点/邮箱不可达
    PERMISSION = "permission_denied"  # 只读或无权限
    UNKNOWN = "unknown_error"       # 其他异常（原文进 failure_detail）


class RunMode(str, Enum):
    """批次模式。"""

    DRY_RUN = "dry_run"  # 试运行：只统计不落盘
    ARCHIVE = "archive"  # 正式归档


class InsuranceType(str, Enum):
    """险种。"""

    MEDICAL = "medical"        # 医疗险
    CRITICAL = "critical"      # 重疾险
    ACCIDENT = "accident"      # 意外险
    AUTO = "auto"              # 车险
    LIFE = "life"              # 寿险


class IngestSource(str, Enum):
    """投件源（3 个 fixture 目录）。"""

    SHARED_DRIVE = "shared_drive"  # 共享盘投件
    MAILBOX = "mailbox"            # 理赔邮箱附件
    PORTABLE = "portable"          # 移动盘补件


MATERIAL_TYPE_LABELS: dict[str, str] = {
    MaterialType.INVOICE.value: "发票",
    MaterialType.DIAGNOSIS.value: "诊断书",
    MaterialType.ID_CARD.value: "身份证",
    MaterialType.BANK_CARD.value: "银行卡",
    MaterialType.DISCHARGE.value: "出院小结",
    MaterialType.UNKNOWN.value: "未识别",
}

# 命名模板里出现的中文材料标签（与文件名一一对应）
MATERIAL_TYPE_FILE_TOKENS: dict[str, str] = {
    MaterialType.INVOICE.value: "发票",
    MaterialType.DIAGNOSIS.value: "诊断书",
    MaterialType.ID_CARD.value: "身份证",
    MaterialType.BANK_CARD.value: "银行卡",
    MaterialType.DISCHARGE.value: "出院小结",
    MaterialType.UNKNOWN.value: "未识别",
}

CASE_STATUS_LABELS: dict[str, str] = {
    CaseStatus.PENDING_DOCS.value: "待收件",
    CaseStatus.ARCHIVED.value: "已归档",
    CaseStatus.EXCEPTION.value: "异常",
}

ATTACHMENT_STATUS_LABELS: dict[str, str] = {
    AttachmentStatus.CLASSIFIED.value: "已识别",
    AttachmentStatus.PENDING.value: "待确认",
    AttachmentStatus.UNKNOWN.value: "未识别",
    AttachmentStatus.ARCHIVED.value: "已归档",
    AttachmentStatus.DUPLICATE.value: "重复件",
}

RUN_STATUS_LABELS: dict[str, str] = {
    RunStatus.QUEUED.value: "排队中",
    RunStatus.RUNNING.value: "执行中",
    RunStatus.SUCCEEDED.value: "已完成",
    RunStatus.PARTIAL.value: "部分来源未覆盖",
    RunStatus.FAILED.value: "失败",
}

SOURCE_READ_STATUS_LABELS: dict[str, str] = {
    SourceReadStatus.PENDING.value: "待读取",
    SourceReadStatus.COVERED.value: "已覆盖",
    SourceReadStatus.FAILED.value: "读取失败",
}

SOURCE_FAILURE_LABELS: dict[str, str] = {
    SourceFailureReason.TIMEOUT.value: "来源读取超时",
    SourceFailureReason.NOT_MOUNTED.value: "来源不可达（未挂载/邮箱连不上）",
    SourceFailureReason.PERMISSION.value: "读取权限不足",
    SourceFailureReason.UNKNOWN.value: "读取异常",
}

RUN_MODE_LABELS: dict[str, str] = {
    RunMode.DRY_RUN.value: "试运行",
    RunMode.ARCHIVE.value: "正式归档",
}

INSURANCE_TYPE_LABELS: dict[str, str] = {
    InsuranceType.MEDICAL.value: "医疗险",
    InsuranceType.CRITICAL.value: "重疾险",
    InsuranceType.ACCIDENT.value: "意外险",
    InsuranceType.AUTO.value: "车险",
    InsuranceType.LIFE.value: "寿险",
}

SOURCE_NAMES: dict[str, str] = {
    IngestSource.SHARED_DRIVE.value: "共享盘投件",
    IngestSource.MAILBOX.value: "理赔邮箱附件",
    IngestSource.PORTABLE.value: "移动盘补件",
}

SOURCE_LABELS: dict[str, str] = {
    IngestSource.SHARED_DRIVE.value: "\\\\fileserver\\claims-drop（共享盘投件）",
    IngestSource.MAILBOX.value: "claims@hangan-broker.cn（理赔邮箱附件）",
    IngestSource.PORTABLE.value: "移动盘补件（现场带回）",
}

# 全部投件源代码的固定顺序（来源覆盖台账按此顺序展示）
ALL_SOURCE_CODES: tuple[str, ...] = (
    IngestSource.SHARED_DRIVE.value,
    IngestSource.MAILBOX.value,
    IngestSource.PORTABLE.value,
)

# 每个险种应收材料（用于缺失材料提示与归档完整性）
EXPECTED_MATERIALS: dict[str, tuple[str, ...]] = {
    InsuranceType.MEDICAL.value: (
        MaterialType.INVOICE.value,
        MaterialType.DIAGNOSIS.value,
        MaterialType.ID_CARD.value,
        MaterialType.BANK_CARD.value,
    ),
    InsuranceType.CRITICAL.value: (
        MaterialType.DIAGNOSIS.value,
        MaterialType.DISCHARGE.value,
        MaterialType.ID_CARD.value,
        MaterialType.BANK_CARD.value,
    ),
    InsuranceType.ACCIDENT.value: (
        MaterialType.INVOICE.value,
        MaterialType.DIAGNOSIS.value,
        MaterialType.ID_CARD.value,
    ),
    InsuranceType.AUTO.value: (
        MaterialType.INVOICE.value,
        MaterialType.ID_CARD.value,
        MaterialType.BANK_CARD.value,
    ),
    InsuranceType.LIFE.value: (
        MaterialType.ID_CARD.value,
        MaterialType.BANK_CARD.value,
        MaterialType.DISCHARGE.value,
    ),
}

# 算法 1 的四路特征权重（后端真算，前端只展示）
FEATURE_WEIGHTS: dict[str, float] = {
    "filename": 0.45,
    "content": 0.35,
    "regex": 0.15,
    "extension": 0.05,
}
