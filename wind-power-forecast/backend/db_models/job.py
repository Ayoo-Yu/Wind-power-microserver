from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(255), unique=True, nullable=False, index=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    payload = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    submit_time = Column(DateTime, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    result_path = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)

    user = relationship("User")

    def __repr__(self):
        return f"<Job {self.job_type} status={self.status}>"
