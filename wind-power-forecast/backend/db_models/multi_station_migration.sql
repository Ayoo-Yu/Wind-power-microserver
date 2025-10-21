-- 风电功率预测系统多场站适配数据库迁移脚本
-- 执行时间：YYYY-MM-DD HH:MM:SS
-- 说明：为支持多场站功能，为相关表添加farm_code字段

-- 1. 首先检查是否已存在默认场站
-- 如果wind_farms表为空，创建一个默认场站
INSERT INTO wind_farms (farm_code, farm_name, capacity, location, is_active)
SELECT 'DEFAULT_FARM', '默认风电场', 100.0, '默认位置', true
WHERE NOT EXISTS (SELECT 1 FROM wind_farms WHERE farm_code = 'DEFAULT_FARM');

-- 2. 为功率预测相关表添加farm_code字段
-- ActualPower表
ALTER TABLE actual_power ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_actual_power_farm_code ON actual_power(farm_code);

-- SupershortlPower表
ALTER TABLE supershortl_power ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_supershortl_power_farm_code ON supershortl_power(farm_code);

-- ShortlPower表
ALTER TABLE shortl_power ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_shortl_power_farm_code ON shortl_power(farm_code);

-- MidPower表
ALTER TABLE mid_power ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_mid_power_farm_code ON mid_power(farm_code);

-- 3. 为训练相关表添加farm_code字段
-- Model表
ALTER TABLE models ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_models_farm_code ON models(farm_code);

-- TrainingRecord表
ALTER TABLE training_records ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_training_records_farm_code ON training_records(farm_code);

-- PredictionRecord表
ALTER TABLE prediction_records ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_prediction_records_farm_code ON prediction_records(farm_code);

-- AutoPredictionTask表
ALTER TABLE auto_prediction_tasks ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_auto_prediction_tasks_farm_code ON auto_prediction_tasks(farm_code);

-- EvaluationMetrics表
ALTER TABLE evaluation_metrics ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_evaluation_metrics_farm_code ON evaluation_metrics(farm_code);

-- DailyMetrics表
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_daily_metrics_farm_code ON daily_metrics(farm_code);

-- 4. 为天气数据获取相关表添加farm_code字段
-- WeatherConnection表
ALTER TABLE weather_connections ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_weather_connections_farm_code ON weather_connections(farm_code);

-- WeatherTask表
ALTER TABLE weather_tasks ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_weather_tasks_farm_code ON weather_tasks(farm_code);

-- WeatherLog表
ALTER TABLE weather_logs ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_weather_logs_farm_code ON weather_logs(farm_code);

-- WeatherData表
ALTER TABLE weather_data_records ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM';
CREATE INDEX IF NOT EXISTS idx_weather_data_records_farm_code ON weather_data_records(farm_code);

-- 5. 移除原有unique约束（因为同一个时间点不同场站都会存在数据）
-- ActualPower表
ALTER TABLE actual_power DROP CONSTRAINT IF EXISTS actual_power_timestamp_key;

-- SupershortlPower表
ALTER TABLE supershortl_power DROP CONSTRAINT IF EXISTS supershortl_power_timestamp_key;

-- ShortlPower表
ALTER TABLE shortl_power DROP CONSTRAINT IF EXISTS shortl_power_timestamp_key;

-- MidPower表
ALTER TABLE mid_power DROP CONSTRAINT IF EXISTS mid_power_timestamp_key;

-- 6. 创建新的复合唯一约束（timestamp + farm_code）
ALTER TABLE actual_power ADD CONSTRAINT actual_power_timestamp_farm_code_key UNIQUE (timestamp, farm_code);
ALTER TABLE supershortl_power ADD CONSTRAINT supershortl_power_timestamp_farm_code_key UNIQUE (timestamp, farm_code);
ALTER TABLE shortl_power ADD CONSTRAINT shortl_power_timestamp_farm_code_key UNIQUE (timestamp, farm_code);
ALTER TABLE mid_power ADD CONSTRAINT mid_power_timestamp_farm_code_key UNIQUE (timestamp, farm_code);

-- 7. 创建迁移日志表
CREATE TABLE IF NOT EXISTS migration_logs (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(100) NOT NULL,
    migration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    details TEXT,
    executed_by VARCHAR(50)
);

-- 8. 记录迁移执行情况
INSERT INTO migration_logs (migration_name, status, details, executed_by)
VALUES ('multi_station_migration', 'completed', '为支持多场站功能，为相关表添加farm_code字段', 'system');

-- 9. 创建视图方便查询各场站统计信息
CREATE OR REPLACE VIEW station_summary_view AS
SELECT
    wf.farm_code,
    wf.farm_name,
    wf.capacity,
    COUNT(DISTINCT ap.timestamp) as actual_power_count,
    COUNT(DISTINCT sp.timestamp) as supershort_power_count,
    COUNT(DISTINCT shp.timestamp) as short_power_count,
    COUNT(DISTINCT mp.timestamp) as mid_power_count,
    COUNT(m.id) as model_count,
    COUNT(tr.id) as training_record_count
FROM wind_farms wf
LEFT JOIN actual_power ap ON wf.farm_code = ap.farm_code
LEFT JOIN supershortl_power sp ON wf.farm_code = sp.farm_code
LEFT JOIN shortl_power shp ON wf.farm_code = shp.farm_code
LEFT JOIN mid_power mp ON wf.farm_code = mp.farm_code
LEFT JOIN models m ON wf.farm_code = m.farm_code
LEFT JOIN training_records tr ON wf.farm_code = tr.farm_code
GROUP BY wf.farm_code, wf.farm_name, wf.capacity;

-- 10. 创建检查约束确保farm_code有效
ALTER TABLE actual_power ADD CONSTRAINT actual_power_farm_code_fkey
    FOREIGN KEY (farm_code) REFERENCES wind_farms(farm_code);

ALTER TABLE supershortl_power ADD CONSTRAINT supershortl_power_farm_code_fkey
    FOREIGN KEY (farm_code) REFERENCES wind_farms(farm_code);

ALTER TABLE shortl_power ADD CONSTRAINT shortl_power_farm_code_fkey
    FOREIGN KEY (farm_code) REFERENCES wind_farms(farm_code);

ALTER TABLE mid_power ADD CONSTRAINT mid_power_farm_code_fkey
    FOREIGN KEY (farm_code) REFERENCES wind_farms(farm_code);

-- 迁移完成提示
SELECT '多场站适配迁移执行完成！' as message;
SELECT '默认场站编码: DEFAULT_FARM' as default_station;
SELECT '请执行 SELECT * FROM station_summary_view; 查看各场站统计信息' as next_step;