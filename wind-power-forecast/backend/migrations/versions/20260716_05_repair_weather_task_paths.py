"""修复旧前端写入的无效气象目录占位配置。

Revision ID: 20260716_05
Revises: 20260716_04
Create Date: 2026-07-16
"""

from alembic import op


revision = "20260716_05"
down_revision = "20260716_04"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE weather_tasks
        SET path_pattern = 'flat',
            custom_path_pattern = NULL
        WHERE path_pattern = 'custom'
          AND custom_path_pattern = 'manual-template'
        """
    )


def downgrade():
    # 清理后无法区分历史占位记录与用户主动创建的平铺目录任务。
    pass
