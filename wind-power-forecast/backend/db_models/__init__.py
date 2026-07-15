# 导入Base以便在迁移脚本中使用
from .base import Base, TimeStampMixin

# 导入所有模型以确保它们注册到Base.metadata
# 核心模型
from .dataset import Dataset
from .power import ActualPower, SupershortlPower, ShortlPower, MidPower
from .training import Model, TrainingRecord, EvaluationMetrics, PredictionRecord, AutoPredictionTask, DailyMetrics
from .user import User, Role, LoginHistory
from .system_settings import SystemSetting
from .auth_extensions import UserProfileMeta, OperationAuditLog
from .alarm import AlarmRecord, AlarmRule, AlarmNotificationPolicy
from .manual_intervention import ManualInterventionVersion
from .farm_profile import FarmProfileConfig
from .report_config_meta import ReportConfigMeta
from .report_outbox import ReportOutbox
# 新增导入特征模型
from .features import TrainPreSupershort
# 物理仿真模型
from .physical_simulation import Condition, Turbine, Reading
# 上报管理模型
from .report_config import WindFarm, ReportConfig, ReportLog, ReportQualityStatistics, DataQualityMarker
# SCADA连接管理模型
from .scada_connection import ScadaConnection
from .scada_ingest_record import ScadaIngestRecord
# 运行数据模型
from .operational_data import (
    WindSpeedData, TurbinePowerData, WeatherData,
    InstalledCapacityData, AvailableCapacityData,
    TheoreticalPowerData, AvailablePowerData
)
from .weather_fetch import (
    WeatherConnection,
    WeatherTask,
    WeatherLog,
    WeatherData as WeatherDataRecord,
)
# 其他模型 - 确保导入被遗漏的模型
from .task import TaskHistory
from .training_history import TrainingHistory
from .user_roles import UserRole
from .features import TrainPreShort, TrainPreMiddle
# 自动预测模型
from .prediction_task import PredictionTask
from .prediction_run import PredictionRun
from .model_version import ModelVersion
# ECMWF 格点数据工具 (每场独立表)
from .ecmwf_grid_model import (
    ecmwf_grid_table_name,
    ensure_ecmwf_grid_table,
    ensure_ecmwf_grid_month_partitions,
    META_COLUMNS,
    WIND_DERIVE_RULES,
)

# 导出所有模型，方便其他模块直接从models导入
__all__ = [
    'Base', 'TimeStampMixin',
    # 核心模型
    'Dataset',
    'ActualPower', 'SupershortlPower', 'ShortlPower', 'MidPower',
    'Model', 'TrainingRecord', 'EvaluationMetrics', 'PredictionRecord', 'AutoPredictionTask', 'DailyMetrics',
    'User', 'Role', 'LoginHistory',
    'SystemSetting',
    'AlarmRecord', 'AlarmRule', 'AlarmNotificationPolicy',
    'ManualInterventionVersion',
    'FarmProfileConfig',
    'ReportConfigMeta',
    'ReportOutbox',
    'UserProfileMeta', 'OperationAuditLog',
    # 特征模型
    'TrainPreShort', 'TrainPreMiddle', 'TrainPreSupershort',
    'ecmwf_grid_table_name', 'ensure_ecmwf_grid_table', 'ensure_ecmwf_grid_month_partitions', 'META_COLUMNS', 'WIND_DERIVE_RULES',
    # 物理仿真模型
    'Condition', 'Turbine', 'Reading',
    # 上报管理模型
    'WindFarm', 'ReportConfig', 'ReportLog', 'ReportQualityStatistics', 'DataQualityMarker',
    'ScadaConnection', 'ScadaIngestRecord',
    # 运行数据模型
    'WindSpeedData', 'TurbinePowerData', 'WeatherData',
    'InstalledCapacityData', 'AvailableCapacityData',
    'TheoreticalPowerData', 'AvailablePowerData',
    'WeatherConnection', 'WeatherTask', 'WeatherLog', 'WeatherDataRecord',
    # 其他模型
    'TaskHistory', 'TrainingHistory', 'UserRole',
    # 自动预测模型
    'PredictionTask', 'PredictionRun', 'ModelVersion',
] 
