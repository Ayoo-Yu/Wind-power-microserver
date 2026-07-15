"""现有业务数据库结构基线。

版本号: 20260715_01
前置版本: 无
"""

from typing import Optional, Sequence, Union


revision: str = "20260715_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """已有数据库通过结构校验后标记到此版本。"""


def downgrade() -> None:
    """基线不执行破坏性回滚。"""
