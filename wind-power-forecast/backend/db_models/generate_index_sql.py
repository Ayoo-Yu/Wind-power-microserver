#!/usr/bin/env python3
"""
数据库索引SQL生成脚本
生成所有索引优化的SQL语句，供手动执行
"""

import os

def generate_phase1_indexes():
    """生成Phase 1索引SQL"""
    sql_statements = []

    sql_statements.append("-- Phase 1: 高优先级时间序列索引")
    sql_statements.append("-- 目标: 为功率预测数据表添加时间戳+场站复合索引")
    sql_statements.append("")

    indexes = [
        {
            'name': 'idx_actual_power_timestamp_farm',
            'table': 'actual_power',
            'columns': 'timestamp, farm_code',
            'comment': '-- 实际功率表时间戳+场站复合索引'
        },
        {
            'name': 'idx_supershortl_power_timestamp_farm',
            'table': 'supershortl_power',
            'columns': 'timestamp, farm_code',
            'comment': '-- 超短期预测表时间戳+场站复合索引'
        },
        {
            'name': 'idx_shortl_power_timestamp_farm',
            'table': 'shortl_power',
            'columns': 'timestamp, farm_code',
            'comment': '-- 短期预测表时间戳+场站复合索引'
        },
        {
            'name': 'idx_mid_power_timestamp_farm',
            'table': 'mid_power',
            'columns': 'timestamp, farm_code',
            'comment': '-- 中期预测表时间戳+场站复合索引'
        },
        {
            'name': 'idx_daily_metrics_date_farm',
            'table': 'daily_metrics',
            'columns': 'date, farm_code',
            'comment': '-- 每日指标表日期+场站复合索引'
        }
    ]

    for idx in indexes:
        sql_statements.append(idx['comment'])
        sql_statements.append(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx['name']}")
        sql_statements.append(f"ON {idx['table']}({idx['columns']});")
        sql_statements.append("")

    return sql_statements

def generate_phase2_indexes():
    """生成Phase 2索引SQL"""
    sql_statements = []

    sql_statements.append("-- Phase 2: 高优先级运营数据索引")
    sql_statements.append("-- 目标: 为运营数据表添加时间戳+场站复合索引，优化数据上传性能")
    sql_statements.append("")

    indexes = [
        {
            'name': 'idx_wind_speed_data_timestamp_farm',
            'table': 'wind_speed_data',
            'columns': 'timestamp, farm_code',
            'comment': '-- 风速数据表时间戳+场站复合索引'
        },
        {
            'name': 'idx_turbine_power_data_timestamp_farm',
            'table': 'turbine_power_data',
            'columns': 'timestamp, farm_code',
            'comment': '-- 功率数据表时间戳+场站复合索引'
        },
        {
            'name': 'idx_weather_data_timestamp_farm',
            'table': 'weather_data',
            'columns': 'timestamp, farm_code',
            'comment': '-- 气象数据表时间戳+场站复合索引'
        },
        {
            'name': 'idx_installed_capacity_timestamp_farm',
            'table': 'installed_capacity_data',
            'columns': 'timestamp, farm_code',
            'comment': '-- 装机容量表时间戳+场站复合索引'
        },
        {
            'name': 'idx_available_capacity_timestamp_farm',
            'table': 'available_capacity_data',
            'columns': 'timestamp, farm_code',
            'comment': '-- 可用容量表时间戳+场站复合索引'
        },
        {
            'name': 'idx_theoretical_power_timestamp_farm',
            'table': 'theoretical_power_data',
            'columns': 'timestamp, farm_code',
            'comment': '-- 理论功率表时间戳+场站复合索引'
        },
        {
            'name': 'idx_available_power_timestamp_farm',
            'table': 'available_power_data',
            'columns': 'timestamp, farm_code',
            'comment': '-- 可用功率表时间戳+场站复合索引'
        }
    ]

    for idx in indexes:
        sql_statements.append(idx['comment'])
        sql_statements.append(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx['name']}")
        sql_statements.append(f"ON {idx['table']}({idx['columns']});")
        sql_statements.append("")

    return sql_statements

