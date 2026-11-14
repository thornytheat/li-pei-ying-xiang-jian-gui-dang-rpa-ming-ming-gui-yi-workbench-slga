"""案件工作台控制器（薄层：只做 schema 收敛与错误映射）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import SOURCE_LABELS
from src.models.attachment import Attachment
from src.schemas.case import CaseListOut, CaseOut
from src.services import case_service


def list_cases(db: Session, status: str, query: str, page: int, page_size: int) -> dict:
    payload = case_service.list_cases(db, status=status, query=query, page=page, page_size=page_size)
    payload["items"] = [CaseOut(**item).model_dump() for item in payload["items"]]
    return CaseListOut(**payload).model_dump()


def summary(db: Session) -> dict:
    return case_service.summary(db)


def detail(db: Session, case_id: str) -> dict:
    return CaseOut(**case_service.detail(db, case_id)).model_dump()


def sources(db: Session) -> dict:
    counts = dict(
        db.execute(select(Attachment.source_code, func.count(Attachment.id)).group_by(Attachment.source_code)).all()
    )
    from scripts.fixtures import SOURCES

    items = [
        {
            "code": source["code"],
            "name": source["name"],
            "path": source["path"],
            "note": source["note"],
            "cycle": source["cycle"],
            "label": SOURCE_LABELS.get(source["code"], source["name"]),
            "attachments": int(counts.get(source["code"], 0)),
        }
        for source in SOURCES
    ]
    return {"items": items, "total_attachments": sum(item["attachments"] for item in items)}
