"""
SCADA Connection API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, scada_connection_crud
from ..models import (
    ScadaConnectionCreate,
    ScadaConnectionUpdate,
    ScadaConnectionResponse,
    ScadaConnectionFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    ConnectionStatus
)
from ..services import ConnectionManager
from ..auth import get_current_user
from ..exceptions import (
    ScadaConnectionNotFoundException,
    DuplicateScadaConnectionException,
    InvalidScadaDataException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/connections", tags=["scada-connections"])

# Global connection manager instance
connection_manager = ConnectionManager()


@router.post(
    "",
    response_model=ScadaConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SCADA connection",
    description="Create a new SCADA connection with protocol configuration",
    responses={
        201: {"description": "SCADA connection created successfully"},
        400: {"description": "Invalid connection data", "model": ErrorResponse},
        409: {"description": "SCADA connection already exists", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_connection(
    connection_data: ScadaConnectionCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Create a new SCADA connection."""
    try:
        # Initialize connection manager if not already done
        if not connection_manager.influxdb_manager.client:
            await connection_manager.initialize()

        connection = await connection_manager.create_connection(
            db=db,
            connection_data=connection_data.dict(),
            current_user_id=current_user.id
        )
        return connection

    except (ValidationException, InvalidScadaDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateScadaConnectionException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create SCADA connection: {str(e)}")


@router.get(
    "/{connection_id}",
    response_model=ScadaConnectionResponse,
    summary="Get SCADA connection by ID",
    description="Retrieve detailed information about a specific SCADA connection",
    responses={
        200: {"description": "SCADA connection retrieved successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA connection by ID."""
    try:
        connection = await connection_manager.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail=f"SCADA connection {connection_id} not found")
        return connection

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA connection: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get list of SCADA connections",
    description="Retrieve paginated list of SCADA connections with filtering and search capabilities",
    responses={
        200: {"description": "SCADA connections retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_connections(
    # Filter parameters
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    protocol: Optional[str] = Query(None, description="Filter by protocol"),
    status: Optional[str] = Query(None, description="Filter by connection status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    host: Optional[str] = Query(None, description="Filter by host"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get list of SCADA connections with filtering and pagination."""
    try:
        # Build filter parameters
        filter_params = None
        if any([wind_farm_id, protocol, status, is_active is not None, host]):
            filter_params = ScadaConnectionFilter(
                wind_farm_id=wind_farm_id,
                protocol=protocol,
                status=status,
                is_active=is_active,
                host=host
            )

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        result = await connection_manager.get_connections(
            db=db,
            filter_params=filter_params,
            pagination=pagination
        )

        return {
            "success": True,
            "message": "SCADA connections retrieved successfully",
            "data": result["items"],
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
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA connections: {str(e)}")


@router.put(
    "/{connection_id}",
    response_model=ScadaConnectionResponse,
    summary="Update SCADA connection",
    description="Update SCADA connection configuration",
    responses={
        200: {"description": "SCADA connection updated successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        400: {"description": "Invalid connection data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def update_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    connection_data: ScadaConnectionUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Update SCADA connection."""
    try:
        connection = await connection_manager.update_connection(
            db=db,
            connection_id=connection_id,
            update_data=connection_data.dict(exclude_unset=True),
            current_user_id=current_user.id
        )
        return connection

    except ScadaConnectionNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationException, InvalidScadaDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update SCADA connection: {str(e)}")


@router.delete(
    "/{connection_id}",
    response_model=SuccessResponse,
    summary="Delete SCADA connection",
    description="Delete a SCADA connection permanently",
    responses={
        200: {"description": "SCADA connection deleted successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def delete_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Delete SCADA connection."""
    try:
        success = await connection_manager.delete_connection(
            db=db,
            connection_id=connection_id,
            current_user_id=current_user.id
        )

        return {
            "success": success,
            "message": f"SCADA connection {connection_id} deleted successfully"
        }

    except ScadaConnectionNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete SCADA connection: {str(e)}")


@router.post(
    "/{connection_id}/start",
    response_model=SuccessResponse,
    summary="Start SCADA connection",
    description="Start a SCADA connection and begin data collection",
    responses={
        200: {"description": "SCADA connection started successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def start_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    current_user = Depends(get_current_user)
):
    """Start SCADA connection."""
    try:
        # Initialize connection manager if not already done
        if not connection_manager.influxdb_manager.client:
            await connection_manager.initialize()

        success = await connection_manager.start_connection(connection_id)

        return {
            "success": success,
            "message": f"SCADA connection {connection_id} {'started successfully' if success else 'failed to start'}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start SCADA connection: {str(e)}")


@router.post(
    "/{connection_id}/stop",
    response_model=SuccessResponse,
    summary="Stop SCADA connection",
    description="Stop a SCADA connection and data collection",
    responses={
        200: {"description": "SCADA connection stopped successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def stop_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    current_user = Depends(get_current_user)
):
    """Stop SCADA connection."""
    try:
        success = await connection_manager.stop_connection(connection_id)

        return {
            "success": success,
            "message": f"SCADA connection {connection_id} {'stopped successfully' if success else 'failed to stop'}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop SCADA connection: {str(e)}")


@router.post(
    "/start-all",
    response_model=SuccessResponse,
    summary="Start all SCADA connections",
    description="Start all configured SCADA connections",
    responses={
        200: {"description": "All SCADA connections started successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def start_all_connections(
    current_user = Depends(get_current_user)
):
    """Start all SCADA connections."""
    try:
        # Initialize connection manager if not already done
        if not connection_manager.influxdb_manager.client:
            await connection_manager.initialize()

        await connection_manager.start_all_connections()

        return {
            "success": True,
            "message": "All SCADA connections started successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start all SCADA connections: {str(e)}")


@router.post(
    "/stop-all",
    response_model=SuccessResponse,
    summary="Stop all SCADA connections",
    description="Stop all SCADA connections",
    responses={
        200: {"description": "All SCADA connections stopped successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def stop_all_connections(
    current_user = Depends(get_current_user)
):
    """Stop all SCADA connections."""
    try:
        await connection_manager.stop_all_connections()

        return {
            "success": True,
            "message": "All SCADA connections stopped successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop all SCADA connections: {str(e)}")


@router.get(
    "/{connection_id}/statistics",
    response_model=Dict[str, Any],
    summary="Get SCADA connection statistics",
    description="Get comprehensive statistics for a SCADA connection",
    responses={
        200: {"description": "Connection statistics retrieved successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_connection_statistics(
    connection_id: str = Path(..., description="SCADA connection ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA connection statistics."""
    try:
        # Get connection
        connection = await connection_manager.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail=f"SCADA connection {connection_id} not found")

        # Get protocol connection statistics
        stats = None
        for adapter in connection_manager.protocol_adapters.values():
            conn = adapter.get_connection(connection_id)
            if conn:
                stats = conn.get_statistics()
                break

        return {
            "success": True,
            "message": "Connection statistics retrieved successfully",
            "data": {
                "connection_info": connection,
                "statistics": stats or {},
                "last_updated": datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get connection statistics: {str(e)}")


@router.get(
    "/statistics/global",
    response_model=Dict[str, Any],
    summary="Get global SCADA connection statistics",
    description="Get overall statistics for all SCADA connections",
    responses={
        200: {"description": "Global statistics retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_global_statistics(
    current_user = Depends(get_current_user)
):
    """Get global SCADA connection statistics."""
    try:
        stats = connection_manager.get_connection_statistics()

        return {
            "success": True,
            "message": "Global SCADA connection statistics retrieved successfully",
            "data": stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get global statistics: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=List[ScadaConnectionResponse],
    summary="Get SCADA connections by wind farm",
    description="Get all SCADA connections for a specific wind farm",
    responses={
        200: {"description": "SCADA connections retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_connections_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA connections by wind farm."""
    try:
        # Build filter for wind farm
        filter_params = ScadaConnectionFilter(wind_farm_id=wind_farm_id)

        result = await connection_manager.get_connections(
            db=db,
            filter_params=filter_params,
            pagination=None  # Get all connections for this wind farm
        )

        return result["items"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA connections by wind farm: {str(e)}")


@router.post(
    "/{connection_id}/test",
    response_model=Dict[str, Any],
    summary="Test SCADA connection",
    description="Test connectivity to SCADA server without starting data collection",
    responses={
        200: {"description": "Connection test completed"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def test_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    current_user = Depends(get_current_user)
):
    """Test SCADA connection."""
    try:
        # Find connection in adapters
        connection_found = False
        for adapter in connection_manager.protocol_adapters.values():
            conn = adapter.get_connection(connection_id)
            if conn:
                connection_found = True
                # Test connection health
                is_healthy = conn.is_healthy()
                stats = conn.get_statistics()

                return {
                    "success": True,
                    "message": "Connection test completed",
                    "data": {
                        "connection_id": connection_id,
                        "is_healthy": is_healthy,
                        "status": conn.status.value,
                        "statistics": stats,
                        "test_timestamp": datetime.utcnow().isoformat()
                    }
                }

        if not connection_found:
            raise HTTPException(status_code=404, detail=f"SCADA connection {connection_id} not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test SCADA connection: {str(e)}")