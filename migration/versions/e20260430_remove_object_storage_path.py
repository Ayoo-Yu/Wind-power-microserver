"""remove object storage model path

Revision ID: e20260430
Revises: d20260429
Create Date: 2026-04-30 09:00:00
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import Column, String, text


revision = "e20260430"
down_revision = "d20260429"
branch_labels = None
depends_on = None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :table_name "
                "AND column_name = :column_name)"
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
    )


def upgrade() -> None:
    connection = op.get_bind()
    if _column_exists(connection, "model_versions", "s3_path"):
        op.drop_column("model_versions", "s3_path")


def downgrade() -> None:
    connection = op.get_bind()
    if not _column_exists(connection, "model_versions", "s3_path"):
        op.add_column("model_versions", Column("s3_path", String(500)))
