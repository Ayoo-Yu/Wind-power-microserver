"""清理会混入业务页面的模拟默认数据。

Revision ID: 20260717_01
Revises: 20260716_05
Create Date: 2026-07-17
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20260717_01"
down_revision = "20260716_05"
branch_labels = None
depends_on = None


NON_AUTHORITATIVE_PROFILE_FIELDS = {
    "scada_status",
    "nwp_status",
    "current_actual_power",
}

SIMULATED_FARMS = {
    "HUST001": "华中科技大学示例风电场",
    "TEST002": "测试风电场2号",
    "DEMO003": "演示风电场",
}


def _existing_tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names(schema="public"))


def _remove_alarm_defaults(bind, existing: set[str]) -> None:
    if "alarm_records" in existing:
        bind.execute(
            sa.text(
                "DELETE FROM alarm_records "
                "WHERE source = 'system-log' "
                "AND module = 'system-log' "
                "AND message IN (:heartbeat, :scheduler)"
            ),
            {
                "heartbeat": "system service heartbeat is normal",
                "scheduler": "scheduler latency is higher than expected",
            },
        )

    if "alarm_rules" in existing:
        bind.execute(
            sa.text(
                "DELETE FROM alarm_rules WHERE "
                "(rule_name = '系统错误告警' AND module = 'system-log' "
                "AND keyword = 'error' AND \"level\" = 'danger') OR "
                "(rule_name = '调度异常告警' AND module = 'scheduler' "
                "AND keyword = 'scheduler' AND \"level\" = 'warning')"
            )
        )

    if "alarm_notification_policies" in existing:
        bind.execute(
            sa.text(
                "DELETE FROM alarm_notification_policies WHERE "
                "(policy_name = '默认声音通知' AND channel = 'sound' "
                "AND target = 'browser-audio') OR "
                "(policy_name = '默认短信通知' AND channel = 'sms' "
                "AND target = 'ops-oncall')"
            )
        )


def _remove_profile_placeholders(bind, existing: set[str]) -> None:
    if "farm_profile_configs" not in existing:
        return

    rows = bind.execute(
        sa.text("SELECT id, payload FROM farm_profile_configs")
    ).mappings()
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if not NON_AUTHORITATIVE_PROFILE_FIELDS.intersection(payload):
            continue
        for field in NON_AUTHORITATIVE_PROFILE_FIELDS:
            payload.pop(field, None)
        bind.execute(
            sa.text(
                "UPDATE farm_profile_configs "
                "SET payload = :payload, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = :row_id"
            ),
            {
                "payload": json.dumps(payload, ensure_ascii=False),
                "row_id": row["id"],
            },
        )


def _remove_report_demo_data(bind, existing: set[str]) -> None:
    if "wind_farms" not in existing:
        return

    farm_rows = bind.execute(
        sa.text(
            "SELECT id, farm_code, farm_name FROM wind_farms "
            "WHERE farm_code IN ('HUST001', 'TEST002', 'DEMO003')"
        )
    ).mappings()
    fake_farms = [
        row
        for row in farm_rows
        if SIMULATED_FARMS.get(row["farm_code"]) == row["farm_name"]
    ]
    if not fake_farms:
        return

    farm_ids = [row["id"] for row in fake_farms]
    farm_codes = [row["farm_code"] for row in fake_farms]
    config_ids: list[int] = []
    if "report_configs" in existing:
        config_ids = list(
            bind.execute(
                sa.text(
                    "SELECT id FROM report_configs "
                    "WHERE farm_id IN :farm_ids"
                ).bindparams(sa.bindparam("farm_ids", expanding=True)),
                {"farm_ids": farm_ids},
            ).scalars()
        )

    if config_ids:
        for table_name in ("report_config_meta", "report_logs", "report_outbox"):
            if table_name not in existing:
                continue
            bind.execute(
                sa.text(
                    f"DELETE FROM {table_name} WHERE config_id IN :config_ids"
                ).bindparams(sa.bindparam("config_ids", expanding=True)),
                {"config_ids": config_ids},
            )
        bind.execute(
            sa.text(
                "DELETE FROM report_configs WHERE id IN :config_ids"
            ).bindparams(sa.bindparam("config_ids", expanding=True)),
            {"config_ids": config_ids},
        )

    for table_name in ("report_logs", "report_quality_statistics"):
        if table_name not in existing:
            continue
        bind.execute(
            sa.text(
                f"DELETE FROM {table_name} WHERE farm_code IN :farm_codes"
            ).bindparams(sa.bindparam("farm_codes", expanding=True)),
            {"farm_codes": farm_codes},
        )

    if "farm_profile_configs" in existing:
        bind.execute(
            sa.text(
                "DELETE FROM farm_profile_configs WHERE farm_code IN :farm_codes"
            ).bindparams(sa.bindparam("farm_codes", expanding=True)),
            {"farm_codes": farm_codes},
        )
    bind.execute(
        sa.text(
            "DELETE FROM wind_farms WHERE id IN :farm_ids"
        ).bindparams(sa.bindparam("farm_ids", expanding=True)),
        {"farm_ids": farm_ids},
    )


def _remove_test_statistics(bind, existing: set[str]) -> None:
    if "report_quality_statistics" not in existing:
        return
    bind.execute(
        sa.text(
            "DELETE FROM report_quality_statistics "
            "WHERE farm_code = 'TEST001'"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_tables(bind)
    _remove_alarm_defaults(bind, existing)
    _remove_profile_placeholders(bind, existing)
    _remove_report_demo_data(bind, existing)
    _remove_test_statistics(bind, existing)


def downgrade() -> None:
    # 已清理的模拟记录没有业务恢复价值。
    pass
