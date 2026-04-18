# 导入Base以便在迁移脚本中使用
from .base import Base, TimeStampMixin

# 导入所有模型以确保它们注册到Base.metadata
# 核心模型
from .dataset import Dataset
from .power import ActualPower, SupershortlPower, ShortlPower, MidPower
from .training import Model, TrainingRecord, EvaluationMetrics, PredictionRecord, AutoPredictionTask, DailyMetrics
from .user import User, Role, LoginHistory
# 新增导入特征模型
from .features import TrainPreMiddle, TrainPreShort
# ECMWF气象数据集中存储模型
from .ecmwf_model import EcmwfMeteorologicalData
# 其他模型 - 确保导入被遗漏的模型
from .task import TaskHistory
from .training_history import TrainingHistory
from .user_roles import UserRole
# Celery 预测任务模型
from .prediction_task import PredictionTask
from .prediction_run import PredictionRun
# Model versioning for model registry
from .model_version import ModelVersion

# 导出所有模型，方便其他模块直接从models导入
__all__ = [
    'Base', 'TimeStampMixin',
    # 核心模型
    'Dataset', 
    'ActualPower', 'SupershortlPower', 'ShortlPower', 'MidPower',
    'Model', 'TrainingRecord', 'EvaluationMetrics', 'PredictionRecord', 'AutoPredictionTask', 'DailyMetrics',
    'User', 'Role', 'LoginHistory',
    # 新增模型到 __all__
    'TrainPreMiddle', 'TrainPreShort',
    'EcmwfMeteorologicalData',
    # 其他模型
    'TaskHistory', 'TrainingHistory', 'UserRole',
    # Celery 预测任务模型
    'PredictionTask', 'PredictionRun',
    # Model versioning
    'ModelVersion',
]
