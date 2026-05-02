import pandas as pd
import numpy as np
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from db_session import db_session

logger = logging.getLogger(__name__)

class WeatherDataService:
    """气象数据处理服务类（支持多场站）"""

    def __init__(self):
        self.supported_formats = ['.csv', '.txt', '.data']
        self.default_farm_code = ''
        
    def process_weather_file_local(self, file_path: str, 
                                 processing_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理本地气象数据文件（不插入数据库）"""
        try:
            # 1. 文件存在性检查
            if not os.path.exists(file_path):
                raise Exception(f"文件不存在: {file_path}")
            
            # 2. 文件大小检查
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise Exception(f"文件为空: {file_path}")
            
            # 3. 应用处理选项
            if processing_options:
                # 数据完整性校验
                if 'integrity_check' in processing_options:
                    integrity_result = self._check_file_integrity(file_path)
                    if not integrity_result['valid']:
                        raise Exception(f"文件完整性校验失败: {integrity_result['errors']}")
                
                # 如果需要数据验证，读取少量数据进行验证
                if any(opt in processing_options for opt in ['interpolation']):
                    sample_data = self._read_sample_data(file_path)
                    if sample_data is not None:
                        logger.info(f"文件 {file_path} 数据格式验证通过")
            
            return {
                "success": True,
                "file_path": file_path,
                "file_size": file_size,
                "message": "文件保存并验证成功"
            }
            
        except Exception as e:
            logger.error(f"处理本地气象数据文件失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_weather_file(self, file_path: str, target_table: str,
                           processing_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理气象数据文件（支持多场站）"""
        try:
            # 获取场站代码
            farm_code = processing_options.get('farm_code', self.default_farm_code) if processing_options else self.default_farm_code

            # 1. 文件格式检查
            if not self._is_supported_format(file_path):
                raise Exception(f"不支持的文件格式: {file_path}")

            # 2. 读取数据
            df = self._read_weather_data(file_path, processing_options)

            # 3. 数据验证
            validation_result = self._validate_data(df)
            if not validation_result['valid']:
                raise Exception(f"数据验证失败: {validation_result['errors']}")

            # 4. 数据处理（添加场站信息）
            processed_df = self._process_data(df, processing_options, farm_code)

            # 5. 插入数据库（包含场站信息）
            insert_result = self._insert_to_database(processed_df, target_table, farm_code)

            return {
                "success": True,
                "farm_code": farm_code,
                "records_processed": len(df),
                "records_inserted": insert_result['inserted_count'],
                "processing_summary": {
                    "original_records": len(df),
                    "processed_records": len(processed_df),
                    "inserted_records": insert_result['inserted_count']
                }
            }

        except Exception as e:
            logger.error(f"处理气象数据文件失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_supported_format(self, file_path: str) -> bool:
        """检查文件格式是否支持"""
        _, ext = os.path.splitext(file_path)
        return ext.lower() in self.supported_formats
    
    def _read_weather_data(self, file_path: str, options: Dict[str, Any] = None) -> pd.DataFrame:
        """读取气象数据文件"""
        try:
            # 默认选项
            default_options = {
                'separator': ',',
                'header_row': 0,
                'encoding': 'utf-8',
                'skip_rows': 0
            }
            
            if options:
                default_options.update(options.get('read_options', {}))
            
            # 读取文件
            df = pd.read_csv(
                file_path,
                sep=default_options['separator'],
                header=default_options['header_row'],
                encoding=default_options['encoding'],
                skiprows=default_options['skip_rows']
            )
            
            logger.info(f"成功读取文件 {file_path}，共 {len(df)} 行数据")
            return df
            
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            raise Exception(f"读取文件失败: {str(e)}")
    
    def _validate_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """数据验证"""
        errors = []
        
        # 检查数据是否为空
        if df.empty:
            errors.append("数据文件为空")
        
        # 基础列存在性检查（不强制要求所有列）
        basic_columns = ['time'] if len(df.columns) > 0 else []
        if basic_columns:
            missing_basic = [col for col in basic_columns if col not in df.columns]
            if missing_basic:
                # 尝试找时间相关的列
                time_related_cols = [col for col in df.columns if any(keyword in col.lower() 
                                   for keyword in ['time', 'date', 'datetime', '时间', '日期'])]
                if not time_related_cols:
                    errors.append("未找到时间相关列")
        
        # 基础数据类型检查
        try:
            # 尝试读取前几行数据进行基本验证
            if len(df) > 0:
                logger.info(f"数据文件包含 {len(df)} 行，{len(df.columns)} 列")
        except Exception as e:
            errors.append(f"数据格式错误: {str(e)}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    

    
    def _process_data(self, df: pd.DataFrame, options: Dict[str, Any] = None, farm_code: str = None) -> pd.DataFrame:
        """数据处理（插值、单位转换等，支持多场站）"""
        processed_df = df.copy()

        # 添加场站信息
        if farm_code:
            processed_df['farm_code'] = farm_code
            logger.info(f"为数据添加场站标识: {farm_code}")

        if not options:
            return processed_df

        # 基础时间列处理（如果存在）
        time_cols = [col for col in processed_df.columns if any(keyword in col.lower()
                    for keyword in ['time', 'date', 'datetime', '时间', '日期'])]
        if time_cols:
            try:
                main_time_col = time_cols[0]  # 使用第一个找到的时间列
                processed_df[main_time_col] = pd.to_datetime(processed_df[main_time_col])
                logger.info(f"时间列处理成功: {main_time_col}")
            except Exception as e:
                logger.warning(f"时间列处理失败: {e}")

        # 数据插值
        if options.get('interpolate', False):
            numeric_columns = processed_df.select_dtypes(include=[np.number]).columns
            processed_df[numeric_columns] = processed_df[numeric_columns].interpolate(method='linear')

        # 基础缺失值处理（仅在插值选项启用时）
        if options.get('interpolate', False):
            # 对缺失值进行简单处理
            processed_df = processed_df.dropna()

        return processed_df
    

    
    def _insert_to_database(self, df: pd.DataFrame, target_table: str, farm_code: str = None) -> Dict[str, Any]:
        """插入数据到数据库（支持多场站）"""
        try:
            with db_session() as session:
                # 检查目标表是否存在
                table_check_sql = f"""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_name = '{target_table}'
                """
                result = session.execute(text(table_check_sql)).fetchone()

                if result.count == 0:
                    raise Exception(f"目标表 {target_table} 不存在")

                # 准备插入数据
                records_to_insert = df.to_dict('records')
                inserted_count = 0

                # 确保每条记录都有场站信息
                for record in records_to_insert:
                    if 'farm_code' not in record:
                        record['farm_code'] = farm_code or self.default_farm_code

                # 根据目标表动态构建插入语句
                if target_table in ['train_pre_middle', 'train_pre_short', 'train_pre_supershort']:
                    # 风电预测特征表（需要更新以支持farm_code）
                    for record in records_to_insert:
                        try:
                            # 检查表是否有farm_code字段
                            has_farm_code = self._check_table_has_farm_code(session, target_table)

                            if has_farm_code:
                                insert_sql = f"""
                                INSERT INTO {target_table} (
                                    time, temperature, humidity, wind_speed, wind_direction,
                                    farm_code, created_at
                                ) VALUES (
                                    :time, :temperature, :humidity, :wind_speed, :wind_direction,
                                    :farm_code, :created_at
                                )
                                """
                            else:
                                insert_sql = f"""
                                INSERT INTO {target_table} (
                                    time, temperature, humidity, wind_speed, wind_direction,
                                    created_at
                                ) VALUES (
                                    :time, :temperature, :humidity, :wind_speed, :wind_direction,
                                    :created_at
                                )
                                """

                            # 添加创建时间
                            record['created_at'] = datetime.now()

                            session.execute(text(insert_sql), record)
                            inserted_count += 1

                        except Exception as e:
                            logger.warning(f"插入记录失败: {e}")
                            continue

                elif target_table == 'weather_data_records':
                    # 天气数据记录表（支持farm_code）
                    for record in records_to_insert:
                        try:
                            insert_sql = f"""
                            INSERT INTO weather_data_records (
                                timestamp, temperature, humidity, wind_speed, wind_direction,
                                pressure, visibility, precipitation, air_density,
                                farm_code, created_at
                            ) VALUES (
                                :timestamp, :temperature, :humidity, :wind_speed, :wind_direction,
                                :pressure, :visibility, :precipitation, :air_density,
                                :farm_code, :created_at
                            )
                            """

                            # 确保字段映射正确
                            if 'time' in record and 'timestamp' not in record:
                                record['timestamp'] = record['time']

                            # 添加创建时间
                            record['created_at'] = datetime.now()

                            session.execute(text(insert_sql), record)
                            inserted_count += 1

                        except Exception as e:
                            logger.warning(f"插入天气记录失败: {e}")
                            continue

                else:
                    logger.warning(f"不支持的目标表: {target_table}")

                session.commit()

                logger.info(f"成功插入 {inserted_count} 条记录到表 {target_table}，场站: {farm_code}")

                return {
                    "success": True,
                    "inserted_count": inserted_count
                }

        except Exception as e:
            logger.error(f"数据库插入失败: {e}")
            raise Exception(f"数据库插入失败: {str(e)}")

    def _check_table_has_farm_code(self, session, table_name: str) -> bool:
        """检查表是否有farm_code字段"""
        try:
            result = session.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = :table AND column_name = 'farm_code'
            """), {"table": table_name}).fetchone()
            return result[0] > 0
        except Exception as e:
            logger.warning(f"检查表字段失败: {e}")
            return False
    
    def get_table_columns(self, table_name: str) -> List[str]:
        """获取表的列信息"""
        try:
            with db_session() as session:
                sql = f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
                """
                result = session.execute(text(sql)).fetchall()
                return [row.column_name for row in result]
                
        except Exception as e:
            logger.error(f"获取表列信息失败: {e}")
            return []

    def _check_file_integrity(self, file_path: str) -> Dict[str, Any]:
        """检查文件完整性"""
        errors = []
        
        try:
            # 检查文件是否可读
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if not first_line.strip():
                    errors.append("文件第一行为空")
            
            # 检查文件扩展名
            _, ext = os.path.splitext(file_path)
            if ext.lower() not in ['.csv', '.txt', '.data', '.nc', '.grib', '.grib2']:
                errors.append(f"文件格式可能不受支持: {ext}")
            
            # 检查文件大小合理性（不应该太小或太大）
            file_size = os.path.getsize(file_path)
            if file_size < 100:  # 小于100字节
                errors.append("文件大小异常小，可能不完整")
            elif file_size > 1024 * 1024 * 1024:  # 大于1GB
                errors.append("文件大小超过1GB，处理可能较慢")
                
        except Exception as e:
            errors.append(f"文件读取错误: {str(e)}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _read_sample_data(self, file_path: str) -> Optional[pd.DataFrame]:
        """读取文件样本数据进行验证"""
        try:
            # 根据文件扩展名选择读取方式
            _, ext = os.path.splitext(file_path)
            
            if ext.lower() in ['.csv', '.txt']:
                # 读取前几行进行验证
                sample_df = pd.read_csv(file_path, nrows=5, encoding='utf-8')
                logger.info(f"CSV/TXT文件样本读取成功，列: {list(sample_df.columns)}")
                return sample_df
            elif ext.lower() in ['.nc']:
                # NetCDF文件基础检查
                logger.info(f"NetCDF文件检查: {file_path}")
                return None  # NetCDF需要特殊处理库，这里仅做基础验证
            elif ext.lower() in ['.grib', '.grib2']:
                # GRIB文件基础检查
                logger.info(f"GRIB文件检查: {file_path}")
                return None  # GRIB需要特殊处理库，这里仅做基础验证
            else:
                logger.warning(f"未知文件格式: {ext}")
                return None
                
        except Exception as e:
            logger.error(f"样本数据读取失败: {e}")
            return None

# 全局气象数据处理服务实例
weather_data_service = WeatherDataService() 