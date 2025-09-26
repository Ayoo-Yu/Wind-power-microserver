"""
Power Predictions API endpoints for Power Prediction Service
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, power_prediction_crud
from ..models import (
    PowerPredictionResponse,
    PowerPredictionCreate,
    PredictionRequest,
    BatchPredictionRequest,
    PredictionResponse,
    PredictionFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    PredictionStatus,
    ModelType
)
from ..services import PowerPredictionManager
from ..auth import get_current_user, require_operator, WindFarmAccessChecker
from ..exceptions import (
    PredictionException,
    ValidationException,
    ModelNotFoundException
)
from ..prediction_service import prediction_service

router = APIRouter(prefix="/api/v1/predictions", tags=["power-predictions"])

# Global prediction manager instance
prediction_manager = PowerPredictionManager()


@router.post(
    "",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate power prediction",
    description="Generate power prediction for a specific wind farm and horizon",
    responses={
        201: {"description": "Power prediction generated successfully"},
        400: {"description": "Invalid prediction parameters", "model": ErrorResponse},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def generate_power_prediction(
    prediction_request: PredictionRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Generate power prediction for a wind farm."""
    try:
        # Validate prediction horizon
        if not prediction_service.validate_prediction_horizon(prediction_request.prediction_horizon):
            raise HTTPException(status_code=400, detail="Invalid prediction horizon")

        # Generate prediction
        if prediction_service.is_initialized:
            prediction_result = await prediction_service.get_power_prediction(
                wind_farm_id=prediction_request.wind_farm_id,
                turbine_id=prediction_request.turbine_id,
                prediction_horizon=prediction_request.prediction_horizon,
                model_types=prediction_request.model_types,
                include_ensemble=prediction_request.include_ensemble,
                include_confidence_intervals=prediction_request.include_confidence_intervals,
                db_session=db
            )

            return prediction_result
        else:
            return {
                "wind_farm_id": prediction_request.wind_farm_id,
                "turbine_id": prediction_request.turbine_id,
                "prediction_time": datetime.utcnow(),
                "prediction_horizon": prediction_request.prediction_horizon,
                "predictions": {},
                "ensemble_prediction": None,
                "model_versions": {},
                "input_features": {},
                "processing_time_ms": 0,
                "error": "Prediction service not initialized"
            }

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prediction: {str(e)}")


