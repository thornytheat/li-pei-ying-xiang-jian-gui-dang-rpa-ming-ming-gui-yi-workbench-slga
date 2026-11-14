from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import run_controller
from src.middlewares.rate_limit import rate_limit
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.run import RunCreateRequest, RunResumeRequest

router = APIRouter(tags=["runs"])


@router.get("/runs")
def list_runs(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("runs:read")),
) -> dict:
    return run_controller.list_runs(db, limit)


@router.post("/runs", dependencies=[rate_limit("run")])
def create_run(
    payload: RunCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("runs:create")),
) -> dict:
    return run_controller.create_run(db, payload, user)


@router.post("/runs/{run_id}/resume", dependencies=[rate_limit("run")])
def resume_run(
    run_id: str,
    payload: RunResumeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("runs:create")),
) -> dict:
    """来源恢复后只补失败来源（同批次链，移交版本号不变）。"""
    return run_controller.resume_run(db, run_id, payload, user)


@router.get("/runs/{run_id}")
def detail(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("runs:read")),
) -> dict:
    return run_controller.detail(db, run_id)
