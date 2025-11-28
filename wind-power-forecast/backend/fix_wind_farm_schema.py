import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from sqlalchemy import text

from database_config import engine


DDL_SQL = """
-- Wind farm support - create tables and columns (idempotent where possible)

-- 1. wind_farms table metadata扩展
ALTER TABLE wind_farms ADD COLUMN IF NOT EXISTS timezone VARCHAR(64);
ALTER TABLE wind_farms ADD COLUMN IF NOT EXISTS config JSON;
ALTER TABLE wind_farms ADD COLUMN IF NOT EXISTS description TEXT;

-- 2. datasets
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='datasets' AND column_name='wind_farm_code') THEN
        ALTER TABLE datasets ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='datasets' AND column_name='wind_farm_id') THEN
        ALTER TABLE datasets ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE datasets ADD CONSTRAINT fk_datasets_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 3. models
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='models' AND column_name='wind_farm_code') THEN
        ALTER TABLE models ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='models' AND column_name='wind_farm_id') THEN
        ALTER TABLE models ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE models ADD CONSTRAINT fk_models_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 4. training_records
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='training_records' AND column_name='wind_farm_code') THEN
        ALTER TABLE training_records ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='training_records' AND column_name='wind_farm_id') THEN
        ALTER TABLE training_records ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE training_records ADD CONSTRAINT fk_training_records_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 5. prediction_records
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='prediction_records' AND column_name='wind_farm_code') THEN
        ALTER TABLE prediction_records ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='prediction_records' AND column_name='wind_farm_id') THEN
        ALTER TABLE prediction_records ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE prediction_records ADD CONSTRAINT fk_prediction_records_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 6. training_history
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='training_history' AND column_name='wind_farm_code') THEN
        ALTER TABLE training_history ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='training_history' AND column_name='wind_farm_id') THEN
        ALTER TABLE training_history ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE training_history ADD CONSTRAINT fk_training_history_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 7. jobs
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='wind_farm_code') THEN
        ALTER TABLE jobs ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='wind_farm_id') THEN
        ALTER TABLE jobs ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE jobs ADD CONSTRAINT fk_jobs_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 8. evaluation_metrics
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='evaluation_metrics' AND column_name='wind_farm_code') THEN
        ALTER TABLE evaluation_metrics ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='evaluation_metrics' AND column_name='wind_farm_id') THEN
        ALTER TABLE evaluation_metrics ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE evaluation_metrics ADD CONSTRAINT fk_evaluation_metrics_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 9. daily_metrics
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='daily_metrics' AND column_name='wind_farm_code') THEN
        ALTER TABLE daily_metrics ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='daily_metrics' AND column_name='wind_farm_id') THEN
        ALTER TABLE daily_metrics ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE daily_metrics ADD CONSTRAINT fk_daily_metrics_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;

-- 10. auto_prediction_tasks
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='auto_prediction_tasks' AND column_name='wind_farm_code') THEN
        ALTER TABLE auto_prediction_tasks ADD COLUMN wind_farm_code VARCHAR(64);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='auto_prediction_tasks' AND column_name='wind_farm_id') THEN
        ALTER TABLE auto_prediction_tasks ADD COLUMN wind_farm_id INTEGER;
        ALTER TABLE auto_prediction_tasks ADD CONSTRAINT fk_auto_prediction_tasks_wind_farm FOREIGN KEY (wind_farm_id) REFERENCES wind_farms(id);
    END IF;
END $$;
"""


if __name__ == "__main__":
    if engine is None:
        raise SystemExit("数据库引擎不可用，请检查 database_config.py 配置")

    with engine.begin() as conn:
        conn.execute(text(DDL_SQL))

    print("✅ 已尝试为 datasets 表添加 wind_farm_code / wind_farm_id 字段（如已存在则跳过）")
