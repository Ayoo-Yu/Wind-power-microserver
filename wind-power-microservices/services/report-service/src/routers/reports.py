"""
Report management router for Report Service
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import ReportCreate, ReportUpdate, ReportResponse, ReportStatus
from ..services import report_service
from ..exceptions import ReportNotFoundException, ReportGenerationException, ValidationException
from ..utils import get_logger, create_success_response, create_error_response

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("/", response_model=ReportResponse)
async def create_report(
    report_data: ReportCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    generated_by: Optional[str] = Query(None, description="User who generated the report")
):
    """Create a new report and start generation process."""
    try:
        logger.info(f"Creating report: {report_data.name} (type: {report_data.report_type})")

        # Create report record in database
        report = await report_service.create_report(db, report_data, generated_by)

        # Start report generation in background
        background_tasks.add_task(
            report_service.generate_report_async,
            report.id,
            db,
            generated_by
        )

        return report

    except ValidationException as e:
        logger.error(f"Validation error creating report: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating report: {e}")
        raise HTTPException(status_code=500, detail="Failed to create report")


@router.get("/", response_model=Dict[str, Any])
async def list_reports(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    status: Optional[ReportStatus] = Query(None, description="Filter by report status"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    generated_by: Optional[str] = Query(None, description="Filter by user who generated the report"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    db: AsyncSession = Depends(get_db)
):
    """Get list of reports with optional filtering."""
    try:
        logger.info(f"Listing reports with filters: type={report_type}, status={status}")

        # Build filters
        filters = {}
        if report_type:
            filters["report_type"] = report_type
        if status:
            filters["status"] = status
        if wind_farm_id:
            filters["wind_farm_id"] = wind_farm_id
        if generated_by:
            filters["generated_by"] = generated_by
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date

        # Get reports from service
        reports, total = await report_service.list_reports(
            db, skip=skip, limit=limit, filters=filters
        )

        return create_success_response(
            "Reports retrieved successfully",
            {
                "reports": reports,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        )

    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to list reports")


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str = Path(..., description="Report ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific report by ID."""
    try:
        logger.info(f"Getting report: {report_id}")

        report = await report_service.get_report(db, report_id)
        if not report:
            raise ReportNotFoundException(report_id)

        return report

    except ReportNotFoundException as e:
        logger.error(f"Report not found: {report_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get report")


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: str = Path(..., description="Report ID"),
    report_data: ReportUpdate = ...,
    db: AsyncSession = Depends(get_db)
):
    """Update a report."""
    try:
        logger.info(f"Updating report: {report_id}")

        report = await report_service.update_report(db, report_id, report_data)
        if not report:
            raise ReportNotFoundException(report_id)

        return report

    except ReportNotFoundException as e:
        logger.error(f"Report not found: {report_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error updating report: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update report")


@router.delete("/{report_id}")
async def delete_report(
    report_id: str = Path(..., description="Report ID"),
    db: AsyncSession = Depends(get_db)
):
    """Delete a report."""
    try:
        logger.info(f"Deleting report: {report_id}")

        success = await report_service.delete_report(db, report_id)
        if not success:
            raise ReportNotFoundException(report_id)

        return create_success_response(f"Report {report_id} deleted successfully")

    except ReportNotFoundException as e:
        logger.error(f"Report not found: {report_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete report")


@router.post("/{report_id}/regenerate")
async def regenerate_report(
    report_id: str = Path(..., description="Report ID"),
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    generated_by: Optional[str] = Query(None, description="User who regenerated the report")
):
    """Regenerate an existing report."""
    try:
        logger.info(f"Regenerating report: {report_id}")

        # Get existing report
        report = await report_service.get_report(db, report_id)
        if not report:
            raise ReportNotFoundException(report_id)

        # Start regeneration in background
        background_tasks.add_task(
            report_service.regenerate_report_async,
            report_id,
            db,
            generated_by
        )

        return create_success_response(f"Report {report_id} regeneration started")

    except ReportNotFoundException as e:
        logger.error(f"Report not found: {report_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error regenerating report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to regenerate report")


@router.get("/{report_id}/download")
async def download_report(
    report_id: str = Path(..., description="Report ID"),
    format: str = Query("pdf", description="Report format: pdf, html, excel"),
    db: AsyncSession = Depends(get_db)
):
    """Download a generated report file."""
    try:
        logger.info(f"Downloading report: {report_id} in format: {format}")

        # Get report file path
        file_path = await report_service.get_report_file_path(db, report_id, format)
        if not file_path:
            raise HTTPException(status_code=404, detail="Report file not found")

        from fastapi.responses import FileResponse
        return FileResponse(
            file_path,
            media_type="application/octet-stream",
            filename=f"report_{report_id}.{format}"
        )

    except Exception as e:
        logger.error(f"Error downloading report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download report")


@router.get("/{report_id}/status")
async def get_report_status(
    report_id: str = Path(..., description="Report ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get report generation status."""
    try:
        logger.info(f"Getting report status: {report_id}")

        status = await report_service.get_report_status(db, report_id)
        if not status:
            raise ReportNotFoundException(report_id)

        return create_success_response("Report status retrieved successfully", status)

    except ReportNotFoundException as e:
        logger.error(f"Report not found: {report_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting report status {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get report status")


@router.get("/types/available")
async def get_available_report_types():
    """Get available report types and their configurations."""
    try:
        logger.info("Getting available report types")

        from ..config import REPORT_TYPES

        report_types = []
        for report_type, config in REPORT_TYPES.items():
            report_types.append({
                "type": report_type,
                "name": config.get("name", report_type),
                "description": config.get("description", ""),
                "data_sources": config.get("data_sources", []),
                "default_charts": config.get("charts", []),
                "available_formats": config.get("formats", ["pdf", "html", "excel"])
            })

        return create_success_response(
            "Available report types retrieved successfully",
            {"report_types": report_types}
        )

    except Exception as e:
        logger.error(f"Error getting report types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get report types")


@router.get("/templates/list")
async def list_report_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    db: AsyncSession = Depends(get_db)
):
    """List available report templates."""
    try:
        logger.info(f"Listing report templates with filters: type={report_type}")

        from ..services import template_service

        templates, total = await template_service.list_templates(
            db, skip=skip, limit=limit, report_type=report_type
        )

        return create_success_response(
            "Report templates retrieved successfully",
            {
                "templates": templates,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        )

    except Exception as e:
        logger.error(f"Error listing report templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list report templates")


@router.post("/generate-quick")
async def generate_quick_report(
    report_type: str = Query(..., description="Report type"),
    wind_farm_id: Optional[str] = Query(None, description="Wind farm ID"),
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    format: str = Query("pdf", description="Report format"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    generated_by: Optional[str] = Query(None, description="User who generated the report")
):
    """Generate a quick report with default settings."""
    try:
        logger.info(f"Generating quick report: type={report_type}, wind_farm={wind_farm_id}")

        from datetime import datetime, timedelta

        # Build time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_range_hours)

        # Create report data
        report_data = ReportCreate(
            name=f"Quick {report_type} Report",
            report_type=report_type,
            wind_farm_id=wind_farm_id,
            time_range={
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat()
            },
            formats=[format]
        )

        # Create report
        report = await report_service.create_report(db, report_data, generated_by)

        # Start generation in background
        background_tasks.add_task(
            report_service.generate_report_async,
            report.id,
            db,
            generated_by
        )

        return create_success_response(
            f"Quick {report_type} report generation started",
            {"report_id": report.id, "status": "generating"}
        )

    except ValidationException as e:
        logger.error(f"Validation error generating quick report: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating quick report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate quick report")