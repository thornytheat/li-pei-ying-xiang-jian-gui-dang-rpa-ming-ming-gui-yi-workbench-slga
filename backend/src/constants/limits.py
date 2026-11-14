"""限流与业务上限。"""
from __future__ import annotations

from src.config.settings import settings

RATE_LIMIT_RUN_PER_MINUTE = settings.rate_limit_run_per_minute
RATE_LIMIT_CONFIRM_PER_MINUTE = settings.rate_limit_confirm_per_minute
RATE_LIMIT_DEFAULT_PER_MINUTE = settings.rate_limit_default_per_minute
LOGIN_ATTEMPT_PER_MINUTE = settings.login_attempt_per_minute

# 命名模板必需占位符
REQUIRED_TEMPLATE_TOKENS: tuple[str, ...] = ("{保单号}", "{材料类型}", "{YYYYMMDD}", "{序号:02d}")
SUPPORTED_TEMPLATE_TOKENS: tuple[str, ...] = REQUIRED_TEMPLATE_TOKENS

# 单个批次最多扫描附件数（防止一次拖入过多文件）
MAX_SCAN_ATTACHMENTS = 2000
# 列表分页上限
MAX_PAGE_SIZE = 100
