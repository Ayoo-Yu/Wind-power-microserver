from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    department = db.Column(db.String(50))
    position = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(50))
    updated_by = db.Column(db.String(50))

    # Relationships
    roles = db.relationship('Role', secondary='user_roles', back_populates='users')
    sessions = db.relationship('Session', back_populates='user', cascade='all, delete-orphan')
    farm_access = db.relationship('FarmAccess', back_populates='user', cascade='all, delete-orphan')
    two_factor_auth = db.relationship('TwoFactorAuth', back_populates='user', uselist=False, cascade='all, delete-orphan')
    password_resets = db.relationship('PasswordReset', back_populates='user', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'department': self.department,
            'position': self.position,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = db.relationship('User', secondary='user_roles', back_populates='roles')
    permissions = db.relationship('Permission', secondary='role_permissions', back_populates='roles')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Permission(db.Model):
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    resource = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    roles = db.relationship('Role', secondary='role_permissions', back_populates='permissions')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'resource': self.resource,
            'action': self.action,
            'created_at': self.created_at.isoformat()
        }

# Association tables
user_roles = db.Table('user_roles',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow),
    db.Column('assigned_by', db.String(50)),
    db.Column('expires_at', db.DateTime),
    db.UniqueConstraint('user_id', 'role_id')
)

role_permissions = db.Table('role_permissions',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False),
    db.Column('granted_at', db.DateTime, default=datetime.utcnow),
    db.Column('granted_by', db.String(50)),
    db.UniqueConstraint('role_id', 'permission_id')
)

class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    refresh_token = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    user = db.relationship('User', back_populates='sessions')

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'ip_address': self.ip_address,
            'is_active': self.is_active
        }

class FarmAccess(db.Model):
    __tablename__ = 'farm_access'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    farm_code = db.Column(db.String(50), nullable=False)
    access_level = db.Column(db.String(20), default='read')  # read, write, admin
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    granted_by = db.Column(db.String(50))
    expires_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', back_populates='farm_access')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'farm_code': self.farm_code,
            'access_level': self.access_level,
            'granted_at': self.granted_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }

class TwoFactorAuth(db.Model):
    __tablename__ = 'two_factor_auth'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    secret_key = db.Column(db.String(255), nullable=False)
    backup_codes = db.Column(db.ARRAY(db.String))
    is_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='two_factor_auth')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'is_enabled': self.is_enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class PasswordReset(db.Model):
    __tablename__ = 'password_resets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='password_resets')

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def is_used(self):
        return self.used_at is not None

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    action = db.Column(db.String(100), nullable=False)
    resource = db.Column(db.String(100), nullable=False)
    resource_id = db.Column(db.String(100))
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='success')

    # Relationships
    user = db.relationship('User', back_populates='audit_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'resource': self.resource,
            'resource_id': self.resource_id,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status
        }