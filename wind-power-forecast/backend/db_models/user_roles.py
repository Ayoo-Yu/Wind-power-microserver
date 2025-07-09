from sqlalchemy import Column, Integer, String, ForeignKey, Table, JSON
# 改用SQLAlchemy核心的JSON类型
# from sqlalchemy.dialects.postgresql import JSON as PostgresJSON
from sqlalchemy.orm import relationship
from . import Base, TimeStampMixin

class UserRole(Base, TimeStampMixin):
    """用户角色表，存储各种角色及其权限配置"""
    __tablename__ = 'user_roles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    
    # 使用标准JSON替代PostgreSQL特定的JSON
    permissions = Column(JSON, nullable=True)
    
    # 关系
    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="user_roles")
    
    def __repr__(self):
        return f"<UserRole {self.name}>" 