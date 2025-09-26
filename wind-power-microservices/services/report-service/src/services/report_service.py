"""
Report service for managing report operations
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from ..database import report_crud, report_data_crud
from ..models import ReportCreate, ReportUpdate, ReportResponse, ReportStatus, ReportFormat
from ..report_generator import report_generator
from ..exceptions import ReportNotFoundException, ReportGenerationException
from ..utils import get_logger, create_error_response

logger = get_logger(__name__)


class ReportService:
    """Service for managing report operations."""

    def __init__(self):
        self.is_initialized = False

    async def initialize(self):
        """Initialize the report service."""
        try:
            logger.info("Initializing Report Service...")
            await report_generator.initialize()
            self.is_initialized = True
            logger.info("Report Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Report Service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the report service."""
        try:
            logger.info("Shutting down Report Service...")
            await report_generator.shutdown()
            self.is_initialized = False
            logger.info("Report Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during Report Service shutdown: {e}")

    async def create_report(
        self,
        db: AsyncSession,
        report_data: ReportCreate,
        generated_by: Optional[str] = None
    ) -> ReportResponse:
        """Create a new report record."""
        try:
            logger.info(f"Creating report: {report_data.name}")

            # Create report record
            report_dict = report_data.dict()
            report_dict["id"] = f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hash(report_data.name) % 10000:04d}"
            report_dict["status"] = ReportStatus.PENDING
            report_dict["generated_by"] = generated_by
            report_dict["created_at"] = datetime.utcnow()
            report_dict["updated_at"] = datetime.utcnow()

            report = await report_crud.create(db, report_dict)

            return ReportResponse.from_orm(report)

        except Exception as e:
            logger.error(f"Error creating report: {e}")
            raise ReportGenerationException(f"Failed to create report: {str(e)}")

    async def list_reports(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ReportResponse], int]:
        """List reports with filtering."""
        try:
            logger.info(f"Listing reports: skip={skip}, limit={limit}, filters={filters}")

            # Build query conditions
            conditions = []
            if filters:
                if "report_type" in filters:
                    conditions.append(report_crud.model.report_type == filters["report_type"])
                if "status" in filters:
                    conditions.append(report_crud.model.status == filters["status"])
                if "wind_farm_id" in filters:
                    conditions.append(report_crud.model.wind_farm_id == filters["wind_farm_id"])
                if "generated_by" in filters:
                    conditions.append(report_crud.model.generated_by == filters["generated_by"])
                if "start_date" in filters:
                    conditions.append(report_crud.model.created_at >= filters["start_date"])
                if "end_date" in filters:
                    conditions.append(report_crud.model.created_at <= filters["end_date"])

            # Execute query
            query = select(report_crud.model)
            if conditions:
                query = query.where(and_(*conditions))

            # Get total count
            count_query = select(func.count(report_crud.model.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))

            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Get paginated results
            query = query.offset(skip).limit(limit).order_by(report_crud.model.created_at.desc())
            result = await db.execute(query)
            reports = result.scalars().all()

            # Convert to response models
            report_responses = [ReportResponse.from_orm(report) for report in reports]

            return report_responses, total

        except Exception as e:
            logger.error(f"Error listing reports: {e}")
            raise ReportGenerationException(f"Failed to list reports: {str(e)}")

    async def get_report(
        self,
        db: AsyncSession,
        report_id: str
    ) -> Optional[ReportResponse]:
        """Get a specific report by ID."""
        try:
            logger.info(f"Getting report: {report_id}")

            report = await report_crud.get(db, report_id)
            if not report:
                return None

            return ReportResponse.from_orm(report)

        except Exception as e:
            logger.error(f"Error getting report {report_id}: {e}")
            raise ReportGenerationException(f"Failed to get report: {str(e)}")

    async def update_report(
        self,
        db: AsyncSession,
        report_id: str,
        report_data: ReportUpdate
    ) -> Optional[ReportResponse]:
        """Update a report."""
        try:
            logger.info(f"Updating report: {report_id}")

            # Get existing report
            existing_report = await report_crud.get(db, report_id)
            if not existing_report:
                return None

            # Update fields
            update_data = report_data.dict(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()

            updated_report = await report_crud.update(db, report_id, update_data)

            return ReportResponse.from_orm(updated_report)

        except Exception as e:
            logger.error(f"Error updating report {report_id}: {e}")
            raise ReportGenerationException(f"Failed to update report: {str(e)}")

    async def delete_report(
        self,
        db: AsyncSession,
        report_id: str
    ) -> bool:
        """Delete a report."""
        try:
            logger.info(f"Deleting report: {report_id}")

            report = await report_crud.get(db, report_id)
            if not report:
                return False

            # Delete report files
            if report.file_paths:
                for file_path in report.file_paths.values():
                    try:
                        import os
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as file_error:
                        logger.warning(f"Failed to delete report file {file_path}: {file_error}")

            # Delete database record
            success = await report_crud.delete(db, report_id)
            return success

        except Exception as e:
            logger.error(f"Error deleting report {report_id}: {e}")
            raise ReportGenerationException(f"Failed to delete report: {str(e)}")

    async def generate_report_async(
        self,
        report_id: str,
        db: AsyncSession,
        generated_by: Optional[str] = None
    ):
        """Generate report asynchronously."""
        try:
            logger.info(f"Starting async report generation: {report_id}")

            # Get report record
            report = await report_crud.get(db, report_id)
            if not report:
                logger.error(f"Report not found for generation: {report_id}")
                return

            # Update status to generating
            await report_crud.update(db, report_id, {
                "status": ReportStatus.GENERATING,
                "updated_at": datetime.utcnow()
            })

            # Prepare report data
            from ..models import ReportCreate
            report_data = ReportCreate(
                name=report.name,
                report_type=report.report_type,
                wind_farm_id=report.wind_farm_id,
                turbine_ids=report.turbine_ids,
                time_range=report.time_range,
                parameters=report.parameters,
                filters=report.filters,
                data_sources=report.data_sources,
                charts_config=report.charts_config,
                formats=report.formats,
                template_id=report.template_id
            )

            # Generate report
            generation_result = await report_generator.generate_report(
                report_data=report_data,
                db_session=db,
                generated_by=generated_by or report.generated_by
            )

            # Update report with results
            update_data = {
                "status": generation_result["status"],
                "updated_at": datetime.utcnow(),
                "generation_start_time": generation_result.get("generation_start_time"),
                "generation_end_time": generation_result.get("generation_end_time"),
                "generation_duration_seconds": generation_result.get("generation_duration_seconds"),
                "data_quality_score": generation_result.get("data_quality_score"),
                "total_file_size": generation_result.get("total_file_size"),
                "charts_generated": generation_result.get("charts_generated"),
                "file_paths": generation_result.get("generated_files", {})
            }

            if generation_result["status"] == ReportStatus.FAILED:
                update_data["error_message"] = generation_result.get("error_message")

            await report_crud.update(db, report_id, update_data)

            logger.info(f"Report generation completed: {report_id} - {generation_result['status']}")

        except Exception as e:
            logger.error(f"Error generating report {report_id}: {e}")
            # Update report status to failed
            try:
                await report_crud.update(db, report_id, {
                    "status": ReportStatus.FAILED,
                    "error_message": str(e),
                    "updated_at": datetime.utcnow()
                })
            except Exception as update_error:
                logger.error(f"Failed to update failed report status: {update_error}")

    async def regenerate_report_async(
        self,
        report_id: str,
        db: AsyncSession,
        generated_by: Optional[str] = None
    ):
        """Regenerate an existing report."""
        try:
            logger.info(f"Starting async report regeneration: {report_id}")

            # Get existing report
            report = await report_crud.get(db, report_id)
            if not report:
                logger.error(f"Report not found for regeneration: {report_id}")
                return

            # Simply call the generation method
            await self.generate_report_async(report_id, db, generated_by)

        except Exception as e:
            logger.error(f"Error regenerating report {report_id}: {e}")

    async def get_report_file_path(
        self,
        db: AsyncSession,
        report_id: str,
        format: str
    ) -> Optional[str]:
        """Get the file path for a generated report."""
        try:
            logger.info(f"Getting report file path: {report_id}, format: {format}")

            report = await report_crud.get(db, report_id)
            if not report:
                return None

            if not report.file_paths or format not in report.file_paths:
                return None

            file_path = report.file_paths[format]
            import os
            if not os.path.exists(file_path):
                return None

            return file_path

        except Exception as e:
            logger.error(f"Error getting report file path {report_id}: {e}")
            return None

    async def get_report_status(
        self,
        db: AsyncSession,
        report_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get report generation status."""
        try:
            logger.info(f"Getting report status: {report_id}")

            report = await report_crud.get(db, report_id)
            if not report:
                return None

            return {
                "report_id": report.id,
                "status": report.status,
                "name": report.name,
                "report_type": report.report_type,
                "created_at": report.created_at,
                "updated_at": report.updated_at,
                "generation_start_time": report.generation_start_time,
                "generation_end_time": report.generation_end_time,
                "generation_duration_seconds": report.generation_duration_seconds,
                "data_quality_score": report.data_quality_score,
                "total_file_size": report.total_file_size,
                "charts_generated": report.charts_generated,
                "error_message": report.error_message,
                "generated_files": list(report.file_paths.keys()) if report.file_paths else []
            }

        except Exception as e:
            logger.error(f"Error getting report status {report_id}: {e}")
            return None


# Global report service instance
report_service = ReportService()