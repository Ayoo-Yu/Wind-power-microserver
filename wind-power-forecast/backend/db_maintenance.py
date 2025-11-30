from sqlalchemy import text

from db_session import db_session


def sync_conditions_sequence() -> None:
    """Ensure `conditions.condition_id` sequence is aligned with current max ID.

    - 只在使用 PostgreSQL 且存在 conditions 表时生效；
    - 设计为幂等，多次调用不会产生副作用；
    - 如果执行失败，只打印警告，不中断应用启动。
    """
    try:
        with db_session() as session:
            session.execute(
                text(
                    """
                    SELECT setval(
                      pg_get_serial_sequence('conditions', 'condition_id'),
                      COALESCE((SELECT MAX(condition_id) FROM conditions), 1)
                    );
                    """
                )
            )
    except Exception as exc:  # pragma: no cover - 仅作为安全兜底
        print(f"警告: 同步 conditions 主键序列失败: {exc}")
