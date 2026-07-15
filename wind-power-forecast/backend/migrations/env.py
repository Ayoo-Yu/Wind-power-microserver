from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import kingbase_dialect  # noqa: F401
from database_config import SQLALCHEMY_DATABASE_URI
from db_models import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """生成 Alembic 使用的数据库连接地址。"""
    return SQLALCHEMY_DATABASE_URI.render_as_string(hide_password=False).replace("%", "%%")


def _include_object(obj, name, type_, reflected, compare_to):
    """阻止自动迁移删除动态表或尚未纳入模型的历史结构。"""
    if reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    """在无数据库连接时生成 SQL。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=False,
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """连接数据库并执行迁移。"""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=False,
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
