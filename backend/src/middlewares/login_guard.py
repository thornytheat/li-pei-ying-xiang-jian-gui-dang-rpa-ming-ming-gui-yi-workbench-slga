"""登录爆破防护（ASGI 中间件 1/2）：按客户端 IP 的分钟级窗口。"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.constants import error_codes as codes
from src.constants.limits import LOGIN_ATTEMPT_PER_MINUTE
from src.utils.redis_client import get_redis


class LoginGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.rstrip("/").endswith("/auth/login"):
            client_ip = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                or (request.client.host if request.client else "unknown")
            )
            key = f"loginguard:{client_ip}"
            now = time.time()
            try:
                client = get_redis()
                pipeline = client.pipeline()
                pipeline.zremrangebyscore(key, 0, now - 60)
                pipeline.zadd(key, {f"{now}": now})
                pipeline.zcard(key)
                pipeline.expire(key, 60)
                count = int(pipeline.execute()[2])
            except Exception:  # noqa: BLE001 - Redis 不可用时不阻塞登录
                count = 0
            if count > LOGIN_ATTEMPT_PER_MINUTE:
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": codes.RATE_LIMITED,
                        "message": "登录尝试过于频繁，请 1 分钟后再试",
                        "detail": f"ip={client_ip} count={count}",
                        "trace_id": getattr(request.state, "trace_id", None),
                    },
                )
        return await call_next(request)
