"""docflow 初始结构：users / claim_cases / attachments / naming_rules / archive_runs / audit_logs。

说明：容器启动走 scripts/bootstrap_db.py 的 metadata create_all（幂等）；
本迁移用于把 demo 结构落到正式迁移链路，二者字段保持一致。

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "docflow"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("role", sa.String(20), nullable=False, server_default="auditor"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )
    op.create_table(
        "claim_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_no", sa.String(32), nullable=False, unique=True),
        sa.Column("policy_no", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("insurance_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("assignee", sa.String(60), nullable=False, server_default=""),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("claim_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )
    op.create_table(
        "naming_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template", sa.String(200), nullable=False),
        sa.Column("conflict_policy", sa.String(30), nullable=False),
        sa.Column("date_source", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.String(240), nullable=False, server_default=""),
        sa.Column("created_by_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )
    op.create_table(
        "archive_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_no", sa.String(32), nullable=False, unique=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("template_snapshot", sa.String(200), nullable=False),
        sa.Column("triggered_by_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("note", sa.String(240), nullable=False, server_default=""),
        sa.Column("scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unknown", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manual", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("log", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.claim_cases.id"), nullable=True),
        sa.Column("scan_seq", sa.Integer(), nullable=False),
        sa.Column("source_code", sa.String(30), nullable=False),
        sa.Column("original_name", sa.String(240), nullable=False),
        sa.Column("stored_name", sa.String(240), nullable=True),
        sa.Column("material_type", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ext", sa.String(12), nullable=False, server_default=""),
        sa.Column("content_sample", sa.Text(), nullable=False, server_default=""),
        sa.Column("match_detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("policy_no", sa.String(20), nullable=False, server_default=""),
        sa.Column("policy_source", sa.String(20), nullable=False, server_default=""),
        sa.Column("doc_date", sa.Date(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("duplicate_of", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("manual_note", sa.String(240), nullable=False, server_default=""),
        sa.Column("first_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.archive_runs.id"), nullable=True),
        sa.Column("last_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.archive_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_attachments_case_id", "attachments", ["case_id"], schema=SCHEMA)
    op.create_index("ix_attachments_status", "attachments", ["status"], schema=SCHEMA)
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"], schema=SCHEMA)
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("entity_type", sa.String(40), nullable=False, server_default=""),
        sa.Column("entity_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trace_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )


def downgrade() -> None:
    for table in ("audit_logs", "attachments", "archive_runs", "naming_rules", "claim_cases", "users"):
        op.drop_table(table, schema=SCHEMA)
