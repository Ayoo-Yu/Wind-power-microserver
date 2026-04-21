# Zone2 容器专用 db_models —— 仅导入 ECMWF 模型
from .base import Base
from .ecmwf_model import EcmwfMeteorologicalData

__all__ = ['Base', 'EcmwfMeteorologicalData']
