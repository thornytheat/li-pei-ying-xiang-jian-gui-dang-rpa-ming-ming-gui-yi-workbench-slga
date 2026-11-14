from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import export_controller
from src.middlewares.rbac import require_permission
from src.models.user import User

router = APIRouter(tags=["export"])

CSV_MEDIA = "text/csv; charset=utf-8"


def _csv_response(filename: str, content: bytes) -> Response:
    return Response(
        content=content,
        media_type=CSV_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/handover.csv")
def handover(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("exports:handover")),
) -> Response:
    filename, content = export_controller.handover(db, user, request)
    return _csv_response(filename, content)


@router.get("/export/audit.csv")
def audit(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("exports:audit")),
) -> Response:
    filename, content = export_controller.audit(db, user, request)
    return _csv_response(filename, content)
