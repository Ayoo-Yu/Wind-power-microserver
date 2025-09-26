"""
Database configuration and management for Power Prediction Service
"""

from typing import AsyncGenerator, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import select, insert, update, delete, func, and_, or_
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta

from .config import get_settings
from .models import Base, PowerPrediction, MLModel, TrainingJob, PowerData, ModelPerformance
from .exceptions import DatabaseConnectionException, RecordNotFoundException

logger = logging.getLogger(__name__)
settings = get_settings()

# Database engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class DatabaseManager:
    """Database manager for handling database operations."""

    def __init__(self):
        self.engine = engine
        self.session_factory = AsyncSessionLocal

    async def initialize(self):
        """Initialize database connection and create tables."""
        try:
            logger.info("Initializing database connection...")

            # Create all tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise DatabaseConnectionException(f"Database initialization failed: {str(e)}")

    async def shutdown(self):
        """Shutdown database connection."""
        try:
            logger.info("Shutting down database connection...")
            await self.engine.dispose()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        session = self.session_factory()
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with db_manager.get_session() as session:
        yield session


class BaseCRUD:
    """Base CRUD operations for database models."""

    def __init__(self, model):
        self.model = model

    async def get(self, db: AsyncSession, record_id: str) -> Optional[Any]:
        """Get record by ID."""
        result = await db.execute(select(self.model).where(self.model.id == record_id))
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        filter_params: Optional[Dict[str, Any]] = None,
        time_range: Optional[Dict[str, datetime]] = None,
        pagination: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Get multiple records with filtering and pagination."""
        query = select(self.model)

        # Apply filters
        if filter_params:
            for key, value in filter_params.items():
                if value is not None:
                    if isinstance(value, list):
                        query = query.where(getattr(self.model, key).in_(value))
                    else:
                        query = query.where(getattr(self.model, key) == value)

        # Apply time range filters
        if time_range:
            if "start_time" in time_range and time_range["start_time"]:
                query = query.where(self.model.created_at >= time_range["start_time"])
            if "end_time" in time_range and time_range["end_time"]:
                query = query.where(self.model.created_at <= time_range["end_time"])

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        if pagination:
            offset = (pagination.page - 1) * pagination.size
            query = query.offset(offset).limit(pagination.size)

        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()

        # Calculate pagination info
        pages = (total + pagination.size - 1) // pagination.size if pagination else 1
        has_next = pagination.page < pages if pagination else False
        has_prev = pagination.page > 1 if pagination else False

        return {
            "items": items,
            "total": total,
            "page": pagination.page if pagination else 1,
            "size": pagination.size if pagination else len(items),
            "pages": pages,
            "has_next": has_next,
            "has_prev": has_prev
        }

    async def create(self, db: AsyncSession, data: Dict[str, Any]) -> Any:
        """Create new record."""
        db_obj = self.model(**data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, db_obj: Any, data: Dict[str, Any]) -> Any:
        """Update existing record."""
        for key, value in data.items():
            if hasattr(db_obj, key) and value is not None:
                setattr(db_obj, key, value)

        db_obj.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, record_id: str) -> bool:
        """Delete record by ID."""
        result = await db.execute(delete(self.model).where(self.model.id == record_id))
        await db.commit()
        return result.rowcount > 0


class PowerPredictionCRUD(BaseCRUD):
    """CRUD operations for power predictions."""

    def __init__(self):
        super().__init__(PowerPrediction)

    async def get_by_wind_farm_and_time(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        start_time: datetime,
        end_time: datetime,
        turbine_id: Optional[str] = None
    ) -> List[PowerPrediction]:
        """Get predictions by wind farm and time range."""
        query = select(self.model).where(
            and_(
                self.model.wind_farm_id == wind_farm_id,
                self.model.prediction_time >= start_time,
                self.model.prediction_time <= end_time
            )
        )

        if turbine_id:
            query = query.where(self.model.turbine_id == turbine_id)

        result = await db.execute(query.order_by(self.model.prediction_time))
        return result.scalars().all()

    async def get_latest_by_wind_farm(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        turbine_id: Optional[str] = None,
        model_type: Optional[str] = None
    ) -> Optional[PowerPrediction]:
        """Get latest prediction for wind farm."""
        query = select(self.model).where(self.model.wind_farm_id == wind_farm_id)

        if turbine_id:
            query = query.where(self.model.turbine_id == turbine_id)
        if model_type:
            query = query.where(self.model.model_type == model_type)

        query = query.order_by(self.model.prediction_time.desc()).limit(1)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_accuracy_metrics(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get prediction accuracy metrics."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        query = select(
            self.model.model_type,
            self.model.prediction_horizon,
            func.avg(func.abs(self.model.predicted_power - self.model.actual_power)).label("mae"),
            func.avg(func.pow(self.model.predicted_power - self.model.actual_power, 2)).label("mse"),
            func.count(self.model.id).label("count")
        ).where(
            and_(
                self.model.wind_farm_id == wind_farm_id,
                self.model.actual_power.isnot(None),
                self.model.prediction_time >= start_time,
                self.model.prediction_time <= end_time
            )
        ).group_by(
            self.model.model_type,
            self.model.prediction_horizon
        )

        result = await db.execute(query)
        metrics = result.fetchall()

        return {
            "period_days": days,
            "metrics": [
                {
                    "model_type": m.model_type,
                    "prediction_horizon": m.prediction_horizon,
                    "mae": float(m.mae) if m.mae else 0,
                    "mse": float(m.mse) if m.mse else 0,
                    "rmse": float(m.mse ** 0.5) if m.mse else 0,
                    "data_points": int(m.count)
                }
                for m in metrics
            ]
        }


class MLModelCRUD(BaseCRUD):
    """CRUD operations for ML models."""

    def __init__(self):
        super().__init__(MLModel)

    async def get_active_models(
        self,
        db: AsyncSession,
        wind_farm_id: Optional[str] = None,
        turbine_id: Optional[str] = None,
        model_type: Optional[str] = None
    ) -> List[MLModel]:
        """Get active ML models."""
        query = select(self.model).where(self.model.is_active == True)

        if wind_farm_id:
            query = query.where(self.model.wind_farm_id == wind_farm_id)
        if turbine_id:
            query = query.where(self.model.turbine_id == turbine_id)
        if model_type:
            query = query.where(self.model.model_type == model_type)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_version(
        self,
        db: AsyncSession,
        model_name: str,
        version: str
    ) -> Optional[MLModel]:
        """Get model by name and version."""
        query = select(self.model).where(
            and_(
                self.model.model_name == model_name,
                self.model.version == version
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()


class TrainingJobCRUD(BaseCRUD):
    """CRUD operations for training jobs."""

    def __init__(self):
        super().__init__(TrainingJob)

    async def get_active_jobs(self, db: AsyncSession) -> List[TrainingJob]:
        """Get active training jobs."""
        query = select(self.model).where(
            self.model.status.in_(["pending", "processing"])
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def update_progress(
        self,
        db: AsyncSession,
        job_id: str,
        progress: int,
        status: Optional[str] = None
    ) -> Optional[TrainingJob]:
        """Update training job progress."""
        job = await self.get(db, job_id)
        if job:
            update_data = {"progress": progress}
            if status:
                update_data["status"] = status
            return await self.update(db, job, update_data)
        return None


class PowerDataCRUD(BaseCRUD):
    """CRUD operations for power data."""

    def __init__(self):
        super().__init__(PowerData)

    async def get_time_series(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        start_time: datetime,
        end_time: datetime,
        turbine_id: Optional[str] = None
    ) -> List[PowerData]:
        """Get power data time series."""
        query = select(self.model).where(
            and_(
                self.model.wind_farm_id == wind_farm_id,
                self.model.timestamp >= start_time,
                self.model.timestamp <= end_time
            )
        )

        if turbine_id:
            query = query.where(self.model.turbine_id == turbine_id)

        result = await db.execute(query.order_by(self.model.timestamp))
        return result.scalars().all()

    async def get_latest(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        turbine_id: Optional[str] = None
    ) -> Optional[PowerData]:
        """Get latest power data."""
        query = select(self.model).where(self.model.wind_farm_id == wind_farm_id)

        if turbine_id:
            query = query.where(self.model.turbine_id == turbine_id)

        query = query.order_by(self.model.timestamp.desc()).limit(1)
        result = await db.execute(query)
        return result.scalar_one_or_none()


class ModelPerformanceCRUD(BaseCRUD):
    """CRUD operations for model performance."""

    def __init__(self):
        super().__init__(ModelPerformance)

    async def get_model_performance(
        self,
        db: AsyncSession,
        model_id: str,
        days: int = 30
    ) -> List[ModelPerformance]:
        """Get model performance metrics."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        query = select(self.model).where(
            and_(
                self.model.model_id == model_id,
                self.model.evaluation_date >= start_time,
                self.model.evaluation_date <= end_time
            )
        ).order_by(self.model.evaluation_date.desc())

        result = await db.execute(query)
        return result.scalars().all()


# Initialize CRUD instances
power_prediction_crud = PowerPredictionCRUD()
ml_model_crud = MLModelCRUD()
training_job_crud = TrainingJobCRUD()
power_data_crud = PowerDataCRUD()
model_performance_crud = ModelPerformanceCRUD()