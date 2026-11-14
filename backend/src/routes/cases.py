from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import case_controller
from src.middlewares.rbac import require_permission
from src.models.user import User

router = APIRouter(tags=["cases"])


@router.get("/cases/summary")
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("cases:read")),
) -> dict:
    return case_controller.summary(db)


@router.get("/cases")
def list_cases(
    status: Annotated[str, Query(max_length=20)] = "",
    q: Annotated[str, Query(max_length=60)] = "",
    page: Annotated[int, Query(ge=1, le=999)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("cases:read")),
) -> dict:
    return case_controller.list_cases(db, status, q, page, page_size)


@router.get("/sources")
def sources(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("cases:read")),
) -> dict:
    return case_controller.sources(db)


@router.get("/cases/{case_id}")
def detail(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("cases:read")),
) -> dict:
    return case_controller.detail(db, case_id)
