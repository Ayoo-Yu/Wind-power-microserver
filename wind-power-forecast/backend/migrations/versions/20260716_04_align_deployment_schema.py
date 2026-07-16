"""对齐部署环境中的模型类型和加密字段注释。

版本号: 20260716_04
前置版本: 20260716_03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_04"
down_revision: Union[str, None] = "20260716_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "weather_connections",
        "password",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="加密密码",
    )
    op.alter_column(
        "weather_connections",
        "key_passphrase",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="加密私钥密码",
    )


def downgrade() -> None:
    op.alter_column(
        "weather_connections",
        "key_passphrase",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="私钥密码",
    )
    op.alter_column(
        "weather_connections",
        "password",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="密码",
    )
