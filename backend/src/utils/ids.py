"""路径/查询参数里的 UUID 归一：非法格式统一走「对象不存在」，不让 500 漏出去。"""
from __future__ import annotations

import uuid


def as_uuid(value: object) -> uuid.UUID | None:
    """把入参转成 UUID；非法（非 UUID 字符串 / None / 其它类型）返回 None。

    调用方拿到 None 就必须按「资源不存在」处理（404），不要拿原始字符串去查库：
    PostgreSQL 的 uuid 列会对非法字面量抛 DataError，最终变成 500。
    """
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


__all__ = ["as_uuid"]
