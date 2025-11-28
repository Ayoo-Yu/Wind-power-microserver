import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from sqlalchemy import text

from database_config import engine


DDL_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='datasets' AND column_name='wind_farm_code') THEN
        ALTER TABLE datasets ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='datasets' AND column_name='wind_farm_id') THEN
        ALTER TABLE datasets ADD COLUMN wind_farm_id INTEGER;
    END IF;
EXCEPTION WHEN others THEN
    RAISE NOTICE '忽略 datasets 上 wind_farm 字段相关变更中的错误: %', SQLERRM;
END $$;
"""


if __name__ == "__main__":
    if engine is None:
        raise SystemExit("数据库引擎不可用，请检查 database_config.py 配置")

    with engine.begin() as conn:
        conn.execute(text(DDL_SQL))

    print("✅ 已尝试为 datasets 表添加 wind_farm_code / wind_farm_id 字段（如已存在则跳过）")
