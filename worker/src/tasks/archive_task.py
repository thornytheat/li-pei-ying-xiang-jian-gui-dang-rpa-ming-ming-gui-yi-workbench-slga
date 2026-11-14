"""消费 docflow.archive_run：执行归档批次（按来源读取/命名/落盘/状态回写）。

kwargs:
  mode: "dry_run" / "archive"
  only_sources: None 读全部来源；补扫时传失败来源代码列表，只重读这些来源。
"""
from __future__ import annotations

from src.config.database import session_scope
from src.models.archive_run import ArchiveRun
from src.services import archive_service
from src.utils.logger import get_logger
from worker_src.config.celery_app import celery_app

logger = get_logger("docflow.worker.archive")


@celery_app.task(name="docflow.archive_run", bind=True, max_retries=0)
def archive_run(self, run_id: str, mode: str = "archive", only_sources: list[str] | None = None) -> dict:
    with session_scope() as db:
        run = db.get(ArchiveRun, run_id)
        if run is None:
            logger.warning("run %s not found", run_id)
            return {"ok": False, "reason": "run_not_found", "run_id": run_id}
        sources = tuple(only_sources) if only_sources else None
        archive_service.execute_run(db, run, mode=mode, only_sources=sources)
        logger.info(
            "run %s finished status=%s archived=%s duplicate=%s coverage_all=%s",
            run.run_no,
            run.status,
            run.archived,
            run.duplicate,
            (run.source_coverage or {}).get("all_covered", False),
        )
        return {
            "ok": run.status in ("succeeded", "partial"),
            "run_no": run.run_no,
            "status": run.status,
            "scanned": run.scanned,
            "archived": run.archived,
            "duplicate": run.duplicate,
            "pending": run.pending,
            "unknown": run.unknown,
            "source_coverage": run.source_coverage,
        }
