-- 风电功率预测系统 - 数据库索引优化完整SQL脚本
-- 生成时间: 2025/09/27 周六 15:13
-- 
-- 使用说明:
-- 1. 建议按Phase顺序执行，每个Phase执行后观察系统性能
-- 2. 使用CONCURRENTLY创建索引，避免锁表影响生产环境
-- 3. 如果出现问题，可以使用回滚脚本删除所有索引
-- 4. 执行完成后可以使用验证脚本检查索引创建情况
-- 

-- Phase 1: 高优先级时间序列索引
-- 目标: 为功率预测数据表添加时间戳+场站复合索引

-- 实际功率表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actual_power_timestamp_farm
ON actual_power(timestamp, farm_code);

-- 超短期预测表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_supershortl_power_timestamp_farm
ON supershortl_power(timestamp, farm_code);

-- 短期预测表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_shortl_power_timestamp_farm
ON shortl_power(timestamp, farm_code);

-- 中期预测表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mid_power_timestamp_farm
ON mid_power(timestamp, farm_code);

-- 每日指标表日期+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_metrics_date_farm
ON daily_metrics(date, farm_code);


-- Phase 2: 高优先级运营数据索引
-- 目标: 为运营数据表添加时间戳+场站复合索引，优化数据上传性能

-- 风速数据表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wind_speed_data_timestamp_farm
ON wind_speed_data(timestamp, farm_code);

-- 功率数据表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_turbine_power_data_timestamp_farm
ON turbine_power_data(timestamp, farm_code);

-- 气象数据表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weather_data_timestamp_farm
ON weather_data(timestamp, farm_code);

-- 装机容量表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_installed_capacity_timestamp_farm
ON installed_capacity_data(timestamp, farm_code);

-- 可用容量表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_available_capacity_timestamp_farm
ON available_capacity_data(timestamp, farm_code);

-- 理论功率表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_theoretical_power_timestamp_farm
ON theoretical_power_data(timestamp, farm_code);

-- 可用功率表时间戳+场站复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_available_power_timestamp_farm
ON available_power_data(timestamp, farm_code);


-- Phase 3: 中优先级报表查询索引
-- 目标: 为报表相关表添加复合索引，优化多场站报表查询性能

-- 报表质量统计表场站+类型+日期复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_quality_farm_type_date
ON report_quality_statistics(farm_code, report_type, date);

-- 报表日志表场站+类型+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_logs_farm_type_time
ON report_logs(farm_code, report_type, report_time);

-- 报表质量统计表场站+日期复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_quality_farm_date
ON report_quality_statistics(farm_code, date);

-- 报表日志表配置+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_logs_config_time
ON report_logs(config_id, report_time);


-- Phase 4: 专用查询索引
-- 目标: 为风机级别分析添加专用索引，优化深度分析查询

-- 功率数据表场站+风机+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_turbine_power_farm_turbine_time
ON turbine_power_data(farm_code, turbine_id, timestamp);

-- 风速数据表场站+风机+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wind_speed_farm_turbine_time
ON wind_speed_data(farm_code, turbine_id, timestamp);

-- 功率数据表风机+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_turbine_power_turbine_time
ON turbine_power_data(turbine_id, timestamp);

-- 风速数据表风机+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wind_speed_turbine_time
ON wind_speed_data(turbine_id, timestamp);

-- 功率数据表状态+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_turbine_power_status_time
ON turbine_power_data(turbine_status, timestamp);

-- 功率数据表有功功率+时间复合索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_turbine_power_active_power_time
ON turbine_power_data(active_power, timestamp);


-- 索引回滚脚本
-- 删除所有优化索引，回滚到优化前状态

DROP INDEX CONCURRENTLY IF EXISTS idx_actual_power_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_supershortl_power_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_shortl_power_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_mid_power_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_daily_metrics_date_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_wind_speed_data_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_turbine_power_data_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_weather_data_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_installed_capacity_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_available_capacity_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_theoretical_power_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_available_power_timestamp_farm;
DROP INDEX CONCURRENTLY IF EXISTS idx_report_quality_farm_type_date;
DROP INDEX CONCURRENTLY IF EXISTS idx_report_logs_farm_type_time;
DROP INDEX CONCURRENTLY IF EXISTS idx_report_quality_farm_date;
DROP INDEX CONCURRENTLY IF EXISTS idx_report_logs_config_time;
DROP INDEX CONCURRENTLY IF EXISTS idx_turbine_power_farm_turbine_time;
DROP INDEX CONCURRENTLY IF EXISTS idx_wind_speed_farm_turbine_time;
DROP INDEX CONCURRENTLY IF EXISTS idx_turbine_power_turbine_time;
DROP INDEX CONCURRENTLY IF EXISTS idx_wind_speed_turbine_time;
DROP INDEX CONCURRENTLY IF EXISTS idx_turbine_power_status_time;
DROP INDEX CONCURRENTLY IF EXISTS idx_turbine_power_active_power_time;

-- 索引验证脚本
-- 检查所有优化索引是否创建成功

-- 检查Phase 1索引
SELECT indexname, tablename FROM pg_indexes
WHERE tablename IN ('actual_power', 'supershortl_power', 'shortl_power', 'mid_power', 'daily_metrics')
AND indexname LIKE '%_timestamp_farm' OR indexname LIKE '%_date_farm'
ORDER BY tablename, indexname;

-- 检查Phase 2索引
SELECT indexname, tablename FROM pg_indexes
WHERE tablename IN ('wind_speed_data', 'turbine_power_data', 'weather_data',
'installed_capacity_data', 'available_capacity_data', 'theoretical_power_data', 'available_power_data')
AND indexname LIKE '%_timestamp_farm'
ORDER BY tablename, indexname;

-- 检查Phase 3索引
SELECT indexname, tablename FROM pg_indexes
WHERE tablename IN ('report_quality_statistics', 'report_logs')
AND indexname LIKE 'idx_%_farm_%' OR indexname LIKE 'idx_%_config_%'
ORDER BY tablename, indexname;

-- 检查Phase 4索引
SELECT indexname, tablename FROM pg_indexes
WHERE tablename IN ('turbine_power_data', 'wind_speed_data')
AND indexname LIKE 'idx_turbine%' OR indexname LIKE 'idx_wind_speed%'
ORDER BY tablename, indexname;

-- 检查索引使用统计
SELECT schemaname, tablename, indexname, idx_scan as index_scans,
pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE indexname LIKE 'idx_%'
ORDER BY idx_scan DESC, tablename, indexname;
