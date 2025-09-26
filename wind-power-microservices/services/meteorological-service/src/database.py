"""
Database models and CRUD operations for Meteorological Data Service
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, AsyncGenerator
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer, Text, JSON, ForeignKey, Index
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy.sql import func, select, delete, update

from .models import WeatherDataSource, WeatherParameter, AlertSeverity, WeatherAlertStatus
from .utils import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class WeatherStation(Base):
    """Weather station model."""
    __tablename__ = "weather_stations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    wind_farm_id = Column(String(100), ForeignKey("wind_farms.id"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation = Column(Float)
    source = Column(String(50), nullable=False, default=WeatherDataSource.MANUAL)
    is_active = Column(Boolean, default=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    weather_data = relationship("WeatherData", back_populates="station", cascade="all, delete-orphan")
    forecasts = relationship("WeatherForecast", back_populates="station", cascade="all, delete-orphan")
    alerts = relationship("WeatherAlert", back_populates="station", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_station_wind_farm", "wind_farm_id"),
        Index("idx_station_location", "latitude", "longitude"),
        Index("idx_station_active", "is_active"),
    )


class WeatherData(Base):
    """Weather data model."""
    __tablename__ = "weather_data"

    id = Column(String, primary_key=True, index=True)
    station_id = Column(String, ForeignKey("weather_stations.id"), nullable=False, index=True)
    wind_farm_id = Column(String(100), ForeignKey("wind_farms.id"), nullable=False, index=True)
    parameter = Column(String(50), nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    quality = Column(String(20), default="good", index=True)
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    station = relationship("WeatherStation", back_populates="weather_data")

    __table_args__ = (
        Index("idx_weather_data_time_param", "timestamp", "parameter"),
        Index("idx_weather_data_station_time", "station_id", "timestamp"),
        Index("idx_weather_data_farm_time", "wind_farm_id", "timestamp"),
    )


class WeatherForecast(Base):
    """Weather forecast model."""
    __tablename__ = "weather_forecasts"

    id = Column(String, primary_key=True, index=True)
    station_id = Column(String, ForeignKey("weather_stations.id"), nullable=False, index=True)
    wind_farm_id = Column(String(100), ForeignKey("wind_farms.id"), nullable=False, index=True)
    forecast_time = Column(DateTime(timezone=True), nullable=False, index=True)
    forecast_hours = Column(Integer, nullable=False, index=True)
    parameters = Column(JSON, nullable=False)
    confidence_interval = Column(JSON)
    source = Column(String(50), nullable=False, index=True)
    model_version = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    station = relationship("WeatherStation", back_populates="forecasts")

    __table_args__ = (
        Index("idx_forecast_station_time", "station_id", "forecast_time"),
        Index("idx_forecast_farm_hours", "wind_farm_id", "forecast_hours"),
    )


class WeatherAlert(Base):
    """Weather alert model."""
    __tablename__ = "weather_alerts"

    id = Column(String, primary_key=True, index=True)
    alert_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    wind_farm_id = Column(String(100), ForeignKey("wind_farms.id"), nullable=False, index=True)
    effective_time = Column(DateTime(timezone=True), nullable=False, index=True)
    expires_time = Column(DateTime(timezone=True), nullable=False, index=True)
    areas = Column(JSON, nullable=False)
    parameters = Column(JSON)
    source = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=WeatherAlertStatus.ACTIVE, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    station = relationship("WeatherStation", back_populates="alerts")

    __table_args__ = (
        Index("idx_alert_farm_status", "wind_farm_id", "status"),
        Index("idx_alert_severity_time", "severity", "effective_time"),
        Index("idx_alert_time_range", "effective_time", "expires_time"),
    )


# CRUD Operations Base Class
class CRUDBase:
    """Base CRUD operations."""

    def __init__(self, model):
        self.model = model

    async def get(self, db: AsyncSession, id: str) -> Optional[Any]:
        """Get record by ID."""
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        filter_params: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None,
        order_by: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Get multiple records with filtering and pagination."""
        query = select(self.model)

        # Apply filters
        if filter_params:
            for key, value in filter_params.items():
                if value is not None:
                    if hasattr(self.model, key):
                        query = query.where(getattr(self.model, key) == value)

        # Get total count
        count_query = select(func.count(self.model.id))
        if filter_params:
            for key, value in filter_params.items():
                if value is not None and hasattr(self.model, key):
                    count_query = count_query.where(getattr(self.model, key) == value)

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        if pagination:
            page = pagination.get("page", 1)
            size = pagination.get("size", 20)
            query = query.offset((page - 1) * size).limit(size)

        # Apply ordering
        if order_by is not None:
            query = query.order_by(order_by)
        else:
            query = query.order_by(self.model.created_at.desc())

        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()

        # Calculate pagination info
        pages = (total + size - 1) // size if pagination else 1
        has_next = page < pages if pagination else False
        has_prev = page > 1 if pagination else False

        return {
            "items": items,
            "total": total,
            "page": page if pagination else 1,
            "size": size if pagination else total,
            "pages": pages,
            "has_next": has_next,
            "has_prev": has_prev,
        }

    async def create(self, db: AsyncSession, obj_in: Dict[str, Any]) -> Any:
        """Create new record."""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, db_obj: Any, obj_in: Dict[str, Any]) -> Any:
        """Update existing record."""
        for field, value in obj_in.items():
            if hasattr(db_obj, field) and value is not None:
                setattr(db_obj, field, value)
        db_obj.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, id: str) -> bool:
        """Delete record by ID."""
        result = await db.execute(select(self.model).where(self.model.id == id))
        db_obj = result.scalar_one_or_none()
        if db_obj:
            await db.delete(db_obj)
            await db.commit()
            return True
        return False


