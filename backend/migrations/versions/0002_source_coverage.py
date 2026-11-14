"""来源读取覆盖 / 批次链移交版本 / 移交发布留痕。

新增：
  - archive_runs 增列 root_run_id / root_run_no / handover_version / source_coverage；
  - 新表 run_source_reads（批次 × 来源的读取覆盖与失败原因）；
  - 新表 handover_publishes（移交发布留痕，同链重试发布版本号不变）。

Revision ID: 0002_source_coverage
Revises: 0001_initial
Create Date: 2026-11-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_source_coverage"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

SCHEMA = "docflow"


def upgrade() -> None:
    op.add_column(
        "archive_runs",
        sa.Column("root_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "archive_runs",
        sa.Column("root_run_no", sa.String(32), nullable=False, server_default=""),
        schema=SCHEMA,
    )
    op.add_column(
        "archive_runs",
        sa.Column("handover_version", sa.Integer(), nullable=False, server_default="1"),
        schema=SCHEMA,
    )
    op.add_column(
        "archive_runs",
        sa.Column(
            "source_coverage",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_archive_runs_root_run_id", "archive_runs", ["root_run_id"], schema=SCHEMA)
    op.create_index("ix_archive_runs_root_run_no", "archive_runs", ["root_run_no"], schema=SCHEMA)

    # 历史批次自成链根：root_run_id=id、root_run_no=run_no、版本 1
    op.execute(
        f'UPDATE {SCHEMA}.archive_runs SET root_run_id = id, root_run_no = run_no, handover_version = 1 '
        f'WHERE root_run_id IS NULL'
    )

    op.create_table(
        "run_source_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("root_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_code", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.String(40), nullable=False, server_default=""),
        sa.Column("failure_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "source_code", name="uq_run_source"),
        schema=SCHEMA,
    )
    op.create_index("ix_run_source_reads_run_id", "run_source_reads", ["run_id"], schema=SCHEMA)
    op.create_index("ix_run_source_reads_root_run_id", "run_source_reads", ["root_run_id"], schema=SCHEMA)
    op.create_index("ix_run_source_reads_source_code", "run_source_reads", ["source_code"], schema=SCHEMA)
    op.create_index("ix_run_source_reads_status", "run_source_reads", ["status"], schema=SCHEMA)

    op.create_table(
        "handover_publishes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("root_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("root_run_no", sa.String(32), nullable=False, server_default=""),
        sa.Column("handover_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_no", sa.String(32), nullable=False, server_default=""),
        sa.Column("triggered_by_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("file_name", sa.String(240), nullable=False, server_default=""),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("byte_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_handover_publishes_root_run_id", "handover_publishes", ["root_run_id"], schema=SCHEMA)
    op.create_index("ix_handover_publishes_root_run_no", "handover_publishes", ["root_run_no"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("handover_publishes", schema=SCHEMA)
    op.drop_table("run_source_reads", schema=SCHEMA)
    op.drop_index("ix_archive_runs_root_run_no", table_name="archive_runs", schema=SCHEMA)
    op.drop_index("ix_archive_runs_root_run_id", table_name="archive_runs", schema=SCHEMA)
    op.drop_column("archive_runs", "source_coverage", schema=SCHEMA)
    op.drop_column("archive_runs", "handover_version", schema=SCHEMA)
    op.drop_column("archive_runs", "root_run_no", schema=SCHEMA)
    op.drop_column("archive_runs", "root_run_id", schema=SCHEMA)
