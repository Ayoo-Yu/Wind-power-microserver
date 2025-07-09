from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base, TimeStampMixin

class Role(Base):
    """用户角色模型"""
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    permissions = Column(JSON)  # 存储权限配置的JSON
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    users = relationship("User", back_populates="role")
    user_roles = relationship("UserRole", back_populates="role")
    
    def __repr__(self):
        return f"<Role {self.name}>"

class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    full_name = Column(String(100))
    role_id = Column(Integer, ForeignKey("roles.id"))
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    first_login = Column(Boolean, default=True)  # 标记是否首次登录
    
    role = relationship("Role", back_populates="users")
    login_history = relationship("LoginHistory", back_populates="user")
    roles = relationship("UserRole", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.username}>"

class LoginHistory(Base):
    """登录历史记录表"""
    __tablename__ = "login_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    login_time = Column(DateTime, default=datetime.now)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    status = Column(String(20))  # 成功/失败
    
    user = relationship("User", back_populates="login_history")
    
    def __repr__(self):
        return f"<LoginHistory {self.user_id} at {self.login_time}>" 