def generate_phase3_indexes():
    """生成Phase 3索引SQL"""
    sql_statements = []

    sql_statements.append("-- Phase 3: 中优先级报表查询索引")
    sql_statements.append("-- 目标: 为报表相关表添加复合索引，优化多场站报表查询性能")
    sql_statements.append("")

    indexes = [
        {
            'name': 'idx_report_quality_farm_type_date',
            'table': 'report_quality_statistics',
            'columns': 'farm_code, report_type, date',
            'comment': '-- 报表质量统计表场站+类型+日期复合索引'
        },
        {
            'name': 'idx_report_logs_farm_type_time',
            'table': 'report_logs',
            'columns': 'farm_code, report_type, report_time',
            'comment': '-- 报表日志表场站+类型+时间复合索引'
        },
        {
            'name': 'idx_report_quality_farm_date',
            'table': 'report_quality_statistics',
            'columns': 'farm_code, date',
            'comment': '-- 报表质量统计表场站+日期复合索引'
        },
        {
            'name': 'idx_report_logs_config_time',
            'table': 'report_logs',
            'columns': 'config_id, report_time',
            'comment': '-- 报表日志表配置+时间复合索引'
        }
    ]

    for idx in indexes:
        sql_statements.append(idx['comment'])
        sql_statements.append(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx['name']}")
        sql_statements.append(f"ON {idx['table']}({idx['columns']});")
        sql_statements.append("")

    return sql_statements

def generate_phase4_indexes():
    """生成Phase 4索引SQL"""
    sql_statements = []

    sql_statements.append("-- Phase 4: 专用查询索引")
    sql_statements.append("-- 目标: 为风机级别分析添加专用索引，优化深度分析查询")
    sql_statements.append("")

    indexes = [
        {
            'name': 'idx_turbine_power_farm_turbine_time',
            'table': 'turbine_power_data',
            'columns': 'farm_code, turbine_id, timestamp',
            'comment': '-- 功率数据表场站+风机+时间复合索引'
        },
        {
            'name': 'idx_wind_speed_farm_turbine_time',
            'table': 'wind_speed_data',
            'columns': 'farm_code, turbine_id, timestamp',
            'comment': '-- 风速数据表场站+风机+时间复合索引'
        },
        {
            'name': 'idx_turbine_power_turbine_time',
            'table': 'turbine_power_data',
            'columns': 'turbine_id, timestamp',
            'comment': '-- 功率数据表风机+时间复合索引'
        },
        {
            'name': 'idx_wind_speed_turbine_time',
            'table': 'wind_speed_data',
            'columns': 'turbine_id, timestamp',
            'comment': '-- 风速数据表风机+时间复合索引'
        },
        {
            'name': 'idx_turbine_power_status_time',
            'table': 'turbine_power_data',
            'columns': 'turbine_status, timestamp',
            'comment': '-- 功率数据表状态+时间复合索引'
        },
        {
            'name': 'idx_turbine_power_active_power_time',
            'table': 'turbine_power_data',
            'columns': 'active_power, timestamp',
            'comment': '-- 功率数据表有功功率+时间复合索引'
        }
    ]

    for idx in indexes:
        sql_statements.append(idx['comment'])
        sql_statements.append(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx['name']}")
        sql_statements.append(f"ON {idx['table']}({idx['columns']});")
        sql_statements.append("")

    return sql_statements

def generate_drop_indexes():
    """生成删除索引的SQL"""
    sql_statements = []

    sql_statements.append("-- 索引回滚脚本")
    sql_statements.append("-- 删除所有优化索引，回滚到优化前状态")
    sql_statements.append("")

    # 所有创建的索引名称
    all_indexes = [
        'idx_actual_power_timestamp_farm',
        'idx_supershortl_power_timestamp_farm',
        'idx_shortl_power_timestamp_farm',
        'idx_mid_power_timestamp_farm',
        'idx_daily_metrics_date_farm',
        'idx_wind_speed_data_timestamp_farm',
        'idx_turbine_power_data_timestamp_farm',
        'idx_weather_data_timestamp_farm',
        'idx_installed_capacity_timestamp_farm',
        'idx_available_capacity_timestamp_farm',
        'idx_theoretical_power_timestamp_farm',
        'idx_available_power_timestamp_farm',
        'idx_report_quality_farm_type_date',
        'idx_report_logs_farm_type_time',
        'idx_report_quality_farm_date',
        'idx_report_logs_config_time',
        'idx_turbine_power_farm_turbine_time',
        'idx_wind_speed_farm_turbine_time',
        'idx_turbine_power_turbine_time',
        'idx_wind_speed_turbine_time',
        'idx_turbine_power_status_time',
        'idx_turbine_power_active_power_time'
    ]

    for index_name in all_indexes:
        sql_statements.append(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name};")

    return sql_statements

