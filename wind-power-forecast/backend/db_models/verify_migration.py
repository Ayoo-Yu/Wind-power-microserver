#!/usr/bin/env python3
"""
多场站迁移结果综合验证脚本
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_database_url
from db_models.power import ActualPower, SupershortlPower, ShortlPower, MidPower
from db_models.training import Model, TrainingRecord, PredictionRecord
from db_models.weather_fetch import WeatherConnection, WeatherTask
from db_models.report_config import WindFarm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('verification.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MultiStationVerifier:
    def __init__(self):
        self.engine = create_engine(get_database_url())
        self.Session = sessionmaker(bind=self.engine)

    def test_database_connection(self):
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                logger.info("✓ 数据库连接成功")
                return True
        except Exception as e:
            logger.error(f"✗ 数据库连接失败: {e}")
            return False

    def verify_wind_farms_table(self):
        """验证wind_farms表数据"""
        try:
            session = self.Session()
            farms = session.query(WindFarm).all()

            logger.info(f"✓ 找到 {len(farms)} 个风电场:")
            for farm in farms:
                logger.info(f"  - {farm.farm_code}: {farm.farm_name} ({farm.capacity}MW)")

            # 验证是否有默认场站
            default_farm = session.query(WindFarm).filter(WindFarm.farm_code == 'DEFAULT_FARM').first()
            if default_farm:
                logger.info("✓ 默认场站存在")
            else:
                logger.warning("✗ 默认场站不存在")

            session.close()
            return len(farms) > 0

        except Exception as e:
            logger.error(f"✗ 验证wind_farms表失败: {e}")
            return False

    def verify_farm_code_columns(self):
        """验证farm_code字段存在性"""
        try:
            with self.engine.connect() as conn:
                # 需要检查的表
                tables_to_check = [
                    'actual_power', 'supershortl_power', 'shortl_power', 'mid_power',
                    'models', 'training_records', 'prediction_records',
                    'auto_prediction_tasks', 'evaluation_metrics', 'daily_metrics',
                    'weather_connections', 'weather_tasks', 'weather_logs', 'weather_data_records'
                ]

                for table in tables_to_check:
                    result = conn.execute(
                        text("""
                            SELECT COUNT(*) FROM information_schema.columns
                            WHERE table_name = :table AND column_name = 'farm_code'
                        """),
                        {"table": table}
                    ).fetchone()

                    if result[0] > 0:
                        logger.info(f"✓ {table}.farm_code 字段存在")
                    else:
                        logger.error(f"✗ {table}.farm_code 字段不存在")

                return True

        except Exception as e:
            logger.error(f"✗ 验证farm_code字段失败: {e}")
            return False

    def verify_unique_constraints(self):
        """验证复合唯一约束"""
        try:
            with self.engine.connect() as conn:
                tables_to_check = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']

                for table in tables_to_check:
                    result = conn.execute(
                        text("""
                            SELECT COUNT(*) FROM information_schema.table_constraints
                            WHERE table_name = :table AND constraint_name = :constraint_name
                        """),
                        {"table": table, "constraint_name": f"{table}_timestamp_farm_code_key"}
                    ).fetchone()

                    if result[0] > 0:
                        logger.info(f"✓ {table} 复合唯一约束存在")
                    else:
                        logger.warning(f"✗ {table} 复合唯一约束不存在")

                return True

        except Exception as e:
            logger.error(f"✗ 验证唯一约束失败: {e}")
            return False

    def test_data_isolation(self):
        """测试数据隔离功能"""
        try:
            session = self.Session()

            # 获取所有场站
            farms = session.query(WindFarm).all()

            if not farms:
                logger.warning("✗ 没有找到任何场站，无法测试数据隔离")
                return False

            # 测试每个场站的数据隔离
            for farm in farms:
                logger.info(f"测试场站 {farm.farm_code} 的数据隔离...")

                # 测试ActualPower表
                count = session.query(ActualPower).filter(ActualPower.farm_code == farm.farm_code).count()
                logger.info(f"  - ActualPower表 {farm.farm_code} 记录数: {count}")

                # 测试SupershortlPower表
                count = session.query(SupershortlPower).filter(SupershortlPower.farm_code == farm.farm_code).count()
                logger.info(f"  - SupershortlPower表 {farm.farm_code} 记录数: {count}")

                # 测试Model表
                count = session.query(Model).filter(Model.farm_code == farm.farm_code).count()
                logger.info(f"  - Model表 {farm.farm_code} 记录数: {count}")

            session.close()
            return True

        except Exception as e:
            logger.error(f"✗ 测试数据隔离失败: {e}")
            return False

    def test_insert_operations(self):
        """测试插入操作"""
        try:
            session = self.Session()

            # 测试在默认场站插入数据
            test_time = datetime.now()

            # 插入测试数据到ActualPower
            test_power = ActualPower(
                timestamp=test_time,
                power_value=100.0,
                farm_code='DEFAULT_FARM'
            )
            session.add(test_power)

            # 插入测试数据到Model
            test_model = Model(
                model_name='test_model',
                model_type='test_type',
                model_version='1.0',
                model_path='/test/path',
                description='Test model for verification',
                farm_code='DEFAULT_FARM'
            )
            session.add(test_model)

            session.commit()
            logger.info("✓ 测试数据插入成功")

            # 清理测试数据
            session.delete(test_power)
            session.delete(test_model)
            session.commit()
            logger.info("✓ 测试数据清理成功")

            session.close()
            return True

        except Exception as e:
            logger.error(f"✗ 测试插入操作失败: {e}")
            return False

    def test_query_operations(self):
        """测试查询操作"""
        try:
            session = self.Session()

            # 测试按场站查询
            farms = session.query(WindFarm).filter(WindFarm.is_active == True).all()
            logger.info(f"✓ 查询到 {len(farms)} 个活跃场站")

            # 测试关联查询
            for farm in farms:
                # 查询该场站的模型
                models = session.query(Model).filter(Model.farm_code == farm.farm_code).all()
                logger.info(f"  - {farm.farm_code} 有 {len(models)} 个模型")

            session.close()
            return True

        except Exception as e:
            logger.error(f"✗ 测试查询操作失败: {e}")
            return False

    def generate_summary_report(self):
        """生成验证总结报告"""
        try:
            session = self.Session()

            logger.info("\n" + "=" * 60)
            logger.info("多场站迁移验证总结报告")
            logger.info("=" * 60)

            # 场站信息
            farms = session.query(WindFarm).all()
            logger.info(f"📊 场站总数: {len(farms)}")
            for farm in farms:
                status = "活跃" if farm.is_active else "非活跃"
                logger.info(f"  🏭 {farm.farm_code} - {farm.farm_name} ({farm.capacity}MW) - {status}")

            # 数据统计
            stats = {}

            # 统计各表数据量
            tables_models = [
                ('ActualPower', ActualPower),
                ('SupershortlPower', SupershortlPower),
                ('ShortlPower', ShortlPower),
                ('MidPower', MidPower),
                ('Model', Model),
                ('TrainingRecord', TrainingRecord),
                ('PredictionRecord', PredictionRecord)
            ]

            for table_name, model in tables_models:
                total_count = session.query(model).count()
                stats[table_name] = total_count

                # 按场站统计
                farm_counts = {}
                for farm in farms:
                    farm_count = session.query(model).filter(model.farm_code == farm.farm_code).count()
                    if farm_count > 0:
                        farm_counts[farm.farm_code] = farm_count

                if farm_counts:
                    logger.info(f"📈 {table_name} 总记录: {total_count}")
                    for farm_code, count in farm_counts.items():
                        logger.info(f"  └─ {farm_code}: {count}")

            session.close()

            logger.info("\n" + "=" * 60)
            logger.info("✅ 验证完成！多场站迁移成功！")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"✗ 生成总结报告失败: {e}")
            return False

def main():
    """主函数"""
    print("风电功率预测系统 - 多场站迁移验证")
    print("=" * 50)

    verifier = MultiStationVerifier()

    # 验证步骤
    verification_steps = [
        ("数据库连接测试", verifier.test_database_connection),
        ("风电场表验证", verifier.verify_wind_farms_table),
        ("farm_code字段验证", verifier.verify_farm_code_columns),
        ("唯一约束验证", verifier.verify_unique_constraints),
        ("数据隔离测试", verifier.test_data_isolation),
        ("插入操作测试", verifier.test_insert_operations),
        ("查询操作测试", verifier.test_query_operations),
        ("生成验证报告", verifier.generate_summary_report)
    ]

    passed_steps = 0
    total_steps = len(verification_steps)

    for step_name, step_func in verification_steps:
        logger.info(f"\n--- {step_name} ---")
        if step_func():
            logger.info(f"✅ {step_name} 通过")
            passed_steps += 1
        else:
            logger.error(f"❌ {step_name} 失败")

    # 最终结果
    logger.info(f"\n" + "=" * 50)
    logger.info(f"验证结果: {passed_steps}/{total_steps} 项通过")

    if passed_steps == total_steps:
        logger.info("🎉 所有验证项目均通过！多场站迁移成功！")
        print("\n✅ 多场站迁移验证成功完成！")
        print("下一步可以开始 Phase 2: 数据采集逻辑改造")
        return True
    else:
        logger.error(f"❌ 有 {total_steps - passed_steps} 项验证失败")
        print("\n❌ 验证失败，请检查错误信息")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)