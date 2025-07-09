from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base, TimeStampMixin

class Model(Base):
    """模型定义"""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(255), nullable=False)
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

class TrainingRecord(Base):
    """模型训练记录"""
    __tablename__ = 'training_records'
    
    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    dataset_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.now())
    duration = Column(Float)
    log_path = Column(String(512))
    
    def __repr__(self):
        return f"<TrainingRecord {self.model_name} ({self.status})>"

class PredictionRecord(Base):
    """预测记录"""
    __tablename__ = 'prediction_records'
    
    id = Column(Integer, primary_key=True)
    model_id = Column(String(255), ForeignKey('datasets.file_id'))
    input_data_id = Column(String(255), ForeignKey('datasets.file_id'))
    scaler_id = Column(String(255), ForeignKey('datasets.file_id'))
    prediction_time = Column(DateTime, default=datetime.now())
    output_path = Column(String(512))
    prediction_type = Column(String(20))
    status = Column(String(20))
    
    model = relationship("Dataset", foreign_keys=[model_id])
    input_data = relationship("Dataset", foreign_keys=[input_data_id])
    scaler = relationship("Dataset", foreign_keys=[scaler_id])
    
    def __repr__(self):
        return f"<PredictionRecord {self.prediction_type} ({self.status})>"

class AutoPredictionTask(Base):
    """自动预测任务"""
    __tablename__ = 'auto_prediction_tasks'
    
    id = Column(Integer, primary_key=True)
    task_type = Column(String(20))
    schedule_time = Column(String(5))
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    output_dir = Column(String(512))
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<AutoPredictionTask {self.task_type}>"

class EvaluationMetrics(Base):
    """评估指标"""
    __tablename__ = 'evaluation_metrics'
    
    id = Column(Integer, primary_key=True)
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
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True)
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