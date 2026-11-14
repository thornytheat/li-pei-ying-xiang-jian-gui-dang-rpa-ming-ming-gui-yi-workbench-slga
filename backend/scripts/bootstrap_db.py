"""建表引导：幂等 create_all（容器 entrypoint 第一步）。

demo 场景用 SQLAlchemy metadata 建表，避免首次启动卡在迁移版本对齐；
正式环境可改用 `alembic upgrade head`（见 backend/migrations/）。

0002 来源覆盖改造后，老库可能已按 0001 建过 archive_runs，这里再做一次幂等补列，
保证「不删卷直接重启」的演示环境也能拿到 root_run_id / source_coverage 等新列。
"""
from __future__ import annotations

import os

from sqlalchemy import text

from src.config.database import engine
from src.config.settings import settings
from src.models import Base

# archive_runs 需要补的列：列名 -> DDL 类型片段
_RUN_COLUMNS: dict[str, str] = {
    "root_run_id": "UUID NULL",
    "root_run_no": "VARCHAR(32) NOT NULL DEFAULT ''",
    "handover_version": "INTEGER NOT NULL DEFAULT 1",
    "source_coverage": "JSONB NOT NULL DEFAULT '{}'::jsonb",
}


def _ensure_run_columns(conn) -> None:
    existing = {
        row[0]
        for row in conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = 'archive_runs'"
            ),
            {"schema": settings.db_schema},
        )
    }
    for column, ddl in _RUN_COLUMNS.items():
        if column not in existing:
            conn.execute(text(f'ALTER TABLE {settings.db_schema}.archive_runs ADD COLUMN {column} {ddl}'))
    # 历史批次自成链根（幂等：已有值的行不动）
    conn.execute(
        text(
            f"UPDATE {settings.db_schema}.archive_runs "
            "SET root_run_id = id, root_run_no = run_no, handover_version = 1 "
            "WHERE root_run_id IS NULL"
        )
    )
    # 新列索引（IF NOT EXISTS 幂等）
    conn.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_archive_runs_root_run_id "
            f"ON {settings.db_schema}.archive_runs (root_run_id)"
        )
    )
    conn.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_archive_runs_root_run_no "
            f"ON {settings.db_schema}.archive_runs (root_run_no)"
        )
    )


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"'))
        Base.metadata.create_all(bind=engine)
        # create_all 不会改已存在的表，老库补列走这里
        _ensure_run_columns(conn)
    os.makedirs(os.path.abspath(settings.archive_store), exist_ok=True)
    print(
        f"[bootstrap] schema={settings.db_schema} tables={len(Base.metadata.tables)} "
        f"archive_store={os.path.abspath(settings.archive_store)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
