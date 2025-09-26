"""
Database configuration and management for Report Service
"""

from typing import AsyncGenerator, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import select, insert, update, delete, func, and_, or_
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta

from .config import get_settings
from .models import Base, Report, ReportTemplate, ReportSchedule, Chart, ReportData, ReportDelivery
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


class ReportCRUD(BaseCRUD):
    """CRUD operations for reports."""

    def __init__(self):
        super().__init__(Report)

    async def get_by_wind_farm_and_type(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        report_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Report]:
        """Get reports by wind farm and type."""
        query = select(self.model).where(
            and_(
                self.model.wind_farm_id == wind_farm_id,
                self.model.report_type == report_type,
                self.model.created_at >= start_date,
                self.model.created_at <= end_date
            )
        )

        result = await db.execute(query.order_by(self.model.created_at.desc()))
        return result.scalars().all()

    async def get_active_reports(self, db: AsyncSession) -> List[Report]:
        """Get active (non-expired) reports."""
        current_time = datetime.utcnow()
        query = select(self.model).where(
            and_(
                self.model.status == "completed",
                or_(
                    self.model.expires_at.is_(None),
                    self.model.expires_at > current_time
                )
            )
        )

        result = await db.execute(query.order_by(self.model.created_at.desc()))
        return result.scalars().all()

    async def get_expired_reports(self, db: AsyncSession) -> List[Report]:
        """Get expired reports."""
        current_time = datetime.utcnow()
        query = select(self.model).where(
            and_(
                self.model.expires_at.isnot(None),
                self.model.expires_at <= current_time
            )
        )

        result = await db.execute(query)
        return result.scalars().all()

    async def update_status(self, db: AsyncSession, report_id: str, status: str, **kwargs) -> Optional[Report]:
        """Update report status."""
        report = await self.get(db, report_id)
        if report:
            update_data = {"status": status, **kwargs}
            return await self.update(db, report, update_data)
        return None

    async def get_reports_by_schedule(self, db: AsyncSession, schedule_id: str) -> List[Report]:
        """Get reports by schedule ID."""
        query = select(self.model).where(self.model.schedule_id == schedule_id)
        result = await db.execute(query.order_by(self.model.created_at.desc()))
        return result.scalars().all()


class ReportTemplateCRUD(BaseCRUD):
    """CRUD operations for report templates."""

    def __init__(self):
        super().__init__(ReportTemplate)

    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[ReportTemplate]:
        """Get template by name."""
        query = select(self.model).where(self.model.name == name)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_type(self, db: AsyncSession, report_type: str) -> List[ReportTemplate]:
        """Get templates by report type."""
        query = select(self.model).where(
            and_(
                self.model.report_type == report_type,
                self.model.is_active == True
            )
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_active_templates(self, db: AsyncSession) -> List[ReportTemplate]:
        """Get active templates."""
        query = select(self.model).where(self.model.is_active == True)
        result = await db.execute(query)
        return result.scalars().all()


class ReportScheduleCRUD(BaseCRUD):
    """CRUD operations for report schedules."""

    def __init__(self):
        super().__init__(ReportSchedule)

    async def get_active_schedules(self, db: AsyncSession) -> List[ReportSchedule]:
        """Get active schedules."""
        query = select(self.model).where(
            and_(
                self.model.status == "active",
                or_(
                    self.model.next_run_time.is_(None),
                    self.model.next_run_time <= datetime.utcnow()
                )
            )
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_wind_farm(self, db: AsyncSession, wind_farm_id: str) -> List[ReportSchedule]:
        """Get schedules by wind farm."""
        query = select(self.model).where(self.model.wind_farm_id == wind_farm_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def update_next_run_time(self, db: AsyncSession, schedule_id: str, next_run_time: datetime) -> Optional[ReportSchedule]:
        """Update next run time for schedule."""
        schedule = await self.get(db, schedule_id)
        if schedule:
            update_data = {
                "next_run_time": next_run_time,
                "updated_at": datetime.utcnow()
            }
            return await self.update(db, schedule, update_data)
        return None


class ChartCRUD(BaseCRUD):
    """CRUD operations for charts."""

    def __init__(self):
        super().__init__(Chart)

    async def get_by_report(self, db: AsyncSession, report_id: str) -> List[Chart]:
        """Get charts by report ID."""
        query = select(self.model).where(self.model.report_id == report_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_type(self, db: AsyncSession, chart_type: str) -> List[Chart]:
        """Get charts by type."""
        query = select(self.model).where(self.model.chart_type == chart_type)
        result = await db.execute(query)
        return result.scalars().all()


class ReportDataCRUD(BaseCRUD):
    """CRUD operations for report data cache."""

    def __init__(self):
        super().__init__(ReportData)

    async def get_by_query_hash(self, db: AsyncSession, query_hash: str) -> Optional[ReportData]:
        """Get cached data by query hash."""
        query = select(self.model).where(
            and_(
                self.model.query_hash == query_hash,
                self.model.expires_at > datetime.utcnow()
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_expired_data(self, db: AsyncSession) -> List[ReportData]:
        """Get expired cached data."""
        current_time = datetime.utcnow()
        query = select(self.model).where(self.model.expires_at <= current_time)
        result = await db.execute(query)
        return result.scalars().all()

    async def cleanup_expired_data(self, db: AsyncSession) -> int:
        """Clean up expired cached data."""
        current_time = datetime.utcnow()
        query = delete(self.model).where(self.model.expires_at <= current_time)
        result = await db.execute(query)
        await db.commit()
        return result.rowcount


class ReportDeliveryCRUD(BaseCRUD):
    """CRUD operations for report deliveries."""

    def __init__(self):
        super().__init__(ReportDelivery)

    async def get_by_report(self, db: AsyncSession, report_id: str) -> List[ReportDelivery]:
        """Get deliveries by report ID."""
        query = select(self.model).where(self.model.report_id == report_id)
        result = await db.execute(query.order_by(self.model.created_at.desc()))
        return result.scalars().all()

    async def get_pending_deliveries(self, db: AsyncSession) -> List[ReportDelivery]:
        """Get pending deliveries."""
        query = select(self.model).where(self.model.status == "pending")
        result = await db.execute(query)
        return result.scalars().all()

    async def update_status(self, db: AsyncSession, delivery_id: str, status: str, **kwargs) -> Optional[ReportDelivery]:
        """Update delivery status."""
        delivery = await self.get(db, delivery_id)
        if delivery:
            update_data = {"status": status, **kwargs}
            return await self.update(db, delivery, update_data)
        return None


# Initialize CRUD instances
report_crud = ReportCRUD()
report_template_crud = ReportTemplateCRUD()
report_schedule_crud = ReportScheduleCRUD()
chart_crud = ChartCRUD()
report_data_crud = ReportDataCRUD()
report_delivery_crud = ReportDeliveryCRUD()