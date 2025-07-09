from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from . import Base, TimeStampMixin

class TrainingHistory(Base, TimeStampMixin):
    """模型训练历史记录表，记录模型训练的详细信息"""
    __tablename__ = 'training_history'
    __table_args__ = {'comment': '模型训练历史记录表'}
    
    id = Column(Integer, primary_key=True, comment='主键ID')
    dataset_name = Column(String(255), nullable=False, comment='数据集名称')
    model_type = Column(String(50), nullable=False, comment='模型类型')
    parameters = Column(JSON, server_default='{}', nullable=False, comment='训练参数（JSON格式）')
    metrics = Column(JSON, server_default='{}', nullable=False, comment='评估指标（JSON格式）')
    prediction_file = Column(String(255), nullable=True, comment='预测结果文件路径')
    report_file = Column(String(255), nullable=True, comment='评估报告文件路径')
    file_id = Column(String(255), nullable=False, comment='关联的文件ID', index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, comment='关联的用户ID', index=True)
    status = Column(String(20), server_default="'completed'", nullable=True, comment='训练状态')
    
    # 关系
    user = relationship("User")
    
    def __repr__(self):
        return f"<TrainingHistory {self.model_type} for {self.dataset_name}>" 