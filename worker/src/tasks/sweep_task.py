"""投件目录巡检（每 10 分钟）：只读统计，供运维确认积压量，不改任何数据。"""
from __future__ import annotations

from sqlalchemy import func, select

from src.config.database import session_scope
from src.models.attachment import Attachment
from src.services.archive_service import stored_file_count
from src.utils.logger import get_logger
from worker_src.config.celery_app import celery_app

logger = get_logger("docflow.worker.sweep")


@celery_app.task(name="docflow.drop_sweep")
def drop_sweep() -> dict:
    with session_scope() as db:
        pending = int(
            db.execute(select(func.count(Attachment.id)).where(Attachment.status == "pending")).scalar_one()
        )
        unknown = int(
            db.execute(select(func.count(Attachment.id)).where(Attachment.status == "unknown")).scalar_one()
        )
        total = int(db.execute(select(func.count(Attachment.id))).scalar_one())
    files = stored_file_count()
    logger.info(
        "drop sweep total=%s pending=%s unknown=%s archive_files=%s", total, pending, unknown, files
    )
    return {"total": total, "pending": pending, "unknown": unknown, "archive_files": files}
