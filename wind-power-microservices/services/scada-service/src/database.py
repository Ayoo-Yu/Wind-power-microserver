"""
Database configuration and models for SCADA Data Service.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey, UniqueConstraint, Index, Text
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


# SCADA Connection Model
class ScadaConnection(Base):
    """SCADA connection configuration model."""

    __tablename__ = "scada_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    wind_farm_id: Mapped[str] = mapped_column(String(36), ForeignKey("wind_farms.id"), nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False, default="iec104")
    host: Mapped[str] = mapped_column(String(100), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    connection_timeout: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_reconnect_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    reconnect_delay: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="disconnected", nullable=False)
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    connection_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000))
    configuration: Mapped[Optional[str]] = mapped_column(Text)  # JSON configuration
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    wind_farm: Mapped["WindFarm"] = relationship("WindFarm", back_populates="scada_connections")
    data_points: Mapped[List["DataPoint"]] = relationship("DataPoint", back_populates="connection", cascade="all, delete-orphan")
    alarms: Mapped[List["Alarm"]] = relationship("Alarm", back_populates="connection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ScadaConnection(id={self.id}, name={self.name}, host={self.host}:{self.port})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "wind_farm_id": self.wind_farm_id,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "connection_timeout": self.connection_timeout,
            "is_active": self.is_active,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "reconnect_delay": self.reconnect_delay,
            "status": self.status,
            "last_connected_at": self.last_connected_at.isoformat() if self.last_connected_at else None,
            "connection_count": self.connection_count,
            "error_count": self.error_count,
            "error_message": self.error_message,
            "configuration": self.configuration,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Wind Farm Reference Model
class WindFarm(Base):
    """Wind farm reference model (read-only reference from wind-farm-service)."""

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
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    scada_connections: Mapped[List["ScadaConnection"]] = relationship("ScadaConnection", back_populates="wind_farm")

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
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Turbine Reference Model
class Turbine(Base):
    """Wind turbine reference model (read-only reference from wind-farm-service)."""

    __tablename__ = "turbines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    turbine_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    wind_farm_id: Mapped[str] = mapped_column(String(36), ForeignKey("wind_farms.id"), nullable=False, index=True)
    manufacturer: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    rated_power: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    wind_farm: Mapped["WindFarm"] = relationship("WindFarm")
    data_points: Mapped[List["DataPoint"]] = relationship("DataPoint", back_populates="turbine")

    # Constraints
    __table_args__ = (
        UniqueConstraint("wind_farm_id", "turbine_id", name="uq_turbine_per_farm"),
        Index("idx_turbine_wind_farm", "wind_farm_id"),
    )

    def __repr__(self):
        return f"<Turbine(id={self.id}, turbine_id={self.turbine_id}, wind_farm_id={self.wind_farm_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "turbine_id": self.turbine_id,
            "wind_farm_id": self.wind_farm_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "rated_power": self.rated_power,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Data Point Model
class DataPoint(Base):
    """SCADA data point configuration model."""

    __tablename__ = "data_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    point_name: Mapped[str] = mapped_column(String(100), nullable=False)
    point_address: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # IOA for IEC104
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("scada_connections.id"), nullable=False, index=True)
    turbine_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("turbines.id"), index=True)
    point_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    scale_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    offset: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    min_value: Mapped[Optional[float]] = mapped_column(Float)
    max_value: Mapped[Optional[float]] = mapped_column(Float)
    is_alarmpoint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alarm_threshold_high: Mapped[Optional[float]] = mapped_column(Float)
    alarm_threshold_low: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    connection: Mapped["ScadaConnection"] = relationship("ScadaConnection", back_populates="data_points")
    turbine: Mapped[Optional["Turbine"]] = relationship("Turbine", back_populates="data_points")

    # Constraints
    __table_args__ = (
        UniqueConstraint("connection_id", "point_address", name="uq_point_per_connection"),
        Index("idx_point_connection", "connection_id"),
        Index("idx_point_type", "point_type"),
        Index("idx_point_active", "is_active"),
    )

    def __repr__(self):
        return f"<DataPoint(id={self.id}, name={self.point_name}, address={self.point_address})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "point_name": self.point_name,
            "point_address": self.point_address,
            "connection_id": self.connection_id,
            "turbine_id": self.turbine_id,
            "point_type": self.point_type,
            "description": self.description,
            "unit": self.unit,
            "scale_factor": self.scale_factor,
            "offset": self.offset,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "is_alarmpoint": self.is_alarmpoint,
            "alarm_threshold_high": self.alarm_threshold_high,
            "alarm_threshold_low": self.alarm_threshold_low,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Alarm Model
class Alarm(Base):
    """SCADA alarm model."""

    __tablename__ = "alarms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    alarm_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    alarm_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    wind_farm_id: Mapped[str] = mapped_column(String(36), ForeignKey("wind_farms.id"), nullable=False, index=True)
    connection_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("scada_connections.id"), index=True)
    turbine_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("turbines.id"), index=True)
    point_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float)
    actual_value: Mapped[Optional[float]] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    wind_farm: Mapped["WindFarm"] = relationship("WindFarm")
    connection: Mapped[Optional["ScadaConnection"]] = relationship("ScadaConnection", back_populates="alarms")

    # Indexes
    __table_args__ = (
        Index("idx_alarm_wind_farm", "wind_farm_id"),
        Index("idx_alarm_connection", "connection_id"),
        Index("idx_alarm_turbine", "turbine_id"),
        Index("idx_alarm_triggered", "triggered_at"),
    )

    def __repr__(self):
        return f"<Alarm(id={self.id}, code={self.alarm_code}, severity={self.severity})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "alarm_code": self.alarm_code,
            "alarm_name": self.alarm_name,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "wind_farm_id": self.wind_farm_id,
            "connection_id": self.connection_id,
            "turbine_id": self.turbine_id,
            "point_id": self.point_id,
            "threshold_value": self.threshold_value,
            "actual_value": self.actual_value,
            "unit": self.unit,
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "cleared_at": self.cleared_at.isoformat() if self.cleared_at else None,
            "acknowledged_by": self.acknowledged_by,
            "created_at": self.created_at.isoformat(),
        }


# Connection Statistics Model
class ConnectionStatistics(Base):
    """SCADA connection statistics model."""

    __tablename__ = "connection_statistics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("scada_connections.id"), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # hour, day, week, month
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_data_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_data_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_data_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alarm_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_alarm_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_alarm_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connection_uptime: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_data_received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    connection: Mapped["ScadaConnection"] = relationship("ScadaConnection")

    # Indexes
    __table_args__ = (
        UniqueConstraint("connection_id", "period_type", "period_start", name="uq_connection_stats_period"),
        Index("idx_stats_connection", "connection_id"),
        Index("idx_stats_period", "period_start"),
    )

    def __repr__(self):
        return f"<ConnectionStatistics(id={self.id}, connection_id={self.connection_id}, period={self.period_type})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "connection_id": self.connection_id,
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_data_points": self.total_data_points,
            "valid_data_points": self.valid_data_points,
            "invalid_data_points": self.invalid_data_points,
            "alarm_count": self.alarm_count,
            "critical_alarm_count": self.critical_alarm_count,
            "warning_alarm_count": self.warning_alarm_count,
            "connection_uptime": self.connection_uptime,
            "last_data_received_at": self.last_data_received_at.isoformat() if self.last_data_received_at else None,
            "created_at": self.created_at.isoformat(),
        }


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
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100):
        """Get multiple records with pagination."""
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj_in):
        """Create new record."""
        db_obj = self.model(**obj_in.dict() if hasattr(obj_in, 'dict') else obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, db_obj, obj_in):
        """Update existing record."""
        update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in
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
scada_connection_crud = CRUDBase(ScadaConnection)
data_point_crud = CRUDBase(DataPoint)
alarm_crud = CRUDBase(Alarm)
connection_statistics_crud = CRUDBase(ConnectionStatistics)
wind_farm_crud = CRUDBase(WindFarm)
turbine_crud = CRUDBase(Turbine)


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
        # Note: AuditLog model would need to be created if audit logging is required
        logger.info(f"Audit: {user_id} {action} {resource_type} {resource_id or ''} - {details or ''}")
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")


# Database utilities for the service
__all__ = [
    "Base",
    "ScadaConnection",
    "WindFarm",
    "Turbine",
    "DataPoint",
    "Alarm",
    "ConnectionStatistics",
    "engine",
    "async_session",
    "init_database",
    "get_db_session",
    "close_database",
    "health_check",
    "CRUDBase",
    "scada_connection_crud",
    "data_point_crud",
    "alarm_crud",
    "connection_statistics_crud",
    "wind_farm_crud",
    "turbine_crud",
    "log_audit_event",
]