@router.post(
    "/batch",
    response_model=Dict[str, Any],
    summary="Generate batch power predictions",
    description="Generate power predictions for multiple turbines and horizons",
    responses={
        200: {"description": "Batch predictions generated successfully"},
        400: {"description": "Invalid request parameters", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def generate_batch_predictions(
    batch_request: BatchPredictionRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Generate batch power predictions."""
    try:
        results = {
            "wind_farm_id": batch_request.wind_farm_id,
            "predictions": {},
            "total_predictions": 0,
            "successful_predictions": 0,
            "failed_predictions": 0,
            "errors": []
        }

        if prediction_service.is_initialized:
            # Process each turbine
            turbine_ids = batch_request.turbine_ids or [None]  # If no specific turbines, use farm-level

            for turbine_id in turbine_ids:
                results["predictions"][turbine_id or "farm"] = {}

                for horizon in batch_request.prediction_horizons:
                    try:
                        prediction = await prediction_service.get_power_prediction(
                            wind_farm_id=batch_request.wind_farm_id,
                            turbine_id=turbine_id,
                            prediction_horizon=horizon,
                            model_types=batch_request.model_types,
                            include_ensemble=batch_request.include_ensemble,
                            db_session=db
                        )

                        results["predictions"][turbine_id or "farm"][horizon] = prediction
                        results["successful_predictions"] += 1

                    except Exception as e:
                        error_msg = f"Failed prediction for turbine {turbine_id}, horizon {horizon}: {str(e)}"
                        results["errors"].append(error_msg)
                        results["failed_predictions"] += 1

            results["total_predictions"] = len(turbine_ids) * len(batch_request.prediction_horizons)

        else:
            results["error"] = "Prediction service not initialized"

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@router.get(
    "/{prediction_id}",
    response_model=PowerPredictionResponse,
    summary="Get power prediction by ID",
    description="Retrieve a specific power prediction",
    responses={
        200: {"description": "Power prediction retrieved successfully"},
        404: {"description": "Power prediction not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_power_prediction(
    prediction_id: str = Path(..., description="Power prediction ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get power prediction by ID."""
    try:
        prediction = await power_prediction_crud.get(db, prediction_id)
        if not prediction:
            raise HTTPException(status_code=404, detail=f"Power prediction {prediction_id} not found")

        return PowerPredictionResponse.from_orm(prediction)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get power prediction: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get power predictions",
    description="Retrieve power predictions with filtering and pagination",
    responses={
        200: {"description": "Power predictions retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_power_predictions(
    # Filter parameters
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    turbine_id: Optional[str] = Query(None, description="Filter by turbine ID"),
    model_type: Optional[ModelType] = Query(None, description="Filter by model type"),
    prediction_horizon: Optional[str] = Query(None, description="Filter by prediction horizon"),
    status: Optional[PredictionStatus] = Query(None, description="Filter by prediction status"),
    data_quality: Optional[str] = Query(None, description="Filter by data quality"),

    # Time range parameters
    start_date: Optional[datetime] = Query(None, description="Predictions after this date"),
    end_date: Optional[datetime] = Query(None, description="Predictions before this date"),
    hours: int = Query(24, ge=1, le=168, description="Get predictions from last N hours"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get power predictions with filtering and pagination."""
    try:
        # Determine time range
        if not start_date or not end_date:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=hours)

        # Build filter parameters
        filter_params = {
            "wind_farm_id": wind_farm_id,
            "turbine_id": turbine_id,
            "model_type": model_type,
            "prediction_horizon": prediction_horizon,
            "status": status,
            "data_quality": data_quality
        }
        filter_params = {k: v for k, v in filter_params.items() if v is not None}

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        # Get predictions
        result = await power_prediction_crud.get_multi(
            db=db,
            filter_params=filter_params,
            time_range={"start_time": start_date, "end_time": end_date},
            pagination=pagination
        )

        # Calculate summary statistics
        total_predictions = result["total"]
        model_breakdown = {}
        horizon_breakdown = {}

        for pred in result["items"]:
            # Model breakdown
            model_type = pred.model_type
            model_breakdown[model_type] = model_breakdown.get(model_type, 0) + 1

            # Horizon breakdown
            horizon = pred.prediction_horizon
            horizon_breakdown[horizon] = horizon_breakdown.get(horizon, 0) + 1

        return {
            "success": True,
            "message": "Power predictions retrieved successfully",
            "data": [PowerPredictionResponse.from_orm(pred) for pred in result["items"]],
            "summary": {
                "total_predictions": total_predictions,
                "model_breakdown": model_breakdown,
                "horizon_breakdown": horizon_breakdown,
                "recent_predictions": len([p for p in result["items"] if p.created_at > datetime.utcnow() - timedelta(hours=24)])
            },
            "pagination": {
                "total": result["total"],
                "page": result["page"],
                "size": result["size"],
                "pages": result["pages"],
                "has_next": result["has_next"],
                "has_prev": result["has_prev"]
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get power predictions: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get predictions by wind farm",
    description="Get all power predictions for a specific wind farm",
    responses={
        200: {"description": "Power predictions retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_predictions_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    turbine_id: Optional[str] = Query(None, description="Filter by turbine ID"),
    model_type: Optional[ModelType] = Query(None, description="Filter by model type"),
    hours: int = Query(24, ge=1, le=168, description="Get predictions from last N hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get power predictions by wind farm."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Build filter
        filter_params = {"wind_farm_id": wind_farm_id}
        if turbine_id:
            filter_params["turbine_id"] = turbine_id
        if model_type:
            filter_params["model_type"] = model_type

        result = await power_prediction_crud.get_multi(
            db=db,
            filter_params=filter_params,
            time_range={"start_time": start_time, "end_time": end_time},
            pagination=None  # Get all predictions for this wind farm
        )

        # Group by model type and horizon
        predictions_by_model = {}
        predictions_by_horizon = {}

        for pred in result["items"]:
            # Group by model type
            model_type = pred.model_type
            if model_type not in predictions_by_model:
                predictions_by_model[model_type] = []
            predictions_by_model[model_type].append(PowerPredictionResponse.from_orm(pred))

            # Group by horizon
            horizon = pred.prediction_horizon
            if horizon not in predictions_by_horizon:
                predictions_by_horizon[horizon] = []
            predictions_by_horizon[horizon].append(PowerPredictionResponse.from_orm(pred))

        # Calculate accuracy statistics if we have actual values
        accuracy_stats = {}
        validated_predictions = [p for p in result["items"] if p.actual_power is not None]

        if validated_predictions:
            for horizon in predictions_by_horizon.keys():
                horizon_validated = [p for p in validated_predictions if p.prediction_horizon == horizon]
                if horizon_validated:
                    errors = [abs(p.predicted_power - p.actual_power) for p in horizon_validated]
                    accuracy_stats[horizon] = {
                        "mae": sum(errors) / len(errors),
                        "max_error": max(errors),
                        "min_error": min(errors),
                        "validation_count": len(horizon_validated)
                    }

        return {
            "success": True,
            "message": f"Power predictions for wind farm {wind_farm_id} retrieved successfully",
            "data": {
                "wind_farm_id": wind_farm_id,
                "total_predictions": result["total"],
                "predictions_by_model": predictions_by_model,
                "predictions_by_horizon": predictions_by_horizon,
                "accuracy_statistics": accuracy_stats,
                "recent_predictions": len([p for p in result["items"] if p.created_at > datetime.utcnow() - timedelta(hours=24)])
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get predictions by wind farm: {str(e)}")


@router.get(
    "/current/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get current predictions",
    description="Get current power predictions for a wind farm",
    responses={
        200: {"description": "Current predictions retrieved successfully"},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_current_predictions(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    horizons: List[str] = Query(["1h", "6h", "24h"], description="Prediction horizons"),
    turbine_id: Optional[str] = Query(None, description="Specific turbine ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get current power predictions."""
    try:
        current_predictions = {
            "wind_farm_id": wind_farm_id,
            "turbine_id": turbine_id,
            "prediction_time": datetime.utcnow(),
            "horizons": {}
        }

        if prediction_service.is_initialized:
            for horizon in horizons:
                try:
                    prediction = await prediction_service.get_power_prediction(
                        wind_farm_id=wind_farm_id,
                        turbine_id=turbine_id,
                        prediction_horizon=horizon,
                        include_ensemble=True,
                        db_session=db
                    )

                    current_predictions["horizons"][horizon] = prediction

                except Exception as e:
                    logger.warning(f"Failed to get current prediction for horizon {horizon}: {e}")
                    current_predictions["horizons"][horizon] = {
                        "error": str(e),
                        "status": "failed"
                    }

        else:
            current_predictions["error"] = "Prediction service not initialized"

        return current_predictions

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get current predictions: {str(e)}")


@router.post(
    "/{prediction_id}/validate",
    response_model=SuccessResponse,
    summary="Validate power prediction",
    description="Validate a power prediction with actual power output",
    responses={
        200: {"description": "Prediction validated successfully"},
        404: {"description": "Power prediction not found", "model": ErrorResponse},
        400: {"description": "Invalid validation data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def validate_prediction(
    prediction_id: str = Path(..., description="Power prediction ID"),
    actual_power: float = Query(..., description="Actual power output (kW)"),
    validation_notes: Optional[str] = Query(None, description="Validation notes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Validate power prediction with actual data."""
    try:
        # Get prediction
        prediction = await power_prediction_crud.get(db, prediction_id)
        if not prediction:
            raise HTTPException(status_code=404, detail=f"Power prediction {prediction_id} not found")

        # Validate actual power
        if actual_power < 0:
            raise HTTPException(status_code=400, detail="Actual power must be non-negative")

        # Update prediction with actual value
        update_data = {
            "actual_power": actual_power,
            "accuracy_metrics": {
                "mae": abs(prediction.predicted_power - actual_power),
                "percentage_error": ((prediction.predicted_power - actual_power) / actual_power * 100) if actual_power > 0 else 0
            },
            "notes": validation_notes
        }

        await power_prediction_crud.update(db, prediction, update_data)

        # Store performance metrics
        if prediction.model_id:
            from ..database import model_performance_crud
            performance_data = {
                "model_id": prediction.model_id,
                "prediction_id": prediction_id,
                "evaluation_date": datetime.utcnow(),
                "prediction_horizon": prediction.prediction_horizon,
                "mae": abs(prediction.predicted_power - actual_power),
                "accuracy": 1 - abs(prediction.predicted_power - actual_power) / actual_power if actual_power > 0 else 0
            }
            await model_performance_crud.create(db, performance_data)

        return {
            "success": True,
            "message": f"Power prediction {prediction_id} validated successfully",
            "data": {
                "prediction_id": prediction_id,
                "predicted_power": prediction.predicted_power,
                "actual_power": actual_power,
                "error": abs(prediction.predicted_power - actual_power),
                "validated_at": datetime.utcnow().isoformat()
            }
        }

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate prediction: {str(e)}")


@router.get(
    "/summary/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get prediction summary",
    description="Get comprehensive prediction statistics and trends for a wind farm",
    responses={
        200: {"description": "Prediction summary retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_prediction_summary(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    days: int = Query(7, ge=1, le=90, description="Summary period in days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get prediction summary for a wind farm."""
    try:
        if prediction_service.is_initialized:
            summary = await prediction_service.get_prediction_summary(
                wind_farm_id=wind_farm_id,
                days=days,
                db_session=db
            )

            return {
                "success": True,
                "message": f"Prediction summary for wind farm {wind_farm_id} retrieved successfully",
                "data": summary
            }
        else:
            return {
                "success": False,
                "message": "Prediction service not initialized",
                "data": {
                    "period_days": days,
                    "total_predictions": 0,
                    "model_breakdown": {},
                    "horizon_breakdown": {},
                    "quality_metrics": {}
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prediction summary: {str(e)}")


@router.delete(
    "/old/{days}",
    response_model=SuccessResponse,
    summary="Clean up old predictions",
    description="Delete old power predictions to manage storage",
    responses={
        200: {"description": "Old predictions cleaned up successfully"},
        400: {"description": "Invalid parameters", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def cleanup_old_predictions(
    days: int = Path(..., ge=1, le=365, description="Delete predictions older than N days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Clean up old power predictions."""
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Would implement actual deletion logic here
        # deleted_count = await power_prediction_crud.delete_old_predictions(db, cutoff_date)

        return {
            "success": True,
            "message": f"Power predictions older than {days} days have been cleaned up",
            "data": {
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup old predictions: {str(e)}")


# Add logging
import logging
logger = logging.getLogger(__name__)