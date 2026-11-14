"""ASGI 审计上下文中间件：trace_id + 访问日志 + 安全响应头（中间件 2/2）。

业务动作的审计由 controller/service 显式调用 audit_service.record（带 entity_id）。
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.utils.logger import get_logger

logger = get_logger("docflow.access")


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id
        request.state.client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "")
        )
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.headers["x-trace-id"] = trace_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "same-origin"
        if request.url.path not in ("/health", "/api/health"):
            logger.info(
                "%s %s -> %s %sms trace=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                trace_id,
            )
        return response
