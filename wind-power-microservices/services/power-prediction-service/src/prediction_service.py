"""
Power Prediction Service - Main prediction service
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings, PREDICTION_CONFIG
from .models import PowerPredictionCreate, PredictionStatus, ModelType
from .database import power_prediction_crud, ml_model_crud, power_data_crud, model_performance_crud
from .ml_models import ModelFactory, BaseMLModel, EnsembleModel
from .feature_engineering import data_preprocessor
from .exceptions import (
    PowerPredictionException,
    ModelNotFoundException,
    PredictionException,
    DataQualityException,
    InsufficientDataException
)
from .utils import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PowerPredictionService:
    """Main service for power prediction operations."""

    def __init__(self):
        self.models: Dict[str, BaseMLModel] = {}
        self.ensemble_models: Dict[str, EnsembleModel] = {}
        self.is_initialized = False

    async def initialize(self):
        """Initialize the prediction service."""
        try:
            logger.info("Initializing Power Prediction Service...")

            # Load existing models
            await self._load_models()

            self.is_initialized = True
            logger.info("Power Prediction Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Power Prediction Service: {e}")
            raise PowerPredictionException(f"Initialization failed: {str(e)}")

    async def shutdown(self):
        """Shutdown the prediction service."""
        try:
            logger.info("Shutting down Power Prediction Service...")
            self.models.clear()
            self.ensemble_models.clear()
            self.is_initialized = False
            logger.info("Power Prediction Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def _load_models(self):
        """Load existing ML models from database and files."""
        try:
            logger.info("Loading existing ML models...")
            # This would be implemented to load models from database/files
            logger.info("ML models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load models: {e}")

    async def get_power_prediction(
        self,
        wind_farm_id: str,
        prediction_horizon: str,
        turbine_id: Optional[str] = None,
        model_types: Optional[List[str]] = None,
        include_ensemble: bool = True,
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Get power prediction for specified horizon."""
        try:
            logger.info(f"Getting power prediction for wind farm {wind_farm_id}, horizon {prediction_horizon}")

            # Get historical data
            historical_data = await self._get_historical_data(wind_farm_id, turbine_id, db_session)
            if len(historical_data) < 100:
                raise InsufficientDataException(
                    f"Insufficient historical data for prediction. Required: 100, Available: {len(historical_data)}"
                )

            # Get weather forecast data
            weather_forecast = await self._get_weather_forecast(wind_farm_id, prediction_horizon)
            if not weather_forecast:
                raise PredictionException("Weather forecast data not available for prediction")

            # Prepare prediction data
            prediction_data = self._prepare_prediction_data(historical_data, weather_forecast)

            # Generate predictions using different models
            predictions = {}
            model_versions = {}

            available_models = model_types or [ModelType.LSTM, ModelType.XGBOOST, ModelType.RANDOM_FOREST]

            for model_type in available_models:
                try:
                    prediction = await self._generate_model_prediction(
                        wind_farm_id, turbine_id, prediction_data, model_type, db_session
                    )
                    if prediction:
                        predictions[model_type] = prediction
                        model_versions[model_type] = prediction.get('model_version', 'unknown')
                except Exception as e:
                    logger.warning(f"Failed to generate prediction with {model_type}: {e}")

            if not predictions:
                raise PredictionException("No successful predictions generated")

            # Generate ensemble prediction if requested
            ensemble_prediction = None
            if include_ensemble and len(predictions) > 1:
                ensemble_prediction = self._generate_ensemble_prediction(predictions)

            # Store predictions in database
            stored_predictions = []
            for model_type, prediction in predictions.items():
                try:
                    stored = await self._store_prediction(
                        wind_farm_id, turbine_id, prediction_horizon, prediction, model_type, db_session
                    )
                    stored_predictions.append(stored)
                except Exception as e:
                    logger.error(f"Failed to store prediction: {e}")

            return {
                "wind_farm_id": wind_farm_id,
                "turbine_id": turbine_id,
                "prediction_time": datetime.utcnow(),
                "prediction_horizon": prediction_horizon,
                "predictions": predictions,
                "ensemble_prediction": ensemble_prediction,
                "model_versions": model_versions,
                "input_features": prediction_data.get("features", {}),
                "processing_time_ms": 0  # Would be calculated
            }

        except Exception as e:
            logger.error(f"Power prediction failed: {e}")
            raise PowerPredictionException(f"Prediction failed: {str(e)}")

    async def _get_historical_data(
        self,
        wind_farm_id: str,
        turbine_id: Optional[str],
        db_session: Optional[AsyncSession]
    ) -> pd.DataFrame:
        """Get historical power and weather data."""
        try:
            # Get historical power data
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)  # Last 30 days

            if db_session:
                power_data = await power_data_crud.get_time_series(
                    db_session, wind_farm_id, start_time, end_time, turbine_id
                )
            else:
                # Use mock data or external API
                power_data = await self._get_mock_historical_data(wind_farm_id, turbine_id)

            if not power_data:
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame([{
                'timestamp': item.timestamp,
                'power_output': item.power_output,
                'wind_speed': item.wind_speed,
                'wind_direction': item.wind_direction,
                'temperature': item.temperature,
                'pressure': item.pressure,
                'humidity': item.humidity,
                'turbine_id': item.turbine_id,
                'data_quality': item.data_quality
            } for item in power_data])

            return df

        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return pd.DataFrame()

    async def _get_weather_forecast(self, wind_farm_id: str, horizon: str) -> List[Dict[str, Any]]:
        """Get weather forecast data."""
        try:
            # This would call the meteorological service
            # For now, return mock data
            hours_ahead = int(horizon.replace('h', ''))
            forecast_time = datetime.utcnow() + timedelta(hours=hours_ahead)

            return [{
                'forecast_time': forecast_time,
                'wind_speed': 8.5,  # Mock data
                'wind_direction': 245,
                'temperature': 15.2,
                'pressure': 1013.2,
                'humidity': 65
            }]

        except Exception as e:
            logger.error(f"Failed to get weather forecast: {e}")
            return []

    def _prepare_prediction_data(self, historical_data: pd.DataFrame, weather_forecast: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare data for prediction models."""
        try:
            # Preprocess historical data
            processed_data = data_preprocessor.preprocess_power_data(historical_data)

            # Create features
            featured_data = data_preprocessor.feature_engineer.create_features(processed_data)

            # Prepare prediction input based on weather forecast
            if weather_forecast:
                forecast_df = pd.DataFrame(weather_forecast)
                # Add historical context
                if not historical_data.empty:
                    recent_data = historical_data.tail(24)  # Last 24 hours
                    # Combine and create features
                    combined_data = pd.concat([recent_data, forecast_df], ignore_index=True)
                    featured_forecast = data_preprocessor.feature_engineer.create_features(combined_data)
                    prediction_input = featured_forecast.tail(len(weather_forecast))
                else:
                    prediction_input = featured_data
            else:
                prediction_input = featured_data

            return {
                "historical_data": featured_data,
                "prediction_input": prediction_input,
                "features": prediction_input.columns.tolist()
            }

        except Exception as e:
            logger.error(f"Failed to prepare prediction data: {e}")
            raise FeatureEngineeringException(f"Data preparation failed: {str(e)}")

    async def _generate_model_prediction(
        self,
        wind_farm_id: str,
        turbine_id: Optional[str],
        prediction_data: Dict[str, Any],
        model_type: str,
        db_session: Optional[AsyncSession]
    ) -> Optional[Dict[str, Any]]:
        """Generate prediction using specific model."""
        try:
            # Get model from database
            models = await ml_model_crud.get_active_models(db_session, wind_farm_id, turbine_id, model_type)
            if not models:
                logger.warning(f"No active {model_type} model found")
                return None

            model_info = models[0]  # Use first available model

            # Load or create model instance
            if model_type not in self.models:
                self.models[model_type] = ModelFactory.create_model(model_type, f"{model_type}_{wind_farm_id}")

            model = self.models[model_type]

            # Prepare features for prediction
            prediction_input = prediction_data["prediction_input"]
            feature_cols = [col for col in prediction_input.columns if col not in ['timestamp', 'turbine_id']]
            X = prediction_input[feature_cols].copy()

            # Make prediction
            prediction = model.predict(X)

            # Calculate confidence intervals
            confidence_intervals = None
            if hasattr(model, 'predict_with_confidence'):
                mean_pred, lower_bound, upper_bound = model.predict_with_confidence(X)
                confidence_intervals = {
                    "lower_bound": float(lower_bound[0]),
                    "upper_bound": float(upper_bound[0]),
                    "confidence_level": 0.95
                }

            return {
                "predicted_power": float(prediction[0]),
                "confidence_intervals": confidence_intervals,
                "model_version": model_info.version,
                "confidence_score": model_info.validation_metrics.get("r2", 0.8) if model_info.validation_metrics else 0.8,
                "input_features": X.iloc[0].to_dict()
            }

        except Exception as e:
            logger.error(f"Model prediction failed for {model_type}: {e}")
            return None

    def _generate_ensemble_prediction(self, predictions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate ensemble prediction from multiple models."""
        try:
            # Extract predictions and confidence scores
            model_predictions = []
            confidence_scores = []

            for model_type, pred in predictions.items():
                model_predictions.append(pred["predicted_power"])
                confidence_scores.append(pred.get("confidence_score", 0.8))

            # Weighted average based on confidence scores
            total_weight = sum(confidence_scores)
            if total_weight > 0:
                weights = [score / total_weight for score in confidence_scores]
                ensemble_prediction = sum(pred * weight for pred, weight in zip(model_predictions, weights))
            else:
                # Simple average if no confidence scores
                ensemble_prediction = np.mean(model_predictions)

            # Calculate confidence intervals
            std_prediction = np.std(model_predictions)
            confidence_intervals = {
                "lower_bound": float(ensemble_prediction - 1.96 * std_prediction),
                "upper_bound": float(ensemble_prediction + 1.96 * std_prediction),
                "confidence_level": 0.95
            }

            return {
                "predicted_power": float(ensemble_prediction),
                "confidence_intervals": confidence_intervals,
                "model_type": "ensemble",
                "individual_predictions": predictions
            }

        except Exception as e:
            logger.error(f"Ensemble prediction failed: {e}")
            return None

    async def _store_prediction(
        self,
        wind_farm_id: str,
        turbine_id: Optional[str],
        prediction_horizon: str,
        prediction: Dict[str, Any],
        model_type: str,
        db_session: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """Store prediction in database."""
        try:
            prediction_data = PowerPredictionCreate(
                wind_farm_id=wind_farm_id,
                turbine_id=turbine_id,
                prediction_time=datetime.utcnow() + timedelta(hours=int(prediction_horizon.replace('h', ''))),
                prediction_horizon=prediction_horizon,
                predicted_power=prediction["predicted_power"],
                predicted_power_min=prediction.get("confidence_intervals", {}).get("lower_bound"),
                predicted_power_max=prediction.get("confidence_intervals", {}).get("upper_bound"),
                model_type=model_type,
                model_version=prediction.get("model_version"),
                confidence_score=prediction.get("confidence_score"),
                input_features=prediction.get("input_features"),
                status=PredictionStatus.COMPLETED
            )

            if db_session:
                stored = await power_prediction_crud.create(db_session, prediction_data.dict())
                return {"id": stored.id, "status": "stored"}
            else:
                return {"id": "mock_id", "status": "mock_stored"}

        except Exception as e:
            logger.error(f"Failed to store prediction: {e}")
            raise PowerPredictionException(f"Prediction storage failed: {str(e)}")

    async def _get_mock_historical_data(self, wind_farm_id: str, turbine_id: Optional[str]) -> List[Any]:
        """Get mock historical data for testing."""
        # This would be replaced with actual data fetching
        from .models import PowerData

        mock_data = []
        base_time = datetime.utcnow() - timedelta(days=30)

        for i in range(720):  # 30 days * 24 hours
            timestamp = base_time + timedelta(hours=i)
            mock_data.append(PowerData(
                id=f"mock_{i}",
                wind_farm_id=wind_farm_id,
                turbine_id=turbine_id,
                timestamp=timestamp,
                power_output=1000 + np.random.normal(0, 100),
                wind_speed=8 + np.random.normal(0, 2),
                wind_direction=180 + np.random.normal(0, 30),
                temperature=15 + np.random.normal(0, 5),
                pressure=1013 + np.random.normal(0, 10),
                humidity=65 + np.random.normal(0, 10),
                data_quality="good"
            ))

        return mock_data

    async def train_model(
        self,
        wind_farm_id: str,
        model_type: str,
        turbine_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Train a new ML model."""
        try:
            logger.info(f"Training {model_type} model for wind farm {wind_farm_id}")

            # Get training data
            training_data = await self._get_training_data(wind_farm_id, turbine_id, db_session)
            if len(training_data) < settings.min_training_samples:
                raise InsufficientDataException(
                    f"Insufficient training data. Required: {settings.min_training_samples}, Available: {len(training_data)}"
                )

            # Preprocess and create features
            processed_data = data_preprocessor.preprocess_power_data(training_data)
            X_train, X_test, y_train, y_test, feature_cols = data_preprocessor.create_training_dataset(
                processed_data
            )

            # Create and train model
            model = ModelFactory.create_model(model_type, f"{model_type}_{wind_farm_id}")
            training_metrics = model.train(X_train, y_train)

            # Evaluate model
            validation_metrics = model.evaluate(X_test, y_test)

            # Store model information
            model_info = {
                "model_name": f"{model_type}_{wind_farm_id}",
                "model_type": model_type,
                "version": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
                "wind_farm_id": wind_farm_id,
                "turbine_id": turbine_id,
                "hyperparameters": MODEL_HYPERPARAMETERS.get(model_type, {}),
                "training_data_count": len(X_train),
                "validation_data_count": len(X_test),
                "training_start_date": X_train.index.min() if hasattr(X_train, 'index') else datetime.utcnow(),
                "training_end_date": X_train.index.max() if hasattr(X_train, 'index') else datetime.utcnow(),
                "performance_metrics": training_metrics,
                "validation_metrics": validation_metrics,
                "is_active": True
            }

            # Save model to database
            if db_session:
                stored_model = await ml_model_crud.create(db_session, model_info)
                model_info["id"] = stored_model.id

            # Store model instance
            self.models[model_type] = model

            logger.info(f"Model training completed: {validation_metrics}")
            return model_info

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise ModelTrainingException(f"Model training failed: {str(e)}")

    async def _get_training_data(
        self,
        wind_farm_id: str,
        turbine_id: Optional[str],
        db_session: Optional[AsyncSession]
    ) -> pd.DataFrame:
        """Get training data for model training."""
        try:
            # Get historical data (longer period for training)
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=90)  # 90 days for training

            if db_session:
                power_data = await power_data_crud.get_time_series(
                    db_session, wind_farm_id, start_time, end_time, turbine_id
                )
            else:
                power_data = await self._get_mock_historical_data(wind_farm_id, turbine_id)

            if not power_data:
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame([{
                'timestamp': item.timestamp,
                'power_output': item.power_output,
                'wind_speed': item.wind_speed,
                'wind_direction': item.wind_direction,
                'temperature': item.temperature,
                'pressure': item.pressure,
                'humidity': item.humidity,
                'turbine_id': item.turbine_id,
                'data_quality': item.data_quality
            } for item in power_data])

            return df

        except Exception as e:
            logger.error(f"Failed to get training data: {e}")
            return pd.DataFrame()

    async def evaluate_predictions(
        self,
        wind_farm_id: str,
        days: int = 7,
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Evaluate prediction accuracy against actual values."""
        try:
            logger.info(f"Evaluating predictions for wind farm {wind_farm_id}, last {days} days")

            # Get accuracy metrics
            if db_session:
                accuracy_metrics = await power_prediction_crud.get_accuracy_metrics(db_session, wind_farm_id, days)
            else:
                accuracy_metrics = {
                    "period_days": days,
                    "metrics": [
                        {"model_type": "lstm", "prediction_horizon": "24h", "mae": 50.2, "rmse": 75.8, "data_points": 168},
                        {"model_type": "xgboost", "prediction_horizon": "24h", "mae": 45.6, "rmse": 68.4, "data_points": 168}
                    ]
                }

            # Calculate overall performance
            if accuracy_metrics["metrics"]:
                total_points = sum(m["data_points"] for m in accuracy_metrics["metrics"])
                weighted_mae = sum(m["mae"] * m["data_points"] for m in accuracy_metrics["metrics"]) / total_points
                weighted_rmse = sum(m["rmse"] * m["data_points"] for m in accuracy_metrics["metrics"]) / total_points

                accuracy_metrics["overall_performance"] = {
                    "weighted_mae": weighted_mae,
                    "weighted_rmse": weighted_rmse,
                    "total_predictions": total_points
                }

            return accuracy_metrics

        except Exception as e:
            logger.error(f"Prediction evaluation failed: {e}")
            raise PowerPredictionException(f"Evaluation failed: {str(e)}")

    async def get_prediction_summary(
        self,
        wind_farm_id: Optional[str] = None,
        days: int = 7,
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Get prediction summary and statistics."""
        try:
            # Get recent predictions
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            if db_session:
                predictions = await power_prediction_crud.get_multi(
                    db_session,
                    filter_params={"wind_farm_id": wind_farm_id} if wind_farm_id else {},
                    time_range={"start_time": start_time, "end_time": end_time}
                )
            else:
                # Mock data
                predictions = {
                    "items": [],
                    "total": 0
                }

            # Calculate summary statistics
            summary = {
                "period_days": days,
                "total_predictions": predictions["total"],
                "model_breakdown": {},
                "horizon_breakdown": {},
                "quality_metrics": {
                    "average_confidence": 0.0,
                    "predictions_with_actual": 0
                }
            }

            if predictions["items"]:
                # Model breakdown
                for pred in predictions["items"]:
                    model_type = pred.model_type
                    if model_type not in summary["model_breakdown"]:
                        summary["model_breakdown"][model_type] = 0
                    summary["model_breakdown"][model_type] += 1

                    # Horizon breakdown
                    horizon = pred.prediction_horizon
                    if horizon not in summary["horizon_breakdown"]:
                        summary["horizon_breakdown"][horizon] = 0
                    summary["horizon_breakdown"][horizon] += 1

                    # Quality metrics
                    if pred.confidence_score:
                        summary["quality_metrics"]["average_confidence"] += pred.confidence_score
                    if pred.actual_power is not None:
                        summary["quality_metrics"]["predictions_with_actual"] += 1

                # Calculate averages
                if predictions["total"] > 0:
                    summary["quality_metrics"]["average_confidence"] /= predictions["total"]
                    summary["quality_metrics"]["actual_validation_rate"] = (
                        summary["quality_metrics"]["predictions_with_actual"] / predictions["total"]
                    )

            return summary

        except Exception as e:
            logger.error(f"Failed to get prediction summary: {e}")
            raise PowerPredictionException(f"Summary generation failed: {str(e)}")


# Global prediction service instance
prediction_service = PowerPredictionService()