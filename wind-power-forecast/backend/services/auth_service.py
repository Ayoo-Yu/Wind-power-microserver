import jwt
import bcrypt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import User, Role, LoginHistory
import os
from typing import Optional, Dict, Any
from utils.password_utils import generate_password_hash as werkzeug_generate_hash
from utils.password_utils import verify_password as werkzeug_verify_password

# JWT密钥，实际应用中应从环境变量获取
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 24  # 小时

def get_password_hash(password: str) -> str:
    """
    生成密码哈希，使用统一的werkzeug实现
    这会让新创建的密码都使用werkzeug格式
    """
    return werkzeug_generate_hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码，兼容bcrypt和werkzeug两种格式
    """
    # 首先尝试使用werkzeug验证（新的统一方式）
    try:
        if werkzeug_verify_password(plain_password, hashed_password):
            return True
    except Exception as e:
        print(f"werkzeug验证出错: {e}")
    
    # 如果werkzeug验证失败，尝试使用bcrypt（旧格式）
    try:
        if bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8')):
            return True
    except Exception as e:
        print(f"bcrypt验证出错: {e}")
    
    return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    """解码JWT令牌"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """验证用户"""
    print(f"尝试验证用户: {username}")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        print(f"用户不存在: {username}")
        return None
    
    password_valid = verify_password(password, user.password_hash)
    print(f"密码验证结果: {password_valid}")
    
    if not password_valid:
        return None
    
    return user

def create_user(db: Session, username: str, password: str, email: str, full_name: str, role_id: int) -> User:
    """创建新用户"""
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        password_hash=hashed_password,
        email=email,
        full_name=full_name,
        role_id=role_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(db: Session, user_id: int, **kwargs) -> Optional[User]:
    """更新用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    # 如果更新密码，需要哈希处理
    if 'password' in kwargs:
        kwargs['password_hash'] = get_password_hash(kwargs.pop('password'))
    
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """通过ID获取用户"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """通过用户名获取用户"""
    return db.query(User).filter(User.username == username).first()

def get_all_users(db: Session, skip: int = 0, limit: int = 100):
    """获取所有用户"""
    return db.query(User).offset(skip).limit(limit).all()

def create_role(db: Session, name: str, description: str, permissions: Dict[str, Any]) -> Role:
    """创建新角色"""
    role = Role(name=name, description=description, permissions=permissions)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

def get_role_by_id(db: Session, role_id: int) -> Optional[Role]:
    """通过ID获取角色"""
    return db.query(Role).filter(Role.id == role_id).first()

def get_all_roles(db: Session):
    """获取所有角色"""
    return db.query(Role).all()

def log_login_attempt(db: Session, user_id: int, ip_address: str, user_agent: str, status: str) -> LoginHistory:
    """记录登录尝试"""
    login_record = LoginHistory(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status
    )
    db.add(login_record)
    db.commit()
    db.refresh(login_record)
    return login_record

def update_last_login(db: Session, user_id: int) -> None:
    """更新用户最后登录时间"""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        # 使用 UTC 时间，避免时区问题
        user.last_login = datetime.utcnow()
        if user.first_login:
            user.first_login = False
        db.commit()

def check_permission(user: User, required_permission: str) -> bool:
    """检查用户是否有特定权限"""
    if not user or not user.role or not user.role.permissions:
        return False
    
    permissions = user.role.permissions
    return required_permission in permissions.get("permissions", []) 