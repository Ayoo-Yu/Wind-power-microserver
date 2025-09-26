"""
Chart management router for Report Service
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import json

from ..database import get_db
from ..models import ChartResponse, ChartType
from ..services import chart_service
from ..exceptions import ChartGenerationException, ValidationException
from ..utils import get_logger, create_success_response, create_error_response

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/charts", tags=["charts"])


@router.post("/generate", response_model=ChartResponse)
async def generate_chart(
    chart_type: str = Query(..., description="Type of chart to generate"),
    title: str = Query("Chart", description="Chart title"),
    data_source: str = Query(..., description="Data source (scada, prediction, weather, etc.)"),
    wind_farm_id: Optional[str] = Query(None, description="Wind farm ID"),
    turbine_ids: Optional[str] = Query(None, description="Comma-separated turbine IDs"),
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    config: Optional[str] = Query(None, description="JSON configuration for chart"),
    backend: str = Query("matplotlib", description="Chart backend (matplotlib, plotly, seaborn)"),
    db: AsyncSession = Depends(get_db)
):
    """Generate a chart from data."""
    try:
        logger.info(f"Generating chart: type={chart_type}, title={title}, backend={backend}")

        # Parse configuration
        chart_config = {}
        if config:
            try:
                chart_config = json.loads(config)
            except json.JSONDecodeError:
                raise ValidationException("Invalid JSON configuration")

        # Parse turbine IDs
        turbine_ids_list = None
        if turbine_ids:
            turbine_ids_list = [tid.strip() for tid in turbine_ids.split(",")]

        # Generate chart
        chart_data = await chart_service.generate_chart(
            db=db,
            chart_type=chart_type,
            title=title,
            data_source=data_source,
            wind_farm_id=wind_farm_id,
            turbine_ids=turbine_ids_list,
            time_range_hours=time_range_hours,
            config=chart_config,
            backend=backend
        )

        return chart_data

    except ValidationException as e:
        logger.error(f"Validation error generating chart: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ChartGenerationException as e:
        logger.error(f"Chart generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate chart")


@router.post("/generate-custom")
async def generate_custom_chart(
    chart_type: str = Query(..., description="Type of chart to generate"),
    title: str = Query("Custom Chart", description="Chart title"),
    data_file: UploadFile = File(..., description="CSV or JSON file with chart data"),
    x_column: Optional[str] = Query(None, description="X-axis column name"),
    y_column: Optional[str] = Query(None, description="Y-axis column name"),
    config: Optional[str] = Query(None, description="JSON configuration for chart"),
    backend: str = Query("matplotlib", description="Chart backend"),
    db: AsyncSession = Depends(get_db)
):
    """Generate a chart from uploaded custom data."""
    try:
        logger.info(f"Generating custom chart: type={chart_type}, title={title}, backend={backend}")

        # Validate file type
        if data_file.content_type not in ["text/csv", "application/json"]:
            raise ValidationException("Only CSV and JSON files are supported")

        # Read and parse data
        content = await data_file.read()

        if data_file.content_type == "text/csv":
            import io
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        else:  # JSON
            data = json.loads(content.decode('utf-8'))
            df = pd.DataFrame(data)

        # Parse configuration
        chart_config = {}
        if config:
            try:
                chart_config = json.loads(config)
            except json.JSONDecodeError:
                raise ValidationException("Invalid JSON configuration")

        # Generate chart
        chart_data = await chart_service.generate_chart_from_dataframe(
            df=df,
            chart_type=chart_type,
            title=title,
            x_column=x_column,
            y_column=y_column,
            config=chart_config,
            backend=backend
        )

        return create_success_response("Custom chart generated successfully", chart_data)

    except ValidationException as e:
        logger.error(f"Validation error generating custom chart: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ChartGenerationException as e:
        logger.error(f"Custom chart generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating custom chart: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate custom chart")


@router.post("/generate-multiple")
async def generate_multiple_charts(
    charts_config: str = Query(..., description="JSON array of chart configurations"),
    db: AsyncSession = Depends(get_db)
):
    """Generate multiple charts in one request."""
    try:
        logger.info("Generating multiple charts")

        # Parse configurations
        try:
            config_list = json.loads(charts_config)
            if not isinstance(config_list, list):
                raise ValidationException("Charts configuration must be a JSON array")
        except json.JSONDecodeError:
            raise ValidationException("Invalid JSON configuration")

        # Generate charts
        charts = await chart_service.generate_multiple_charts(db, config_list)

        return create_success_response(
            f"Generated {len(charts)} charts successfully",
            {"charts": charts, "count": len(charts)}
        )

    except ValidationException as e:
        logger.error(f"Validation error generating multiple charts: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ChartGenerationException as e:
        logger.error(f"Multiple charts generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating multiple charts: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate multiple charts")


@router.get("/types/available")
async def get_available_chart_types():
    """Get available chart types and their configurations."""
    try:
        logger.info("Getting available chart types")

        chart_types = []
        for chart_type in ChartType:
            chart_types.append({
                "type": chart_type.value,
                "name": chart_type.name.replace("_", " ").title(),
                "description": chart_service.get_chart_type_description(chart_type.value)
            })

        return create_success_response(
            "Available chart types retrieved successfully",
            {"chart_types": chart_types}
        )

    except Exception as e:
        logger.error(f"Error getting chart types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chart types")


@router.get("/backends/available")
async def get_available_backends():
    """Get available chart generation backends."""
    try:
        logger.info("Getting available chart backends")

        backends = await chart_service.get_available_backends()

        return create_success_response(
            "Available chart backends retrieved successfully",
            {"backends": backends}
        )

    except Exception as e:
        logger.error(f"Error getting chart backends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chart backends")


@router.get("/templates/list")
async def list_chart_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    chart_type: Optional[str] = Query(None, description="Filter by chart type"),
    db: AsyncSession = Depends(get_db)
):
    """List available chart templates."""
    try:
        logger.info(f"Listing chart templates with filters: type={chart_type}")

        templates, total = await chart_service.list_templates(
            db, skip=skip, limit=limit, chart_type=chart_type
        )

        return create_success_response(
            "Chart templates retrieved successfully",
            {
                "templates": templates,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        )

    except Exception as e:
        logger.error(f"Error listing chart templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list chart templates")


@router.get("/sample-data/{data_source}")
async def get_sample_data(
    data_source: str = Path(..., description="Data source (scada, prediction, weather, etc.)"),
    wind_farm_id: Optional[str] = Query(None, description="Wind farm ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of sample records"),
    db: AsyncSession = Depends(get_db)
):
    """Get sample data for chart testing."""
    try:
        logger.info(f"Getting sample data: source={data_source}, wind_farm={wind_farm_id}")

        sample_data = await chart_service.get_sample_data(
            db=db,
            data_source=data_source,
            wind_farm_id=wind_farm_id,
            limit=limit
        )

        return create_success_response(
            "Sample data retrieved successfully",
            {
                "data": sample_data,
                "count": len(sample_data),
                "data_source": data_source
            }
        )

    except Exception as e:
        logger.error(f"Error getting sample data: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sample data")


@router.get("/previews/{chart_id}")
async def get_chart_preview(
    chart_id: str = Path(..., description="Chart ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get chart preview data."""
    try:
        logger.info(f"Getting chart preview: {chart_id}")

        preview_data = await chart_service.get_chart_preview(db, chart_id)
        if not preview_data:
            raise HTTPException(status_code=404, detail="Chart not found")

        return create_success_response("Chart preview retrieved successfully", preview_data)

    except Exception as e:
        logger.error(f"Error getting chart preview {chart_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chart preview")


@router.delete("/{chart_id}")
async def delete_chart(
    chart_id: str = Path(..., description="Chart ID"),
    db: AsyncSession = Depends(get_db)
):
    """Delete a generated chart."""
    try:
        logger.info(f"Deleting chart: {chart_id}")

        success = await chart_service.delete_chart(db, chart_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chart not found")

        return create_success_response(f"Chart {chart_id} deleted successfully")

    except Exception as e:
        logger.error(f"Error deleting chart {chart_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chart")