"""归档批次控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.user import User
from src.schemas.run import RunCreateRequest, RunOut
from src.services import run_service


def list_runs(db: Session, limit: int) -> dict:
    payload = run_service.list_runs(db, limit=limit)
    payload["items"] = [RunOut(**item).model_dump() for item in payload["items"]]
    if payload.get("active"):
        payload["active"] = RunOut(**payload["active"]).model_dump()
    return payload


def create_run(db: Session, payload: RunCreateRequest, user: User) -> dict:
    run = run_service.create_run(db, user=user, mode=payload.mode, note=payload.note)
    return RunOut(**run).model_dump()


def detail(db: Session, run_id: str) -> dict:
    return RunOut(**run_service.get_run(db, run_id)).model_dump()
