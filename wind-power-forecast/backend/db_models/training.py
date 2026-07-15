from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base, TimeStampMixin

class Model(Base):
    """模型定义"""
    __tablename__ = "models"

    id = Column(Integer, primary_key=True)
    model_name = Column(String(255), nullable=False)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    model_path = Column(String(512))
    scaler_path = Column(String(512))
    train_time = Column(DateTime, default=datetime.now())
    accuracy = Column(Float)
    model_type = Column(String(20))
    dataset_id = Column(String(255), ForeignKey('datasets.file_id'))
    metrics_path = Column(String(512))
    is_active = Column(Boolean, default=False)
    version = Column(String(50), default="1.0")
    is_production = Column(Boolean, default=False)

    dataset = relationship("Dataset")
    evaluation_metrics = relationship("EvaluationMetrics", back_populates="model")

    def __repr__(self):
        return f"<Model {self.model_name} ({self.model_type})>"

class EvaluationMetrics(Base):
    """评估指标"""
    __tablename__ = 'evaluation_metrics'

    id = Column(Integer, primary_key=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    dataset_id = Column(String(255), ForeignKey('datasets.file_id'))
    model_id = Column(Integer, ForeignKey('models.id'))
    mae = Column(Float)
    mse = Column(Float)
    rmse = Column(Float)
    acc = Column(Float)
    k = Column(Float)
    pe = Column(Float)
    created_at = Column(DateTime, default=datetime.now())

    model = relationship("Model", back_populates="evaluation_metrics")
    dataset = relationship("Dataset")

    def __repr__(self):
        return f"<EvaluationMetrics for model_id={self.model_id}>"

class DailyMetrics(Base):
    """每日评估指标"""
    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    mae = Column(Float)
    mse = Column(Float)
    rmse = Column(Float)
    acc = Column(Float)
    k = Column(Float)
    pe = Column(Float)
    sample_count = Column(Integer)
    metric_type = Column(String(20))

    def __repr__(self):
        return f"<DailyMetrics {self.date.strftime('%Y-%m-%d')} ({self.metric_type})>"
