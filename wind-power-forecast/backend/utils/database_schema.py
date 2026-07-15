"""业务接口使用的数据库结构守卫。"""

from sqlalchemy import inspect


def require_model_tables(session, *tables) -> None:
    """确认迁移应提供的模型表已经存在。"""
    bind = session.get_bind()
    if bind is None:
        raise RuntimeError("数据库连接不可用")

    inspector = inspect(bind)
    missing = sorted(table.name for table in tables if not inspector.has_table(table.name))
    if missing:
        raise RuntimeError(
            "数据库结构未升级，缺少表: " + ", ".join(missing)
        )
