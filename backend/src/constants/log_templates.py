"""审计动作常量（写入 audit_logs.action）。"""
from __future__ import annotations

ACTION_LOGIN = "auth.login"
ACTION_LOGOUT = "auth.logout"
ACTION_RUN_CREATE = "run.create"
ACTION_RUN_EXECUTE = "run.execute"
ACTION_RUN_FAILED = "run.failed"
ACTION_ATTACHMENT_CONFIRM = "attachment.confirm"
ACTION_RULE_CREATE = "rule.create"
ACTION_RULE_ACTIVATE = "rule.activate"
ACTION_EXPORT_HANDOVER = "export.handover"
ACTION_EXPORT_AUDIT = "export.audit"
ACTION_VIEW_CASE = "case.view"
