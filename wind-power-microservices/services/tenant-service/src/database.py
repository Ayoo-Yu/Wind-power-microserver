"""
Database configuration and models for Tenant Management Service.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

from .config import get_settings
from .utils import get_logger


logger = get_logger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# User Model
class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


# Tenant Model
class Tenant(Base):
    """Tenant model for multi-tenancy (wind farms)."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    total_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    turbine_count: Mapped[int] = mapped_column(Integer, nullable=False)
    commissioning_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    contact_email: Mapped[Optional[str]] = mapped_column(String(100))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    address: Mapped[Optional[str]] = mapped_column(String(300))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name}, code={self.code})>"


# User Session Model (for refresh tokens)
class UserSession(Base):
    """User session model for managing refresh tokens."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    refresh_token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id})>"


# Audit Log Model
class AuditLog(Base):
    """Audit log model for tracking user actions."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36))
    details: Mapped[Optional[str]] = mapped_column(String(1000))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action})>"


# Database Engine and Session
engine = None
async_session = None


async def init_database():
    """Initialize database connection and create tables."""
    global engine, async_session

    try:
        # Create async engine
        engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=30,
            pool_recycle=3600,
            echo=True if settings.log_level == "DEBUG" else False,
            poolclass=QueuePool,
        )

        # Create session factory
        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def get_db_session() -> AsyncSession:
    """Get database session."""
    if not async_session:
        await init_database()
    return async_session()


async def close_database():
    """Close database connections."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")


# Database Health Check
async def health_check() -> bool:
    """Check database health."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            await result.scalar()
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# CRUD Operations
class CRUDBase:
    """Base CRUD operations class."""

    def __init__(self, model):
        self.model = model

    async def get(self, db: AsyncSession, id: str):
        """Get record by ID."""
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ):
        """Get multiple records with pagination."""
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj_in):
        """Create new record."""
        db_obj = self.model(**obj_in.dict())
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, db_obj, obj_in):
        """Update existing record."""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, id: str):
        """Delete record by ID."""
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj


# Import select function
from sqlalchemy import select

# CRUD instances
user_crud = CRUDBase(User)
tenant_crud = CRUDBase(Tenant)
user_session_crud = CRUDBase(UserSession)
audit_log_crud = CRUDBase(AuditLog)


# Audit logging utility
async def log_audit_event(
    db: AsyncSession,
    user_id: str,
    tenant_id: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Log audit event."""
    try:
        audit_log = AuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_log)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
        # Don't raise exception - audit logging should not break the main flow


# Database utilities for the service
__all__ = [
    "Base",
    "User",
    "Tenant",
    "UserSession",
    "AuditLog",
    "engine",
    "async_session",
    "init_database",
    "get_db_session",
    "close_database",
    "health_check",
    "CRUDBase",
    "user_crud",
    "tenant_crud",
    "user_session_crud",
    "audit_log_crud",
    "log_audit_event",
    "select",
]


if __name__ == "__main__":
    # Test database connection
    import asyncio

    async def test_connection():
        try:
            await init_database()
            print("Database connection successful!")
            await close_database()
        except Exception as e:
            print(f"Database connection failed: {e}")

    asyncio.run(test_connection())