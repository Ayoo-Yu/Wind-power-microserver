"""
Main application for Report Service
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import init_db, get_db
from .models import ReportResponse, ChartResponse, TemplateResponse
from .routers import (
    reports_router,
    charts_router,
    templates_router,
    monitoring_router,
    health_router
)
from .services import report_service, chart_service, template_service, monitoring_service, health_service
from .exceptions import (
    ReportServiceException,
    ReportNotFoundException,
    TemplateNotFoundException,
    ReportGenerationException,
    DataCollectionException,
    ChartGenerationException,
    TemplateRenderingException,
    ValidationException,
    DatabaseConnectionException,
    ExternalAPIException,
    InsufficientDataException,
    DataQualityException
)
from .utils import get_logger, create_error_response

# Initialize settings
settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Report Service...")
    try:
        # Initialize database
        await init_db()

        # Initialize services
        await report_service.initialize()
        await chart_service.initialize()

        logger.info("Report Service started successfully")
    except Exception as e:
        logger.error(f"Failed to start Report Service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Report Service...")
    try:
        # Shutdown services
        await report_service.shutdown()
        await chart_service.shutdown()

        logger.info("Report Service shutdown completed")
    except Exception as e:
        logger.error(f"Error during Report Service shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="Wind Farm Report Service",
    description="Microservice for generating reports and visualizations for wind farm operations",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers
@app.exception_handler(ReportNotFoundException)
async def report_not_found_handler(request: Request, exc: ReportNotFoundException):
    """Handle report not found exceptions."""
    return JSONResponse(
        status_code=404,
        content=create_error_response(str(exc), "REPORT_NOT_FOUND", exc.details)
    )


@app.exception_handler(TemplateNotFoundException)
async def template_not_found_handler(request: Request, exc: TemplateNotFoundException):
    """Handle template not found exceptions."""
    return JSONResponse(
        status_code=404,
        content=create_error_response(str(exc), "TEMPLATE_NOT_FOUND", exc.details)
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    """Handle validation exceptions."""
    return JSONResponse(
        status_code=400,
        content=create_error_response(str(exc), "VALIDATION_ERROR", exc.details)
    )


@app.exception_handler(ReportGenerationException)
async def report_generation_exception_handler(request: Request, exc: ReportGenerationException):
    """Handle report generation exceptions."""
    return JSONResponse(
        status_code=500,
        content=create_error_response(str(exc), "REPORT_GENERATION_ERROR", exc.details)
    )


@app.exception_handler(DataCollectionException)
async def data_collection_exception_handler(request: Request, exc: DataCollectionException):
    """Handle data collection exceptions."""
    return JSONResponse(
        status_code=500,
        content=create_error_response(str(exc), "DATA_COLLECTION_ERROR", exc.details)
    )


@app.exception_handler(ChartGenerationException)
async def chart_generation_exception_handler(request: Request, exc: ChartGenerationException):
    """Handle chart generation exceptions."""
    return JSONResponse(
        status_code=500,
        content=create_error_response(str(exc), "CHART_GENERATION_ERROR", exc.details)
    )


@app.exception_handler(TemplateRenderingException)
async def template_rendering_exception_handler(request: Request, exc: TemplateRenderingException):
    """Handle template rendering exceptions."""
    return JSONResponse(
        status_code=500,
        content=create_error_response(str(exc), "TEMPLATE_RENDERING_ERROR", exc.details)
    )


@app.exception_handler(DatabaseConnectionException)
async def database_connection_exception_handler(request: Request, exc: DatabaseConnectionException):
    """Handle database connection exceptions."""
    return JSONResponse(
        status_code=503,
        content=create_error_response(str(exc), "DATABASE_CONNECTION_ERROR", exc.details)
    )


@app.exception_handler(ExternalAPIException)
async def external_api_exception_handler(request: Request, exc: ExternalAPIException):
    """Handle external API exceptions."""
    return JSONResponse(
        status_code=503,
        content=create_error_response(str(exc), "EXTERNAL_API_ERROR", exc.details)
    )


@app.exception_handler(InsufficientDataException)
async def insufficient_data_exception_handler(request: Request, exc: InsufficientDataException):
    """Handle insufficient data exceptions."""
    return JSONResponse(
        status_code=422,
        content=create_error_response(str(exc), "INSUFFICIENT_DATA", exc.details)
    )


@app.exception_handler(DataQualityException)
async def data_quality_exception_handler(request: Request, exc: DataQualityException):
    """Handle data quality exceptions."""
    return JSONResponse(
        status_code=422,
        content=create_error_response(str(exc), "DATA_QUALITY_ERROR", exc.details)
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            exc.detail if isinstance(exc.detail, str) else "HTTP error occurred",
            f"HTTP_{exc.status_code}",
            {"detail": exc.detail} if not isinstance(exc.detail, str) else {}
        )
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=create_error_response(
            "An internal server error occurred",
            "INTERNAL_SERVER_ERROR",
            {"error_type": type(exc).__name__, "error_message": str(exc)}
        )
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Wind Farm Report Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "docs": "/api/docs",
            "health": "/health",
            "reports": "/api/v1/reports",
            "charts": "/api/v1/charts",
            "templates": "/api/v1/templates",
            "monitoring": "/api/v1/monitoring"
        }
    }


# API information endpoint
@app.get("/api/info")
async def api_info():
    """Get API information."""
    return {
        "service": "Wind Farm Report Service",
        "version": "1.0.0",
        "description": "Microservice for generating reports and visualizations for wind farm operations",
        "features": [
            "Multi-format report generation (PDF, HTML, Excel)",
            "Interactive chart generation with multiple backends",
            "Template-based report system",
            "Real-time monitoring and analytics",
            "Data quality assessment",
            "Scheduled report automation"
        ],
        "supported_formats": ["pdf", "html", "excel"],
        "chart_backends": ["matplotlib", "plotly", "seaborn"],
        "report_types": [
            "daily_power_generation",
            "weekly_performance",
            "operational_dashboard",
            "prediction_accuracy",
            "maintenance_summary"
        ],
        "endpoints": {
            "reports": "/api/v1/reports",
            "charts": "/api/v1/charts",
            "templates": "/api/v1/templates",
            "monitoring": "/api/v1/monitoring",
            "health": "/health"
        }
    }


# Include routers
app.include_router(reports_router)
app.include_router(charts_router)
app.include_router(templates_router)
app.include_router(monitoring_router)
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )