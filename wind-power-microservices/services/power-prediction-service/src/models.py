"""
Data models for Power Prediction Service
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class PredictionStatus(str, Enum):
    """Prediction status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelType(str, Enum):
    """ML model type enumeration."""
    LSTM = "lstm"
    XGBOOST = "xgboost"
    RANDOM_FOREST = "random_forest"
    ENSEMBLE = "ensemble"
    PERSISTENCE = "persistence"
    ARIMA = "arima"


class PredictionHorizon(str, Enum):
    """Prediction horizon enumeration."""
    HOUR_1 = "1h"
    HOUR_6 = "6h"
    HOUR_12 = "12h"
    HOUR_24 = "24h"
    HOUR_48 = "48h"
    HOUR_72 = "72h"


class PowerDataSource(str, Enum):
    """Power data source enumeration."""
    SCADA = "scada"
    MANUAL = "manual"
    CALCULATED = "calculated"
    ESTIMATED = "estimated"


class DataQuality(str, Enum):
    """Data quality enumeration."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    BAD = "bad"


# Database Models
class PowerPrediction(Base):
    """Power prediction database model."""
    __tablename__ = "power_predictions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    wind_farm_id = Column(String, ForeignKey("wind_farms.id"), nullable=False, index=True)
    turbine_id = Column(String, ForeignKey("turbines.id"), nullable=True, index=True)
    prediction_time = Column(DateTime, nullable=False, index=True)
    prediction_horizon = Column(String, nullable=False, index=True)  # e.g., "1h", "6h", "24h"
    predicted_power = Column(Float, nullable=False)
    predicted_power_min = Column(Float, nullable=True)  # Confidence interval lower bound
    predicted_power_max = Column(Float, nullable=True)  # Confidence interval upper bound
    model_type = Column(String, nullable=False, index=True)
    model_version = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    input_features = Column(JSON, nullable=True)  # Features used for prediction
    actual_power = Column(Float, nullable=True)  # For validation
    accuracy_metrics = Column(JSON, nullable=True)  # MAE, MSE, etc.
    data_quality = Column(String, nullable=False, default=DataQuality.GOOD)
    status = Column(String, nullable=False, default=PredictionStatus.COMPLETED, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    wind_farm = relationship("WindFarm", back_populates="power_predictions")
    turbine = relationship("Turbine", back_populates="power_predictions")


class MLModel(Base):
    """ML model database model."""
    __tablename__ = "ml_models"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_name = Column(String, nullable=False, index=True)
    model_type = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)
    wind_farm_id = Column(String, ForeignKey("wind_farms.id"), nullable=True, index=True)
    turbine_id = Column(String, ForeignKey("turbines.id"), nullable=True, index=True)
    hyperparameters = Column(JSON, nullable=True)
    feature_importance = Column(JSON, nullable=True)
    training_data_count = Column(Integer, nullable=True)
    validation_data_count = Column(Integer, nullable=True)
    training_start_date = Column(DateTime, nullable=True)
    training_end_date = Column(DateTime, nullable=True)
    performance_metrics = Column(JSON, nullable=True)  # Training metrics
    validation_metrics = Column(JSON, nullable=True)  # Validation metrics
    model_file_path = Column(String, nullable=True)
    model_size_bytes = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    # Relationships
    wind_farm = relationship("WindFarm", back_populates="ml_models")
    turbine = relationship("Turbine", back_populates="ml_models")


class TrainingJob(Base):
    """Training job database model."""
    __tablename__ = "training_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_name = Column(String, nullable=False, index=True)
    model_type = Column(String, nullable=False, index=True)
    wind_farm_id = Column(String, ForeignKey("wind_farms.id"), nullable=True, index=True)
    turbine_id = Column(String, ForeignKey("turbines.id"), nullable=True, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    progress = Column(Integer, default=0)  # 0-100
    hyperparameters = Column(JSON, nullable=True)
    training_config = Column(JSON, nullable=True)
    data_config = Column(JSON, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    model_id = Column(String, ForeignKey("ml_models.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String, nullable=True)

    # Relationships
    wind_farm = relationship("WindFarm", back_populates="training_jobs")
    turbine = relationship("Turbine", back_populates="training_jobs")
    model = relationship("MLModel", back_populates="training_jobs")


class PowerData(Base):
    """Power data database model."""
    __tablename__ = "power_data"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    wind_farm_id = Column(String, ForeignKey("wind_farms.id"), nullable=False, index=True)
    turbine_id = Column(String, ForeignKey("turbines.id"), nullable=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    power_output = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=True)
    wind_direction = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    turbine_status = Column(String, nullable=True)
    availability = Column(Float, nullable=True)  # 0-1
    efficiency = Column(Float, nullable=True)  # 0-1
    source = Column(String, nullable=False, default=PowerDataSource.SCADA)
    data_quality = Column(String, nullable=False, default=DataQuality.GOOD)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    wind_farm = relationship("WindFarm", back_populates="power_data")
    turbine = relationship("Turbine", back_populates="power_data")


class ModelPerformance(Base):
    """Model performance tracking database model."""
    __tablename__ = "model_performance"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String, ForeignKey("ml_models.id"), nullable=False, index=True)
    prediction_id = Column(String, ForeignKey("power_predictions.id"), nullable=True, index=True)
    evaluation_date = Column(DateTime, nullable=False, index=True)
    prediction_horizon = Column(String, nullable=False, index=True)
    mae = Column(Float, nullable=True)  # Mean Absolute Error
    mse = Column(Float, nullable=True)  # Mean Squared Error
    rmse = Column(Float, nullable=True)  # Root Mean Squared Error
    mape = Column(Float, nullable=True)  # Mean Absolute Percentage Error
    r2 = Column(Float, nullable=True)  # R-squared
    accuracy = Column(Float, nullable=True)  # Overall accuracy
    bias = Column(Float, nullable=True)  # Prediction bias
    data_points = Column(Integer, nullable=True)  # Number of evaluation points
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    model = relationship("MLModel", back_populates="performance_metrics")
    prediction = relationship("PowerPrediction", back_populates="performance_metrics")


# Reference tables (would be imported from other services)
class WindFarm(Base):
    """Wind farm reference model."""
    __tablename__ = "wind_farms"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    capacity_mw = Column(Float, nullable=True)
    number_of_turbines = Column(Integer, nullable=True)
    commission_date = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    power_predictions = relationship("PowerPrediction", back_populates="wind_farm")
    ml_models = relationship("MLModel", back_populates="wind_farm")
    training_jobs = relationship("TrainingJob", back_populates="wind_farm")
    power_data = relationship("PowerData", back_populates="wind_farm")


class Turbine(Base):
    """Turbine reference model."""
    __tablename__ = "turbines"

    id = Column(String, primary_key=True)
    wind_farm_id = Column(String, ForeignKey("wind_farms.id"), nullable=False)
    name = Column(String, nullable=False)
    model = Column(String, nullable=True)
    capacity_kw = Column(Float, nullable=True)
    hub_height = Column(Float, nullable=True)
    rotor_diameter = Column(Float, nullable=True)
    commission_date = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    power_predictions = relationship("PowerPrediction", back_populates="turbine")
    ml_models = relationship("MLModel", back_populates="turbine")
    training_jobs = relationship("TrainingJob", back_populates="turbine")
    power_data = relationship("PowerData", back_populates="turbine")
    wind_farm = relationship("WindFarm")


# Pydantic Models for API
class PowerPredictionCreate(BaseModel):
    """Power prediction create model."""
    wind_farm_id: str
    turbine_id: Optional[str] = None
    prediction_time: datetime
    prediction_horizon: str
    predicted_power: float
    predicted_power_min: Optional[float] = None
    predicted_power_max: Optional[float] = None
    model_type: str
    model_version: Optional[str] = None
    confidence_score: Optional[float] = None
    input_features: Optional[Dict[str, Any]] = None
    data_quality: str = DataQuality.GOOD
    notes: Optional[str] = None

    @validator('predicted_power')
    def validate_predicted_power(cls, v):
        if v < 0:
            raise ValueError('Predicted power must be non-negative')
        return v

    @validator('confidence_score')
    def validate_confidence_score(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Confidence score must be between 0 and 1')
        return v


class PowerPredictionResponse(BaseModel):
    """Power prediction response model."""
    id: str
    wind_farm_id: str
    turbine_id: Optional[str]
    prediction_time: datetime
    prediction_horizon: str
    predicted_power: float
    predicted_power_min: Optional[float]
    predicted_power_max: Optional[float]
    model_type: str
    model_version: Optional[str]
    confidence_score: Optional[float]
    input_features: Optional[Dict[str, Any]]
    actual_power: Optional[float]
    accuracy_metrics: Optional[Dict[str, Any]]
    data_quality: str
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    notes: Optional[str]

    class Config:
        orm_mode = True


class MLModelCreate(BaseModel):
    """ML model create model."""
    model_name: str
    model_type: str
    version: str
    wind_farm_id: Optional[str] = None
    turbine_id: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    training_data_count: Optional[int] = None
    validation_data_count: Optional[int] = None
    training_start_date: Optional[datetime] = None
    training_end_date: Optional[datetime] = None
    model_file_path: Optional[str] = None
    is_active: bool = True
    description: Optional[str] = None


class MLModelResponse(BaseModel):
    """ML model response model."""
    id: str
    model_name: str
    model_type: str
    version: str
    wind_farm_id: Optional[str]
    turbine_id: Optional[str]
    hyperparameters: Optional[Dict[str, Any]]
    feature_importance: Optional[Dict[str, Any]]
    training_data_count: Optional[int]
    validation_data_count: Optional[int]
    training_start_date: Optional[datetime]
    training_end_date: Optional[datetime]
    performance_metrics: Optional[Dict[str, Any]]
    validation_metrics: Optional[Dict[str, Any]]
    model_file_path: Optional[str]
    model_size_bytes: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    description: Optional[str]

    class Config:
        orm_mode = True


class TrainingJobCreate(BaseModel):
    """Training job create model."""
    job_name: str
    model_type: str
    wind_farm_id: Optional[str] = None
    turbine_id: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    training_config: Optional[Dict[str, Any]] = None
    data_config: Optional[Dict[str, Any]] = None


class TrainingJobResponse(BaseModel):
    """Training job response model."""
    id: str
    job_name: str
    model_type: str
    wind_farm_id: Optional[str]
    turbine_id: Optional[str]
    status: str
    progress: int
    hyperparameters: Optional[Dict[str, Any]]
    training_config: Optional[Dict[str, Any]]
    data_config: Optional[Dict[str, Any]]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]
    model_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        orm_mode = True


class PowerDataCreate(BaseModel):
    """Power data create model."""
    wind_farm_id: str
    turbine_id: Optional[str] = None
    timestamp: datetime
    power_output: float
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    humidity: Optional[float] = None
    turbine_status: Optional[str] = None
    availability: Optional[float] = None
    efficiency: Optional[float] = None
    source: str = PowerDataSource.SCADA
    data_quality: str = DataQuality.GOOD

    @validator('power_output')
    def validate_power_output(cls, v):
        if v < 0:
            raise ValueError('Power output must be non-negative')
        return v

    @validator('availability')
    def validate_availability(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Availability must be between 0 and 1')
        return v

    @validator('efficiency')
    def validate_efficiency(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Efficiency must be between 0 and 1')
        return v


class PowerDataResponse(BaseModel):
    """Power data response model."""
    id: str
    wind_farm_id: str
    turbine_id: Optional[str]
    timestamp: datetime
    power_output: float
    wind_speed: Optional[float]
    wind_direction: Optional[float]
    temperature: Optional[float]
    pressure: Optional[float]
    humidity: Optional[float]
    turbine_status: Optional[str]
    availability: Optional[float]
    efficiency: Optional[float]
    source: str
    data_quality: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ModelPerformanceCreate(BaseModel):
    """Model performance create model."""
    model_id: str
    prediction_id: Optional[str] = None
    evaluation_date: datetime
    prediction_horizon: str
    mae: Optional[float] = None
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    r2: Optional[float] = None
    accuracy: Optional[float] = None
    bias: Optional[float] = None
    data_points: Optional[int] = None


class ModelPerformanceResponse(BaseModel):
    """Model performance response model."""
    id: str
    model_id: str
    prediction_id: Optional[str]
    evaluation_date: datetime
    prediction_horizon: str
    mae: Optional[float]
    mse: Optional[float]
    rmse: Optional[float]
    mape: Optional[float]
    r2: Optional[float]
    accuracy: Optional[float]
    bias: Optional[float]
    data_points: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True


class PredictionRequest(BaseModel):
    """Power prediction request model."""
    wind_farm_id: str
    turbine_id: Optional[str] = None
    prediction_horizon: str = "24h"
    model_types: Optional[List[str]] = None
    include_ensemble: bool = True
    include_confidence_intervals: bool = True


class BatchPredictionRequest(BaseModel):
    """Batch power prediction request model."""
    wind_farm_id: str
    turbine_ids: Optional[List[str]] = None
    prediction_horizons: List[str] = ["1h", "6h", "24h"]
    model_types: Optional[List[str]] = None
    include_ensemble: bool = True


class PredictionResponse(BaseModel):
    """Power prediction response model."""
    wind_farm_id: str
    turbine_id: Optional[str]
    prediction_time: datetime
    prediction_horizon: str
    predictions: List[Dict[str, Any]]  # Model predictions
    ensemble_prediction: Optional[Dict[str, Any]] = None
    confidence_intervals: Optional[Dict[str, Any]] = None
    input_features: Optional[Dict[str, Any]] = None
    model_versions: Dict[str, str]
    processing_time_ms: float


class SuccessResponse(BaseModel):
    """Success response model."""
    success: bool = True
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """Pagination parameters model."""
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=200, description="Page size")


class PredictionFilter(BaseModel):
    """Prediction filter model."""
    wind_farm_id: Optional[str] = None
    turbine_id: Optional[str] = None
    model_type: Optional[str] = None
    prediction_horizon: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    data_quality: Optional[str] = None


class ModelFilter(BaseModel):
    """Model filter model."""
    model_type: Optional[str] = None
    wind_farm_id: Optional[str] = None
    turbine_id: Optional[str] = None
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None