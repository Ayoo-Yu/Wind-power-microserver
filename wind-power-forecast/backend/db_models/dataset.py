from sqlalchemy import Column, Integer, String, DateTime, Text
from .base import Base, TimeStampMixin

class Dataset(Base):
    """数据集模型，存储上传的数据文件信息"""
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    upload_time = Column(DateTime, nullable=False)
    file_id = Column(String(255), unique=True, nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    local_path = Column(String(512))
    description = Column(Text)
    data_type = Column(String(20))
    wind_farm = Column(String(100))
    
    def __repr__(self):
        return f"<Dataset {self.filename} ({self.file_id})>" 