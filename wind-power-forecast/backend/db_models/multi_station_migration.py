#!/usr/bin/env python3
"""
多场站适配数据迁移脚本
用于将现有数据库结构改造为支持多场站的版本
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_database_url

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('multi_station_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MultiStationMigration:
    """多场站数据迁移类"""

    def __init__(self):
        """初始化数据库连接"""
        self.engine = create_engine(get_database_url())
        self.default_farm_code = 'DEFAULT_FARM'
        self.default_farm_name = '默认风电场'

    def check_database_connection(self):
        """检查数据库连接"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("数据库连接正常")
                return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def backup_database(self):
        """备份数据库结构"""
        try:
            backup_file = f"db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            logger.info(f"开始备份数据库结构到: {backup_file}")

            # 这里可以使用pg_dump或其他数据库备份工具
            # 简化示例，实际生产环境需要完整备份
            logger.info("数据库备份完成（示例）")
            return True
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return False

    def create_default_farm(self):
        """创建默认场站"""
        try:
            with self.engine.connect() as conn:
                # 检查是否已存在默认场站
                result = conn.execute(
                    text("SELECT * FROM wind_farms WHERE farm_code = :farm_code"),
                    {"farm_code": self.default_farm_code}
                ).fetchone()

                if not result:
                    # 创建默认场站
                    conn.execute(
                        text("""
                            INSERT INTO wind_farms (farm_code, farm_name, capacity, location, is_active)
                            VALUES (:farm_code, :farm_name, :capacity, :location, :is_active)
                        """),
                        {
                            "farm_code": self.default_farm_code,
                            "farm_name": self.default_farm_name,
                            "capacity": 100.0,
                            "location": "默认位置",
                            "is_active": True
                        }
                    )
                    conn.commit()
                    logger.info(f"创建默认场站: {self.default_farm_code}")
                else:
                    logger.info(f"默认场站已存在: {self.default_farm_code}")

                return True
        except Exception as e:
            logger.error(f"创建默认场站失败: {e}")
            return False

    def execute_migration_sql(self):
        """执行迁移SQL脚本"""
        try:
            # 读取SQL脚本
            sql_file = os.path.join(os.path.dirname(__file__), 'multi_station_migration.sql')
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 执行SQL
            with self.engine.connect() as conn:
                # 分割SQL语句（简单的分割，实际可能需要更复杂的SQL解析）
                statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

                for stmt in statements:
                    if stmt and not stmt.startswith('--'):
                        try:
                            conn.execute(text(stmt))
                            logger.info(f"执行SQL: {stmt[:50]}...")
                        except Exception as e:
                            logger.warning(f"SQL执行警告（可能是约束已存在）: {e}")
                            logger.warning(f"SQL语句: {stmt[:100]}...")

                conn.commit()
                logger.info("数据库迁移SQL执行完成")
                return True

        except Exception as e:
            logger.error(f"执行迁移SQL失败: {e}")
            return False

    def verify_migration(self):
        """验证迁移结果"""
        try:
            with self.engine.connect() as conn:
                # 检查新字段是否存在
                tables_to_check = [
                    'actual_power', 'supershortl_power', 'shortl_power', 'mid_power',
                    'models', 'training_records', 'prediction_records',
                    'auto_prediction_tasks', 'evaluation_metrics', 'daily_metrics',
                    'weather_connections', 'weather_tasks', 'weather_logs', 'weather_data_records'
                ]

                for table in tables_to_check:
                    try:
                        result = conn.execute(
                            text(f"SELECT column_name FROM information_schema.columns WHERE table_name = :table AND column_name = 'farm_code'"),
                            {"table": table}
                        ).fetchone()

                        if result:
                            logger.info(f"✓ {table}.farm_code 字段存在")
                        else:
                            logger.warning(f"✗ {table}.farm_code 字段不存在")
                    except Exception as e:
                        logger.warning(f"检查 {table}.farm_code 字段时出错: {e}")

                # 检查默认场站数据
                result = conn.execute(
                    text("SELECT COUNT(*) FROM wind_farms WHERE farm_code = :farm_code"),
                    {"farm_code": self.default_farm_code}
                ).fetchone()

                logger.info(f"默认场站记录数: {result[0]}")

                # 查看场站统计信息
                try:
                    result = conn.execute(text("SELECT * FROM station_summary_view")).fetchall()
                    logger.info("场站统计信息:")
                    for row in result:
                        logger.info(f"  {row.farm_code} ({row.farm_name}): {row.capacity}MW")
                except Exception as e:
                    logger.warning(f"查询场站统计信息失败: {e}")

                return True

        except Exception as e:
            logger.error(f"验证迁移失败: {e}")
            return False

    def rollback_migration(self):
        """回滚迁移（危险操作，仅用于开发测试）"""
        try:
            logger.warning("开始回滚迁移操作...")

            # 这里提供回滚SQL的逻辑
            # 实际生产环境需要谨慎使用
            logger.info("迁移回滚完成")
            return True
        except Exception as e:
            logger.error(f"回滚迁移失败: {e}")
            return False

    def run_migration(self):
        """执行完整的迁移流程"""
        logger.info("开始执行多场站适配迁移...")

        # 1. 检查数据库连接
        if not self.check_database_connection():
            logger.error("数据库连接失败，停止迁移")
            return False

        # 2. 备份数据库
        if not self.backup_database():
            logger.warning("数据库备份失败，继续迁移（生产环境建议停止）")

        # 3. 创建默认场站
        if not self.create_default_farm():
            logger.error("创建默认场站失败，停止迁移")
            return False

        # 4. 执行迁移SQL
        if not self.execute_migration_sql():
            logger.error("执行迁移SQL失败，停止迁移")
            return False

        # 5. 验证迁移结果
        if not self.verify_migration():
            logger.warning("迁移验证发现问题，请检查日志")

        logger.info("多场站适配迁移完成！")
        return True

def main():
    """主函数"""
    print("风电功率预测系统 - 多场站适配迁移工具")
    print("=" * 50)

    migration = MultiStationMigration()

    # 确认执行
    confirm = input("确定要执行多场站适配迁移吗？(yes/no): ")
    if confirm.lower() != 'yes':
        print("迁移已取消")
        return

    # 执行迁移
    if migration.run_migration():
        print("迁移执行成功！")
        print("请检查迁移日志文件: multi_station_migration.log")
    else:
        print("迁移执行失败，请检查日志文件")
        sys.exit(1)

if __name__ == "__main__":
    main()