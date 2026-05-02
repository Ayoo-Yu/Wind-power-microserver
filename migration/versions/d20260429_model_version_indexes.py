"""refresh model version indexes

Revision ID: d20260429
Revises: c20260429
Create Date: 2026-04-29 12:10:00
"""
from __future__ import annotations

from sqlalchemy import text
from alembic import op


revision = "d20260429"
down_revision = "c20260429"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name: str) -> bool:
    return bool(
        connection.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": table_name},
        ).scalar()
    )


def upgrade() -> None:
    connection = op.get_bind()
    if not _table_exists(connection, "model_versions"):
        return

    connection.execute(text("DROP INDEX IF EXISTS idx_mv_farm_type"))
    connection.execute(text("DROP INDEX IF EXISTS idx_mv_active"))
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_model_versions_farm_type_trained "
            "ON model_versions (farm_code, task_type, trained_at)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_model_versions_active_score "
            "ON model_versions (farm_code, task_type, is_active, val_accuracy, trained_at) "
            "WHERE is_active = true"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    if not _table_exists(connection, "model_versions"):
        return

    connection.execute(text("DROP INDEX IF EXISTS ix_model_versions_active_score"))
    connection.execute(text("DROP INDEX IF EXISTS ix_model_versions_farm_type_trained"))
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_mv_farm_type "
            "ON model_versions (farm_code, task_type)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_mv_active "
            "ON model_versions (farm_code, task_type, is_active) "
            "WHERE is_active = true"
        )
    )
