"""数据库结构版本检查服务。"""

from pathlib import Path
from typing import Any

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from db_models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG_PATH = PROJECT_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_PATH = PROJECT_ROOT / "backend" / "migrations"
VERSION_TABLE = "alembic_version"


def build_alembic_config() -> AlembicConfig:
    """构造与工作目录无关的 Alembic 配置。"""
    config = AlembicConfig(str(ALEMBIC_CONFIG_PATH))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT / "backend"))
    return config


def model_table_names() -> set[str]:
    """返回由 SQLAlchemy 模型声明的表名。"""
    return {table.name for table in Base.metadata.sorted_tables}


def migration_heads() -> list[str]:
    """返回代码仓库中的最新迁移版本。"""
    scripts = ScriptDirectory.from_config(build_alembic_config())
    return sorted(scripts.get_heads())


def database_revisions(engine) -> list[str]:
    """读取数据库当前迁移版本，不创建任何结构。"""
    inspector = inspect(engine)
    if not inspector.has_table(VERSION_TABLE):
        return []

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return sorted(context.get_current_heads())


def inspect_schema_status(engine) -> dict[str, Any]:
    """对比数据库表、模型表和迁移版本。"""
    inspector = inspect(engine)
    database_tables = set(inspector.get_table_names(schema="public"))
    managed_tables = model_table_names()
    application_tables = database_tables - {VERSION_TABLE}
    missing_tables = managed_tables - application_tables
    unmanaged_tables = application_tables - managed_tables
    current_revisions = database_revisions(engine)
    heads = migration_heads()

    if not application_tables:
        state = "empty"
    elif not current_revisions:
        state = "drift" if missing_tables else "unversioned"
    elif set(current_revisions) != set(heads):
        # 新迁移创建的表在升级前必然尚不存在，应先按版本判断为待升级。
        state = "pending"
    elif missing_tables:
        state = "drift"
    else:
        state = "ready"

    return {
        "state": state,
        "ready": state == "ready",
        "current_revisions": current_revisions,
        "head_revisions": heads,
        "database_table_count": len(application_tables),
        "model_table_count": len(managed_tables),
        "missing_tables": sorted(missing_tables),
        "unmanaged_tables": sorted(unmanaged_tables),
    }


def schema_state_message(status: dict[str, Any]) -> str:
    """生成人员可读的结构状态说明。"""
    state = status.get("state")
    if state == "ready":
        return "数据库结构版本与代码一致"
    if state == "empty":
        return "数据库尚未初始化，请执行 manage_db.py prepare"
    if state == "unversioned":
        return "数据库尚未纳入版本管理，请执行 manage_db.py prepare"
    if state == "pending":
        return "数据库存在待执行迁移，请执行 manage_db.py upgrade"
    if state == "drift":
        missing = ", ".join(status.get("missing_tables") or [])
        return f"数据库缺少模型表: {missing}"
    return "数据库结构状态未知"
