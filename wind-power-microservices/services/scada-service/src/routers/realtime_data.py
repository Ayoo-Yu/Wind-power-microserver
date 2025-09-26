"""
SCADA Real-time Data API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from ..database import get_db_session
from ..models import (
    ScadaDataPoint,
    RealtimeDataResponse,
    DataAggregationRequest,
    DataAggregationResponse,
    ErrorResponse,
    DataPointType,
    DataQuality
)
from ..services import ConnectionManager, DataProcessor, RealtimeDataAggregator
from ..auth import get_current_user
from ..exceptions import (
    ScadaConnectionNotFoundException,
    InvalidScadaDataException,
    ValidationException
)
from ..utils import get_logger

router = APIRouter(prefix="/api/v1/realtime-data", tags=["scada-realtime-data"])

# Global service instances
connection_manager = ConnectionManager()
data_processor = DataProcessor()
data_aggregator = RealtimeDataAggregator()
logger = get_logger(__name__)

# WebSocket connection manager
class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, client_info: Dict[str, Any]):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_info[websocket] = client_info
        logger.info(f"WebSocket client connected: {client_info}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            client_info = self.connection_info.pop(websocket, {})
            logger.info(f"WebSocket client disconnected: {client_info}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            self.disconnect(websocket)

    async def broadcast_message(self, message: Dict[str, Any]):
        disconnected = []
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting WebSocket message: {e}")
                disconnected.append(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)

websocket_manager = WebSocketManager()


@router.get(
    "/current",
    response_model=Dict[str, Any],
    summary="Get current real-time data",
    description="Retrieve current real-time SCADA data with filtering options",
    responses={
        200: {"description": "Real-time data retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_current_data(
    # Filter parameters
    connection_id: Optional[str] = Query(None, description="Filter by connection ID"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    turbine_id: Optional[str] = Query(None, description="Filter by turbine ID"),
    point_id: Optional[str] = Query(None, description="Filter by specific point ID"),
    quality: Optional[str] = Query(None, description="Filter by data quality (good/bad/uncertain)"),

    # Time range (optional)
    minutes: int = Query(5, ge=1, le=60, description="Get data from last N minutes"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get current real-time SCADA data."""
    try:
        # Get recent data from InfluxDB
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        # Build query filters
        filters = {}
        if connection_id:
            filters["connection_id"] = connection_id
        if wind_farm_id:
            filters["wind_farm_id"] = wind_farm_id
        if turbine_id:
            filters["turbine_id"] = turbine_id
        if point_id:
            filters["point_id"] = point_id
        if quality:
            filters["quality"] = quality

        # Query InfluxDB for recent data
        data_points = await connection_manager.influxdb_manager.query_points(
            measurement="scada_data",
            start_time=start_time,
            end_time=end_time,
            filters=filters
        )

        return {
            "success": True,
            "message": "Current real-time data retrieved successfully",
            "data": {
                "data_points": data_points,
                "total_points": len(data_points),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get current real-time data: {str(e)}")


@router.get(
    "/by-connection/{connection_id}",
    response_model=Dict[str, Any],
    summary="Get real-time data by connection",
    description="Retrieve current real-time data for a specific SCADA connection",
    responses={
        200: {"description": "Connection real-time data retrieved successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_by_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    minutes: int = Query(5, ge=1, le=60, description="Get data from last N minutes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get real-time data by connection."""
    try:
        # Validate connection exists
        connection = await connection_manager.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail=f"SCADA connection {connection_id} not found")

        # Get recent data for connection
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        data_points = await connection_manager.influxdb_manager.query_points(
            measurement="scada_data",
            start_time=start_time,
            end_time=end_time,
            filters={"connection_id": connection_id}
        )

        # Group by turbine and point type
        grouped_data = {}
        for point in data_points:
            turbine_id = point.get("turbine_id", "unknown")
            point_name = point.get("point_name", "unknown")

            if turbine_id not in grouped_data:
                grouped_data[turbine_id] = {}

            grouped_data[turbine_id][point_name] = {
                "value": point.get("value"),
                "quality": point.get("quality"),
                "timestamp": point.get("timestamp"),
                "unit": point.get("unit", "")
            }

        return {
            "success": True,
            "message": f"Real-time data for connection {connection_id} retrieved successfully",
            "data": {
                "connection_id": connection_id,
                "connection_name": connection.name,
                "data": grouped_data,
                "total_points": len(data_points),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get connection real-time data: {str(e)}")


@router.get(
    "/by-turbine/{turbine_id}",
    response_model=Dict[str, Any],
    summary="Get real-time data by turbine",
    description="Retrieve current real-time data for a specific turbine",
    responses={
        200: {"description": "Turbine real-time data retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_by_turbine(
    turbine_id: str = Path(..., description="Turbine ID"),
    minutes: int = Query(5, ge=1, le=60, description="Get data from last N minutes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get real-time data by turbine."""
    try:
        # Get recent data for turbine
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        data_points = await connection_manager.influxdb_manager.query_points(
            measurement="scada_data",
            start_time=start_time,
            end_time=end_time,
            filters={"turbine_id": turbine_id}
        )

        # Organize by point name
        turbine_data = {}
        for point in data_points:
            point_name = point.get("point_name", "unknown")
            turbine_data[point_name] = {
                "value": point.get("value"),
                "quality": point.get("quality"),
                "timestamp": point.get("timestamp"),
                "unit": point.get("unit", "")
            }

        return {
            "success": True,
            "message": f"Real-time data for turbine {turbine_id} retrieved successfully",
            "data": {
                "turbine_id": turbine_id,
                "data": turbine_data,
                "total_points": len(data_points),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get turbine real-time data: {str(e)}")


@router.post(
    "/aggregate",
    response_model=Dict[str, Any],
    summary="Aggregate real-time data",
    description="Aggregate SCADA data over specified time windows",
    responses={
        200: {"description": "Data aggregation completed successfully"},
        400: {"description": "Invalid aggregation request", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def aggregate_data(
    aggregation_request: DataAggregationRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Aggregate real-time SCADA data."""
    try:
        # Get data for aggregation
        data_points = await connection_manager.influxdb_manager.query_points(
            measurement="scada_data",
            start_time=aggregation_request.start_time,
            end_time=aggregation_request.end_time,
            filters=aggregation_request.filters or {}
        )

        # Convert to ScadaDataPoint objects for processing
        scada_points = []
        for point_data in data_points:
            point = ScadaDataPoint(
                point_id=point_data.get("point_id", ""),
                point_name=point_data.get("point_name", ""),
                value=point_data.get("value", 0),
                quality=point_data.get("quality", "good"),
                timestamp=point_data.get("timestamp", datetime.utcnow()),
                wind_farm_id=point_data.get("wind_farm_id", ""),
                turbine_id=point_data.get("turbine_id", ""),
                connection_id=point_data.get("connection_id", "")
            )
            scada_points.append(point)

        # Perform aggregation
        aggregation_result = await data_aggregator.aggregate_data_points(
            scada_points,
            aggregation_request.window
        )

        return {
            "success": True,
            "message": "Data aggregation completed successfully",
            "data": aggregation_result
        }

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to aggregate data: {str(e)}")


@router.get(
    "/latest/{point_id}",
    response_model=Dict[str, Any],
    summary="Get latest data point value",
    description="Retrieve the latest value for a specific data point",
    responses={
        200: {"description": "Latest data point value retrieved successfully"},
        404: {"description": "Data point not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_latest_point_value(
    point_id: str = Path(..., description="Data point ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get latest value for a specific data point."""
    try:
        # Get latest data point from InfluxDB
        latest_data = await connection_manager.influxdb_manager.get_latest_point(
            measurement="scada_data",
            point_id=point_id
        )

        if not latest_data:
            raise HTTPException(status_code=404, detail=f"No data found for point {point_id}")

        return {
            "success": True,
            "message": "Latest data point value retrieved successfully",
            "data": latest_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get latest point value: {str(e)}")


@router.websocket("/ws/{wind_farm_id}")
async def websocket_realtime_data(
    websocket: WebSocket,
    wind_farm_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """WebSocket endpoint for real-time data streaming."""
    try:
        # Accept WebSocket connection
        client_info = {"wind_farm_id": wind_farm_id, "connected_at": datetime.utcnow().isoformat()}
        await websocket_manager.connect(websocket, client_info)

        logger.info(f"WebSocket connection established for wind farm {wind_farm_id}")

        # Add callback for real-time data
        async def data_callback(data_points: List[ScadaDataPoint]):
            # Filter data for this wind farm
            wind_farm_data = [
                point for point in data_points
                if point.wind_farm_id == wind_farm_id
            ]

            if wind_farm_data:
                message = {
                    "type": "realtime_data",
                    "wind_farm_id": wind_farm_id,
                    "data": [
                        {
                            "point_id": point.point_id,
                            "point_name": point.point_name,
                            "value": point.value,
                            "quality": point.quality,
                            "timestamp": point.timestamp.isoformat(),
                            "turbine_id": point.turbine_id
                        }
                        for point in wind_farm_data
                    ],
                    "timestamp": datetime.utcnow().isoformat()
                }

                await websocket_manager.send_personal_message(message, websocket)

        # Register callback
        connection_manager.add_data_callback(data_callback)

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive and handle client messages
                data = await websocket.receive_json()

                # Handle different message types
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "subscribe_turbine":
                    turbine_id = data.get("turbine_id")
                    # Handle turbine-specific subscription
                    logger.info(f"Client subscribed to turbine {turbine_id}")
                elif data.get("type") == "unsubscribe_turbine":
                    turbine_id = data.get("turbine_id")
                    # Handle turbine unsubscription
                    logger.info(f"Client unsubscribed from turbine {turbine_id}")

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Clean up
        websocket_manager.disconnect(websocket)
        logger.info(f"WebSocket connection closed for wind farm {wind_farm_id}")


@router.get(
    "/statistics/processing",
    response_model=Dict[str, Any],
    summary="Get data processing statistics",
    description="Get statistics about real-time data processing performance",
    responses={
        200: {"description": "Processing statistics retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_processing_statistics(
    current_user = Depends(get_current_user)
):
    """Get data processing statistics."""
    try:
        stats = await data_processor.get_processing_statistics()

        return {
            "success": True,
            "message": "Processing statistics retrieved successfully",
            "data": stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get processing statistics: {str(e)}")


@router.post(
    "/simulate/{connection_id}",
    response_model=Dict[str, Any],
    summary="Simulate real-time data",
    description="Generate simulated real-time data for testing purposes",
    responses={
        200: {"description": "Data simulation completed"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def simulate_realtime_data(
    connection_id: str = Path(..., description="SCADA connection ID"),
    count: int = Query(10, ge=1, le=100, description="Number of data points to simulate"),
    include_alarms: bool = Query(False, description="Include alarm data points"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Simulate real-time data for testing."""
    try:
        # Validate connection exists
        connection = await connection_manager.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail=f"SCADA connection {connection_id} not found")

        # Generate simulated data points
        import random
        simulated_points = []

        for i in range(count):
            # Simulate different types of data points
            point_types = ["Power", "WindSpeed", "RotorSpeed", "Temperature", "Status"]
            point_type = random.choice(point_types)

            if point_type == "Power":
                value = random.uniform(0, 2.5)  # 0-2.5 MW
                unit = "MW"
            elif point_type == "WindSpeed":
                value = random.uniform(0, 20)  # 0-20 m/s
                unit = "m/s"
            elif point_type == "RotorSpeed":
                value = random.uniform(0, 25)  # 0-25 rpm
                unit = "rpm"
            elif point_type == "Temperature":
                value = random.uniform(-10, 50)  # -10 to 50°C
                unit = "°C"
            else:  # Status
                value = random.choice([0, 1])  # Binary status
                unit = ""

            # Determine quality and alarm status
            quality = random.choice(["good", "good", "good", "uncertain", "bad"])  # 60% good, 20% uncertain, 20% bad
            is_alarm = include_alarms and random.random() < 0.2  # 20% chance of alarm if enabled

            data_point = ScadaDataPoint(
                point_id=f"SIM_{connection_id}_{i}_{point_type}",
                point_name=f"WT001.{point_type}",
                value=value,
                quality=quality,
                timestamp=datetime.utcnow(),
                is_alarm=is_alarm,
                connection_id=connection_id,
                wind_farm_id=connection.wind_farm_id,
                turbine_id="WT001"
            )

            simulated_points.append(data_point)

        # Process simulated data
        processing_result = await data_processor.process_data_points(simulated_points)

        # Store in InfluxDB
        await connection_manager._handle_data_points(simulated_points)

        return {
            "success": True,
            "message": f"Generated {count} simulated data points",
            "data": {
                "simulated_points": len(simulated_points),
                "processing_result": processing_result,
                "include_alarms": include_alarms
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate real-time data: {str(e)}")