def generate_verification_sql():
    """生成验证索引的SQL"""
    sql_statements = []

    sql_statements.append("-- 索引验证脚本")
    sql_statements.append("-- 检查所有优化索引是否创建成功")
    sql_statements.append("")

    sql_statements.append("-- 检查Phase 1索引")
    sql_statements.append("SELECT indexname, tablename FROM pg_indexes")
    sql_statements.append("WHERE tablename IN ('actual_power', 'supershortl_power', 'shortl_power', 'mid_power', 'daily_metrics')")
    sql_statements.append("AND indexname LIKE '%_timestamp_farm' OR indexname LIKE '%_date_farm'")
    sql_statements.append("ORDER BY tablename, indexname;")
    sql_statements.append("")

    sql_statements.append("-- 检查Phase 2索引")
    sql_statements.append("SELECT indexname, tablename FROM pg_indexes")
    sql_statements.append("WHERE tablename IN ('wind_speed_data', 'turbine_power_data', 'weather_data',")
    sql_statements.append("'installed_capacity_data', 'available_capacity_data', 'theoretical_power_data', 'available_power_data')")
    sql_statements.append("AND indexname LIKE '%_timestamp_farm'")
    sql_statements.append("ORDER BY tablename, indexname;")
    sql_statements.append("")

    sql_statements.append("-- 检查Phase 3索引")
    sql_statements.append("SELECT indexname, tablename FROM pg_indexes")
    sql_statements.append("WHERE tablename IN ('report_quality_statistics', 'report_logs')")
    sql_statements.append("AND indexname LIKE 'idx_%_farm_%' OR indexname LIKE 'idx_%_config_%'")
    sql_statements.append("ORDER BY tablename, indexname;")
    sql_statements.append("")

    sql_statements.append("-- 检查Phase 4索引")
    sql_statements.append("SELECT indexname, tablename FROM pg_indexes")
    sql_statements.append("WHERE tablename IN ('turbine_power_data', 'wind_speed_data')")
    sql_statements.append("AND indexname LIKE 'idx_turbine%' OR indexname LIKE 'idx_wind_speed%'")
    sql_statements.append("ORDER BY tablename, indexname;")
    sql_statements.append("")

    sql_statements.append("-- 检查索引使用统计")
    sql_statements.append("SELECT schemaname, tablename, indexname, idx_scan as index_scans,")
    sql_statements.append("pg_size_pretty(pg_relation_size(indexrelid)) as index_size")
    sql_statements.append("FROM pg_stat_user_indexes")
    sql_statements.append("WHERE indexname LIKE 'idx_%'")
    sql_statements.append("ORDER BY idx_scan DESC, tablename, indexname;")

    return sql_statements

def main():
    """主函数"""
    print("风电功率预测系统 - 数据库索引SQL生成")
    print("=" * 50)

    # 生成所有SQL
    all_sql = []

    all_sql.extend(generate_phase1_indexes())
    all_sql.append("")

    all_sql.extend(generate_phase2_indexes())
    all_sql.append("")

    all_sql.extend(generate_phase3_indexes())
    all_sql.append("")

    all_sql.extend(generate_phase4_indexes())
    all_sql.append("")

    all_sql.extend(generate_drop_indexes())
    all_sql.append("")

    all_sql.extend(generate_verification_sql())

    # 写入文件
    output_file = "database_indexes.sql"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- 风电功率预测系统 - 数据库索引优化完整SQL脚本\n")
        f.write("-- 生成时间: " + os.popen('date /t').read().strip() + " " + os.popen('time /t').read().strip() + "\n")
        f.write("-- \n")
        f.write("-- 使用说明:\n")
        f.write("-- 1. 建议按Phase顺序执行，每个Phase执行后观察系统性能\n")
        f.write("-- 2. 使用CONCURRENTLY创建索引，避免锁表影响生产环境\n")
        f.write("-- 3. 如果出现问题，可以使用回滚脚本删除所有索引\n")
        f.write("-- 4. 执行完成后可以使用验证脚本检查索引创建情况\n")
        f.write("-- \n\n")

        for line in all_sql:
            f.write(line + "\n")

    print(f"SQL脚本已生成到文件: {output_file}")
    print(f"包含 {len([line for line in all_sql if line.strip().startswith('CREATE INDEX')])} 个创建索引语句")
    print(f"包含 {len([line for line in all_sql if line.strip().startswith('DROP INDEX')])} 个删除索引语句")
    print(f"包含 {len([line for line in all_sql if line.strip().startswith('SELECT')])} 个验证查询语句")
    print("\n使用方法:")
    print("1. 在数据库客户端中打开此SQL文件")
    print("2. 按Phase顺序执行索引创建")
    print("3. 观察系统性能变化")
    print("4. 使用验证语句检查索引状态")

if __name__ == "__main__":
    main()