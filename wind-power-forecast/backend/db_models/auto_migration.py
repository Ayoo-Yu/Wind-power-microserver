#!/usr/bin/env python3
"""
自动执行多场站迁移脚本（跳过用户确认）
"""
import os
import sys
import logging
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_database_url
from multi_station_migration import MultiStationMigration

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    print("风电功率预测系统 - 自动多场站迁移")
    print("=" * 50)

    migration = MultiStationMigration()

    # 直接执行迁移，跳过用户确认
    logger.info("开始自动执行多场站适配迁移...")

    if migration.run_migration():
        print("迁移执行成功！")
        print("请检查迁移日志文件: auto_migration.log")
        print("\n下一步：运行功能测试")
        print("命令: python db_models/test_multi_station.py")
    else:
        print("迁移执行失败，请检查日志文件")
        sys.exit(1)

if __name__ == "__main__":
    main()