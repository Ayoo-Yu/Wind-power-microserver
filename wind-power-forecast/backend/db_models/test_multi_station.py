#!/usr/bin/env python3
"""
多场站功能测试脚本
用于验证多场站数据存储和查询功能
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_database_url
from db_models import Base, ActualPower, SupershortlPower, ShortlPower, MidPower, WindFarm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MultiStationTester:
    """多场站功能测试类"""

    def __init__(self):
        """初始化测试环境"""
        self.engine = create_engine(get_database_url())
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # 测试场站数据
        self.test_stations = [
            {'farm_code': 'TEST_FARM_001', 'farm_name': '测试风电场1', 'capacity': 50.0},
            {'farm_code': 'TEST_FARM_002', 'farm_name': '测试风电场2', 'capacity': 80.0},
            {'farm_code': 'TEST_FARM_003', 'farm_name': '测试风电场3', 'capacity': 120.0}
        ]

    def create_test_stations(self):
        """创建测试场站"""
        try:
            session = self.SessionLocal()

            # 清理旧的测试数据
            session.query(WindFarm).filter(WindFarm.farm_code.like('TEST_FARM_%')).delete()
            session.commit()

            # 创建测试场站
            for station_data in self.test_stations:
                station = WindFarm(**station_data)
                session.add(station)
                logger.info(f"创建测试场站: {station_data['farm_code']}")

            session.commit()
            logger.info(f"成功创建 {len(self.test_stations)} 个测试场站")
            return True

        except Exception as e:
            logger.error(f"创建测试场站失败: {e}")
            if 'session' in locals():
                session.rollback()
            return False
        finally:
            if 'session' in locals():
                session.close()

    def test_actual_power_data(self):
        """测试实际功率数据的多场站存储"""
        try:
            session = self.SessionLocal()

            # 生成测试数据
            base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # 清理旧的测试数据
            session.query(ActualPower).filter(ActualPower.farm_code.like('TEST_FARM_%')).delete()
            session.commit()

            # 为每个场站生成24小时的数据
            for station in self.test_stations:
                for hour in range(24):
                    timestamp = base_time + timedelta(hours=hour)

                    # 生成模拟功率数据（白天高，夜晚低）
                    if 6 <= hour <= 18:
                        power = station['capacity'] * (0.3 + 0.6 * (hour - 6) / 12)  # 30%-90%
                    else:
                        power = station['capacity'] * 0.2  # 夜晚20%

                    actual_power = ActualPower(
                        timestamp=timestamp,
                        farm_code=station['farm_code'],
                        wp_true=power
                    )
                    session.add(actual_power)

            session.commit()
            logger.info("实际功率数据插入完成")
            return True

        except Exception as e:
            logger.error(f"测试实际功率数据失败: {e}")
            if 'session' in locals():
                session.rollback()
            return False
        finally:
            if 'session' in locals():
                session.close()

    def test_prediction_data(self):
        """测试预测数据的多场站存储"""
        try:
            session = self.SessionLocal()

            # 清理旧的测试数据
            session.query(SupershortlPower).filter(SupershortlPower.farm_code.like('TEST_FARM_%')).delete()
            session.query(ShortlPower).filter(ShortlPower.farm_code.like('TEST_FARM_%')).delete()
            session.query(MidPower).filter(MidPower.farm_code.like('TEST_FARM_%')).delete()
            session.commit()

            base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # 为每个场站生成预测数据
            for station in self.test_stations:
                for hour in range(24):
                    timestamp = base_time + timedelta(hours=hour)

                    # 超短期预测（未来16个点）
                    supershort = SupershortlPower(
                        timestamp=timestamp,
                        farm_code=station['farm_code'],
                        wp_pred2=station['capacity'] * 0.4,
                        wp_pred3=station['capacity'] * 0.45,
                        wp_pred4=station['capacity'] * 0.5,
                        wp_pred5=station['capacity'] * 0.55,
                        wp_pred6=station['capacity'] * 0.6,
                        wp_pred7=station['capacity'] * 0.65,
                        wp_pred8=station['capacity'] * 0.7,
                        wp_pred9=station['capacity'] * 0.75,
                        wp_pred10=station['capacity'] * 0.8,
                        wp_pred11=station['capacity'] * 0.75,
                        wp_pred12=station['capacity'] * 0.7,
                        wp_pred13=station['capacity'] * 0.65,
                        wp_pred14=station['capacity'] * 0.6,
                        wp_pred15=station['capacity'] * 0.55,
                        wp_pred16=station['capacity'] * 0.5,
                        wp_pred17=station['capacity'] * 0.45
                    )
                    session.add(supershort)

                    # 短期预测
                    short = ShortlPower(
                        timestamp=timestamp,
                        farm_code=station['farm_code'],
                        wp_pred=station['capacity'] * 0.6,
                        pre_at=timestamp,
                        pre_num=4
                    )
                    session.add(short)

                    # 中期预测
                    mid = MidPower(
                        timestamp=timestamp,
                        farm_code=station['farm_code'],
                        wp_pred=station['capacity'] * 0.55,
                        pre_at=timestamp,
                        pre_num=72
                    )
                    session.add(mid)

            session.commit()
            logger.info("预测数据插入完成")
            return True

        except Exception as e:
            logger.error(f"测试预测数据失败: {e}")
            if 'session' in locals():
                session.rollback()
            return False
        finally:
            if 'session' in locals():
                session.close()

    def test_data_query(self):
        """测试多场站数据查询"""
        try:
            session = self.SessionLocal()

            # 1. 测试按场站查询实际功率
            logger.info("=== 测试按场站查询实际功率 ===")
            for station in self.test_stations:
                result = session.query(ActualPower).filter(
                    ActualPower.farm_code == station['farm_code']
                ).count()
                logger.info(f"{station['farm_code']}: {result} 条实际功率记录")

            # 2. 测试按时间范围查询
            logger.info("=== 测试按时间范围查询 ===")
            start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=6)

            result = session.query(ActualPower).filter(
                ActualPower.timestamp >= start_time,
                ActualPower.timestamp < end_time
            ).all()

            logger.info(f"时间范围查询结果: {len(result)} 条记录")

            # 3. 测试跨场站统计
            logger.info("=== 测试跨场站统计 ===")
            result = session.query(
                ActualPower.farm_code,
                session.query(WindFarm.farm_name).filter(
                    WindFarm.farm_code == ActualPower.farm_code
                ).label('farm_name'),
                session.query(WindFarm.capacity).filter(
                    WindFarm.farm_code == ActualPower.farm_code
                ).label('capacity'),
                session.query(ActualPower.wp_true).filter(
                    ActualPower.farm_code == ActualPower.farm_code
                ).func.avg().label('avg_power')
            ).group_by(ActualPower.farm_code).all()

            for row in result:
                logger.info(f"{row.farm_code}: 平均功率 = {row.avg_power:.2f} MW (容量: {row.capacity} MW)")

            # 4. 测试数据隔离性
            logger.info("=== 测试数据隔离性 ===")
            farm_001_count = session.query(ActualPower).filter(
                ActualPower.farm_code == 'TEST_FARM_001'
            ).count()
            farm_002_count = session.query(ActualPower).filter(
                ActualPower.farm_code == 'TEST_FARM_002'
            ).count()
            farm_003_count = session.query(ActualPower).filter(
                ActualPower.farm_code == 'TEST_FARM_003'
            ).count()

            logger.info(f"TEST_FARM_001: {farm_001_count} 条")
            logger.info(f"TEST_FARM_002: {farm_002_count} 条")
            logger.info(f"TEST_FARM_003: {farm_003_count} 条")

            if farm_001_count == farm_002_count == farm_003_count:
                logger.info("✓ 数据隔离性测试通过")
            else:
                logger.warning("✗ 数据隔离性测试失败")

            return True

        except Exception as e:
            logger.error(f"测试数据查询失败: {e}")
            return False
        finally:
            if 'session' in locals():
                session.close()

    def test_data_integrity(self):
        """测试数据完整性"""
        try:
            session = self.SessionLocal()

            # 1. 检查外键约束
            logger.info("=== 测试外键约束 ===")

            # 查询所有实际功率记录的场站编码是否都存在于wind_farms表中
            result = session.execute(
                text("""
                    SELECT COUNT(*) as invalid_count
                    FROM actual_power ap
                    LEFT JOIN wind_farms wf ON ap.farm_code = wf.farm_code
                    WHERE wf.farm_code IS NULL
                """)
            ).fetchone()

            if result.invalid_count == 0:
                logger.info("✓ 外键约束检查通过")
            else:
                logger.warning(f"✗ 发现 {result.invalid_count} 条无效的场站编码")

            # 2. 检查唯一性约束
            logger.info("=== 测试唯一性约束 ===")
            result = session.execute(
                text("""
                    SELECT timestamp, farm_code, COUNT(*) as duplicate_count
                    FROM actual_power
                    GROUP BY timestamp, farm_code
                    HAVING COUNT(*) > 1
                """)
            ).fetchall()

            if len(result) == 0:
                logger.info("✓ 唯一性约束检查通过")
            else:
                logger.warning(f"✗ 发现 {len(result)} 组重复数据")

            # 3. 检查数据完整性
            logger.info("=== 测试数据完整性 ===")
            for station in self.test_stations:
                # 检查实际功率数据
                actual_count = session.query(ActualPower).filter(
                    ActualPower.farm_code == station['farm_code']
                ).count()

                # 检查超短期预测数据
                supershort_count = session.query(SupershortlPower).filter(
                    SupershortlPower.farm_code == station['farm_code']
                ).count()

                logger.info(f"{station['farm_code']}: 实际功率={actual_count}, 超短期预测={supershort_count}")

            return True

        except Exception as e:
            logger.error(f"测试数据完整性失败: {e}")
            return False
        finally:
            if 'session' in locals():
                session.close()

    def cleanup_test_data(self):
        """清理测试数据"""
        try:
            session = self.SessionLocal()

            # 删除测试数据
            session.query(ActualPower).filter(ActualPower.farm_code.like('TEST_FARM_%')).delete()
            session.query(SupershortlPower).filter(SupershortlPower.farm_code.like('TEST_FARM_%')).delete()
            session.query(ShortlPower).filter(ShortlPower.farm_code.like('TEST_FARM_%')).delete()
            session.query(MidPower).filter(MidPower.farm_code.like('TEST_FARM_%')).delete()
            session.query(WindFarm).filter(WindFarm.farm_code.like('TEST_FARM_%')).delete()

            session.commit()
            logger.info("测试数据清理完成")
            return True

        except Exception as e:
            logger.error(f"清理测试数据失败: {e}")
            if 'session' in locals():
                session.rollback()
            return False
        finally:
            if 'session' in locals():
                session.close()

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始多场站功能测试...")

        tests = [
            ("创建测试场站", self.create_test_stations),
            ("测试实际功率数据", self.test_actual_power_data),
            ("测试预测数据", self.test_prediction_data),
            ("测试数据查询", self.test_data_query),
            ("测试数据完整性", self.test_data_integrity),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            logger.info(f"\n--- 执行测试: {test_name} ---")
            try:
                if test_func():
                    logger.info(f"✓ {test_name} 通过")
                    passed += 1
                else:
                    logger.error(f"✗ {test_name} 失败")
                    failed += 1
            except Exception as e:
                logger.error(f"✗ {test_name} 异常: {e}")
                failed += 1

        # 清理测试数据
        logger.info("\n--- 清理测试数据 ---")
        self.cleanup_test_data()

        # 输出测试结果
        logger.info("\n" + "=" * 50)
        logger.info(f"测试结果: {passed} 通过, {failed} 失败")
        logger.info("=" * 50)

        return failed == 0

def main():
    """主函数"""
    print("风电功率预测系统 - 多场站功能测试")
    print("=" * 50)

    tester = MultiStationTester()

    # 确认执行
    confirm = input("确定要执行多场站功能测试吗？(yes/no): ")
    if confirm.lower() != 'yes':
        print("测试已取消")
        return

    # 运行测试
    if tester.run_all_tests():
        print("所有测试通过！")
    else:
        print("部分测试失败，请检查日志")
        sys.exit(1)

if __name__ == "__main__":
    main()