"""RBAC 角色常量。

前后端必须一致：users.role / src/constants/roles.py / frontend/src/constants/roles.ts。
角色：admin 受理主管｜analyst 受理员｜auditor 稽核（只读 + 稽核导出）。
"""
from __future__ import annotations

ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_AUDITOR = "auditor"

ALL_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_ANALYST, ROLE_AUDITOR)

# 能力矩阵：action -> 允许的角色
PERMISSIONS: dict[str, tuple[str, ...]] = {
    "cases:read": ALL_ROLES,
    "cases:write": (ROLE_ADMIN, ROLE_ANALYST),
    "attachments:read": ALL_ROLES,
    "attachments:confirm": (ROLE_ADMIN, ROLE_ANALYST),
    "rules:read": ALL_ROLES,
    "rules:write": (ROLE_ADMIN,),
    "runs:read": ALL_ROLES,
    "runs:create": (ROLE_ADMIN, ROLE_ANALYST),
    "pending:read": ALL_ROLES,
    "exports:handover": (ROLE_ADMIN, ROLE_ANALYST),
    "exports:audit": ALL_ROLES,
    "audit:read": (ROLE_ADMIN,),
}

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "受理主管",
    ROLE_ANALYST: "受理员",
    ROLE_AUDITOR: "稽核",
}

ROLE_PERMISSION_HINT: dict[str, str] = {
    ROLE_ADMIN: "命名规则版本、归档批次、移交清单导出、审计日志",
    ROLE_ANALYST: "发起归档、处理待确认件、案件改判、移交清单导出",
    ROLE_AUDITOR: "只读案件与批次，可导出稽核清单，不可改件/发起批次",
}


def role_can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, ())


def role_permissions(role: str) -> list[str]:
    return [action for action, roles in PERMISSIONS.items() if role in roles]
