"""路由总装配（统一 /api 前缀；Nginx 会剥掉 /api，因此应用内也挂一份根路径）。"""
from fastapi import APIRouter

from src.routes import attachments, audit, auth, cases, export, health, pending, rules, runs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(attachments.router)
api_router.include_router(rules.router)
api_router.include_router(runs.router)
api_router.include_router(pending.router)
api_router.include_router(export.router)
api_router.include_router(audit.router)

__all__ = ["api_router"]