# Specific CRUD classes
class WeatherStationCRUD(CRUDBase):
    """Weather station CRUD operations."""

    def __init__(self):
        super().__init__(WeatherStation)

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[WeatherStation]:
        """Get weather station by code."""
        result = await db.execute(select(WeatherStation).where(WeatherStation.code == code))
        return result.scalar_one_or_none()

    async def get_by_wind_farm(self, db: AsyncSession, wind_farm_id: str) -> List[WeatherStation]:
        """Get weather stations by wind farm."""
        result = await db.execute(
            select(WeatherStation).where(WeatherStation.wind_farm_id == wind_farm_id)
        )
        return result.scalars().all()


class WeatherDataCRUD(CRUDBase):
    """Weather data CRUD operations."""

    def __init__(self):
        super().__init__(WeatherData)

    async def get_latest_by_station(
        self,
        db: AsyncSession,
        station_id: str,
        parameter: Optional[WeatherParameter] = None
    ) -> Optional[WeatherData]:
        """Get latest weather data for a station."""
        query = select(WeatherData).where(WeatherData.station_id == station_id)
        if parameter:
            query = query.where(WeatherData.parameter == parameter)
        query = query.order_by(WeatherData.timestamp.desc()).limit(1)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_time_series(
        self,
        db: AsyncSession,
        station_id: str,
        parameter: WeatherParameter,
        start_time: datetime,
        end_time: datetime
    ) -> List[WeatherData]:
        """Get time series weather data."""
        result = await db.execute(
            select(WeatherData)
            .where(
                WeatherData.station_id == station_id,
                WeatherData.parameter == parameter,
                WeatherData.timestamp >= start_time,
                WeatherData.timestamp <= end_time
            )
            .order_by(WeatherData.timestamp.asc())
        )
        return result.scalars().all()


class WeatherForecastCRUD(CRUDBase):
    """Weather forecast CRUD operations."""

    def __init__(self):
        super().__init__(WeatherForecast)

    async def get_latest_forecast(
        self,
        db: AsyncSession,
        station_id: str,
        forecast_hours: int
    ) -> Optional[WeatherForecast]:
        """Get latest forecast for a station."""
        result = await db.execute(
            select(WeatherForecast)
            .where(
                WeatherForecast.station_id == station_id,
                WeatherForecast.forecast_hours == forecast_hours
            )
            .order_by(WeatherForecast.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_forecast_series(
        self,
        db: AsyncSession,
        station_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[WeatherForecast]:
        """Get forecast series for a time range."""
        result = await db.execute(
            select(WeatherForecast)
            .where(
                WeatherForecast.station_id == station_id,
                WeatherForecast.forecast_time >= start_time,
                WeatherForecast.forecast_time <= end_time
            )
            .order_by(WeatherForecast.forecast_time.asc())
        )
        return result.scalars().all()


class WeatherAlertCRUD(CRUDBase):
    """Weather alert CRUD operations."""

    def __init__(self):
        super().__init__(WeatherAlert)

    async def get_active_alerts(
        self,
        db: AsyncSession,
        wind_farm_id: Optional[str] = None
    ) -> List[WeatherAlert]:
        """Get active weather alerts."""
        current_time = datetime.utcnow()
        query = select(WeatherAlert).where(
            WeatherAlert.status == WeatherAlertStatus.ACTIVE,
            WeatherAlert.effective_time <= current_time,
            WeatherAlert.expires_time >= current_time
        )

        if wind_farm_id:
            query = query.where(WeatherAlert.wind_farm_id == wind_farm_id)

        result = await db.execute(query.order_by(WeatherAlert.severity.desc()))
        return result.scalars().all()

    async def expire_old_alerts(self, db: AsyncSession) -> int:
        """Expire old alerts and return count."""
        current_time = datetime.utcnow()

        result = await db.execute(
            update(WeatherAlert)
            .where(
                WeatherAlert.status == WeatherAlertStatus.ACTIVE,
                WeatherAlert.expires_time < current_time
            )
            .values(status=WeatherAlertStatus.EXPIRED)
        )

        await db.commit()
        return result.rowcount


# Global CRUD instances
weather_station_crud = WeatherStationCRUD()
weather_data_crud = WeatherDataCRUD()
weather_forecast_crud = WeatherForecastCRUD()
weather_alert_crud = WeatherAlertCRUD()


# Database connection management
class DatabaseManager:
    """Database connection manager."""

    def __init__(self):
        self.engine = None
        self.async_session = None

    async def init_db(self, database_url: str):
        """Initialize database connection."""
        try:
            self.engine = create_async_engine(
                database_url,
                echo=False,
                pool_size=20,
                max_overflow=0,
                pool_pre_ping=True,
            )
            self.async_session = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def create_tables(self):
        """Create database tables."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    async def close_db(self):
        """Close database connection."""
        try:
            if self.engine:
                await self.engine.dispose()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async with self.async_session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Global database manager instance
db_manager = DatabaseManager()


# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for FastAPI dependency injection."""
    async for session in db_manager.get_session():
        yield session