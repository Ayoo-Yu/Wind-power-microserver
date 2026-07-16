"""强化预测运行身份、并发约束和审计来源。

版本号: 20260716_03
前置版本: 20260716_02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_03"
down_revision: Union[str, None] = "20260716_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalise_existing_runs() -> None:
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY celery_task_id
                    ORDER BY id
                ) AS duplicate_rank
            FROM prediction_runs
            WHERE celery_task_id IS NOT NULL
        )
        UPDATE prediction_runs
        SET celery_task_id = LEFT(celery_task_id, 70)
            || ':legacy:' || CAST(id AS VARCHAR(20))
        WHERE id IN (
            SELECT id FROM ranked WHERE duplicate_rank > 1
        )
    """))
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY task_id
                    ORDER BY COALESCE(started_at, created_at) DESC, id DESC
                ) AS active_rank
            FROM prediction_runs
            WHERE task_id IS NOT NULL
              AND status IN ('queued', 'running')
        )
        UPDATE prediction_runs
        SET status = 'interrupted',
            finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP),
            error_message = COALESCE(
                error_message,
                '迁移时发现同类并发运行，已终止较早记录'
            )
        WHERE id IN (
            SELECT id FROM ranked WHERE active_rank > 1
        )
    """))
    op.execute(sa.text("""
        UPDATE prediction_runs
        SET attempt_count = CASE
            WHEN status = 'queued' THEN 0
            ELSE 1
        END
        WHERE attempt_count = 0
    """))


def _repair_orphaned_lineage() -> None:
    op.execute(sa.text("""
        DELETE FROM forecast_output_points AS output
        WHERE NOT EXISTS (
            SELECT 1
            FROM prediction_runs AS run
            WHERE run.id = output.prediction_run_id
        )
    """))
    op.execute(sa.text("""
        DELETE FROM prediction_input_snapshots AS snapshot
        WHERE NOT EXISTS (
            SELECT 1
            FROM prediction_runs AS run
            WHERE run.id = snapshot.prediction_run_id
        )
    """))
    op.execute(sa.text("""
        UPDATE forecast_output_points AS output
        SET input_snapshot_id = NULL
        WHERE input_snapshot_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM prediction_input_snapshots AS snapshot
              WHERE snapshot.id = output.input_snapshot_id
          )
    """))
    op.execute(sa.text("""
        UPDATE prediction_input_snapshots AS snapshot
        SET model_version_id = NULL
        WHERE model_version_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM model_versions AS model
              WHERE model.id = snapshot.model_version_id
          )
    """))
    op.execute(sa.text("""
        UPDATE forecast_output_points AS output
        SET model_version_id = NULL
        WHERE model_version_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM model_versions AS model
              WHERE model.id = output.model_version_id
          )
    """))


def upgrade() -> None:
    op.add_column("prediction_runs", sa.Column("requested_by", sa.String(100)))
    op.add_column(
        "prediction_runs",
        sa.Column(
            "trigger_source",
            sa.String(32),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column("prediction_runs", sa.Column("request_id", sa.String(100)))
    op.add_column(
        "prediction_runs",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("prediction_runs", sa.Column("last_heartbeat_at", sa.DateTime()))

    _normalise_existing_runs()

    op.create_unique_constraint(
        "uq_prediction_runs_celery_task_id",
        "prediction_runs",
        ["celery_task_id"],
    )
    op.create_index(
        "ix_prediction_runs_task_action_status",
        "prediction_runs",
        ["task_id", "action", "status"],
    )
    op.create_index(
        "ix_prediction_runs_request_id",
        "prediction_runs",
        ["request_id"],
    )
    op.execute(sa.text("""
        CREATE UNIQUE INDEX uq_prediction_runs_active_task
        ON prediction_runs (task_id)
        WHERE status IN ('queued', 'running') AND task_id IS NOT NULL
    """))

    op.add_column(
        "operation_audit_logs",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "operation_audit_logs",
        sa.Column("request_id", sa.String(100)),
    )
    op.create_index(
        "ix_operation_audit_logs_source",
        "operation_audit_logs",
        ["source"],
    )
    op.create_index(
        "ix_operation_audit_logs_request_id",
        "operation_audit_logs",
        ["request_id"],
    )

    _repair_orphaned_lineage()
    op.create_foreign_key(
        "fk_prediction_input_snapshots_run",
        "prediction_input_snapshots",
        "prediction_runs",
        ["prediction_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_prediction_input_snapshots_model",
        "prediction_input_snapshots",
        "model_versions",
        ["model_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_forecast_output_points_snapshot",
        "forecast_output_points",
        "prediction_input_snapshots",
        ["input_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_forecast_output_points_model",
        "forecast_output_points",
        "model_versions",
        ["model_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_forecast_output_points_model",
        "forecast_output_points",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_forecast_output_points_snapshot",
        "forecast_output_points",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_prediction_input_snapshots_model",
        "prediction_input_snapshots",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_prediction_input_snapshots_run",
        "prediction_input_snapshots",
        type_="foreignkey",
    )

    op.drop_index("ix_operation_audit_logs_request_id", table_name="operation_audit_logs")
    op.drop_index("ix_operation_audit_logs_source", table_name="operation_audit_logs")
    op.drop_column("operation_audit_logs", "request_id")
    op.drop_column("operation_audit_logs", "source")

    op.drop_index("uq_prediction_runs_active_task", table_name="prediction_runs")
    op.drop_index("ix_prediction_runs_request_id", table_name="prediction_runs")
    op.drop_index("ix_prediction_runs_task_action_status", table_name="prediction_runs")
    op.drop_constraint(
        "uq_prediction_runs_celery_task_id",
        "prediction_runs",
        type_="unique",
    )
    op.drop_column("prediction_runs", "last_heartbeat_at")
    op.drop_column("prediction_runs", "attempt_count")
    op.drop_column("prediction_runs", "request_id")
    op.drop_column("prediction_runs", "trigger_source")
    op.drop_column("prediction_runs", "requested_by")
