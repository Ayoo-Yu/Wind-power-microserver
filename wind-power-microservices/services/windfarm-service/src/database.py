"""
Database configuration and models for Wind Farm Management Service.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List

from .config import get_settings
from .utils import get_logger


logger = get_logger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Wind Farm Model
class WindFarm(Base):
    """Wind farm model for managing multiple wind farms."""

    __tablename__ = "wind_farms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    total_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    turbine_count: Mapped[int] = mapped_column(Integer, nullable=False)
    commissioning_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    contact_email: Mapped[Optional[str]] = mapped_column(String(100))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    address: Mapped[Optional[str]] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    turbines: Mapped[List["WindTurbine"]] = relationship("WindTurbine", back_populates="wind_farm", cascade="all, delete-orphan")
    user_accesses: Mapped[List["WindFarmAccess"]] = relationship("WindFarmAccess", back_populates="wind_farm", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WindFarm(id={self.id}, code={self.code}, name={self.name})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "total_capacity": self.total_capacity,
            "turbine_count": self.turbine_count,
            "commissioning_date": self.commissioning_date.isoformat() if self.commissioning_date else None,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "address": self.address,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Wind Turbine Model
class WindTurbine(Base):
    """Wind turbine model for individual turbines within a wind farm."""

    __tablename__ = "wind_turbines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    turbine_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    wind_farm_id: Mapped[str] = mapped_column(String(36), ForeignKey("wind_farms.id"), nullable=False, index=True)
    manufacturer: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    rated_power: Mapped[float] = mapped_column(Float, nullable=False)
    rotor_diameter: Mapped[float] = mapped_column(Float, nullable=False)
    hub_height: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    commissioning_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    wind_farm: Mapped["WindFarm"] = relationship("WindFarm", back_populates="turbines")

    # Constraints
    __table_args__ = (
        UniqueConstraint("wind_farm_id", "turbine_id", name="uq_turbine_per_farm"),
        Index("idx_turbine_farm_id", "wind_farm_id"),
        Index("idx_turbine_status", "status"),
    )

    def __repr__(self):
        return f"<WindTurbine(id={self.id}, turbine_id={self.turbine_id}, wind_farm_id={self.wind_farm_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "turbine_id": self.turbine_id,
            "wind_farm_id": self.wind_farm_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "rated_power": self.rated_power,
            "rotor_diameter": self.rotor_diameter,
            "hub_height": self.hub_height,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "commissioning_date": self.commissioning_date.isoformat() if self.commissioning_date else None,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# User Model (Simplified)
class User(Base):
    """User model for system authentication."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    wind_farm_accesses: Mapped[List["WindFarmAccess"]] = relationship("WindFarmAccess", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


# Wind Farm Access Model
class WindFarmAccess(Base):
    """Wind farm access permission model."""

    __tablename__ = "wind_farm_access"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    wind_farm_id: Mapped[str] = mapped_column(String(36), ForeignKey("wind_farms.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    granted_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="wind_farm_accesses")
    wind_farm: Mapped["WindFarm"] = relationship("WindFarm", back_populates="user_accesses")
    granted_by_user: Mapped["User"] = relationship("User", foreign_keys=[granted_by])

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "wind_farm_id", name="uq_user_windfarm_access"),
        Index("idx_access_user_id", "user_id"),
        Index("idx_access_windfarm_id", "wind_farm_id"),
    )

    def __repr__(self):
        return f"<WindFarmAccess(id={self.id}, user_id={self.user_id}, wind_farm_id={self.wind_farm_id})>"


# Audit Log Model
class AuditLog(Base):
    """Audit log model for tracking user actions."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
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


# CRUD Operations Base Class
class CRUDBase:
    """Base CRUD operations class."""

    def __init__(self, model):
        self.model = model

    async def get(self, db: AsyncSession, id: str):
        """Get record by ID."""
        from sqlalchemy import select
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ):
        """Get multiple records with pagination."""
        from sqlalchemy import select
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


# CRUD instances
wind_farm_crud = CRUDBase(WindFarm)
turbine_crud = CRUDBase(WindTurbine)
user_crud = CRUDBase(User)
wind_farm_access_crud = CRUDBase(WindFarmAccess)
audit_log_crud = CRUDBase(AuditLog)


# Audit logging utility
async def log_audit_event(
    db: AsyncSession,
    user_id: str,
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
    "WindFarm",
    "WindTurbine",
    "User",
    "WindFarmAccess",
    "AuditLog",
    "engine",
    "async_session",
    "init_database",
    "get_db_session",
    "close_database",
    "health_check",
    "CRUDBase",
    "wind_farm_crud",
    "turbine_crud",
    "user_crud",
    "wind_farm_access_crud",
    "audit_log_crud",
    "log_audit_event",
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