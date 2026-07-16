"""加密上报与气象连接凭据。

版本号: 20260716_02
前置版本: 20260716_01
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from utils.credential_cipher import encrypt_secret


revision: str = "20260716_02"
down_revision: Union[str, None] = "20260716_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _encrypt_report_credentials(bind) -> None:
    rows = bind.execute(
        sa.text("SELECT id, payload FROM report_config_meta")
    ).mappings()
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        password = payload.get("server_password")
        if not isinstance(password, str) or not password:
            continue
        encrypted_password = encrypt_secret(password)
        if encrypted_password == password:
            continue

        payload["server_password"] = encrypted_password
        bind.execute(
            sa.text(
                "UPDATE report_config_meta "
                "SET payload = :payload, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = :row_id"
            ),
            {
                "payload": json.dumps(payload, ensure_ascii=False),
                "row_id": row["id"],
            },
        )


def _encrypt_weather_credentials(bind) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT id, password, key_passphrase "
            "FROM weather_connections"
        )
    ).mappings()
    for row in rows:
        values = {
            "password": encrypt_secret(row["password"]),
            "key_passphrase": encrypt_secret(row["key_passphrase"]),
        }
        if (
            values["password"] == row["password"]
            and values["key_passphrase"] == row["key_passphrase"]
        ):
            continue
        bind.execute(
            sa.text(
                "UPDATE weather_connections "
                "SET password = :password, key_passphrase = :key_passphrase "
                "WHERE id = :row_id"
            ),
            {**values, "row_id": row["id"]},
        )


def upgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())

    if "weather_connections" in table_names:
        op.alter_column(
            "weather_connections",
            "password",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=True,
        )
        op.alter_column(
            "weather_connections",
            "key_passphrase",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=True,
        )
        _encrypt_weather_credentials(bind)

    if "report_config_meta" in table_names:
        _encrypt_report_credentials(bind)


def downgrade() -> None:
    """安全迁移保留密文和扩容字段，回退应用仍可读取字符串。"""
    return None
