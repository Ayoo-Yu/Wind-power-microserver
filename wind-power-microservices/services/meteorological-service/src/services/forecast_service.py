"""
Weather forecasting service using multiple models and approaches
"""

import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib

from ..models import (
    WeatherParameter, WeatherForecastCreate, WeatherDataResponse,
    ForecastPoint, ForecastSeries, ForecastAccuracy
)
from ..database import weather_data_crud, weather_forecast_crud
from ..config import get_settings
from ..utils import get_logger

logger = get_logger(__name__)


class ForecastModel:
    """Base forecast model."""

    def __init__(self, name: str, parameters: List[WeatherParameter]):
        self.name = name
        self.parameters = parameters
        self.is_trained = False
        self.models = {}
        self.scalers = {}

    async def train(self, training_data: List[WeatherDataResponse]) -> bool:
        """Train the forecast model."""
        try:
            if len(training_data) < 50:
                logger.warning(f"Insufficient training data for {self.name}")
                return False

            # Prepare data for training
            df = self._prepare_training_data(training_data)

            # Train models for each parameter
            for parameter in self.parameters:
                if parameter in df.columns:
                    model, scaler = self._train_parameter_model(df, parameter)
                    self.models[parameter] = model
                    self.scalers[parameter] = scaler

            self.is_trained = True
            logger.info(f"Forecast model {self.name} trained successfully")
            return True

        except Exception as e:
            logger.error(f"Error training forecast model {self.name}: {e}")
            return False

    async def predict(
        self,
        station_id: str,
        wind_farm_id: str,
        start_time: datetime,
        hours: int,
        historical_data: List[WeatherDataResponse]
    ) -> ForecastSeries:
        """Generate forecast using the trained model."""
        if not self.is_trained:
            raise ValueError(f"Model {self.name} is not trained")

        try:
            forecast_points = []

            for hour in range(1, hours + 1):
                forecast_time = start_time + timedelta(hours=hour)

                # Prepare input features
                features = self._prepare_prediction_features(
                    historical_data, forecast_time, hour
                )

                # Predict parameters
                predicted_params = {}
                for parameter in self.parameters:
                    if parameter in self.models:
                        prediction = self._predict_parameter(parameter, features)
                        predicted_params[parameter] = prediction

                forecast_point = ForecastPoint(
                    time=forecast_time,
                    temperature=predicted_params.get(WeatherParameter.TEMPERATURE),
                    wind_speed=predicted_params.get(WeatherParameter.WIND_SPEED),
                    wind_direction=predicted_params.get(WeatherParameter.WIND_DIRECTION),
                    pressure=predicted_params.get(WeatherParameter.PRESSURE),
                    humidity=predicted_params.get(WeatherParameter.HUMIDITY),
                    precipitation=predicted_params.get(WeatherParameter.PRECIPITATION),
                    cloud_cover=predicted_params.get(WeatherParameter.CLOUD_COVER)
                )

                forecast_points.append(forecast_point)

            return ForecastSeries(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                forecast_made=datetime.utcnow(),
                forecast_points=forecast_points,
                source=self._get_source(),
                confidence=self._calculate_confidence(historical_data, hours)
            )

        except Exception as e:
            logger.error(f"Error generating forecast with model {self.name}: {e}")
            raise

    def _prepare_training_data(self, training_data: List[WeatherDataResponse]) -> pd.DataFrame:
        """Prepare training data."""
        # Convert to DataFrame
        records = []
        for data in training_data:
            records.append({
                "timestamp": data.timestamp,
                "parameter": data.parameter,
                "value": data.value,
                "quality": data.quality
            })

        df = pd.DataFrame(records)

        # Pivot to have parameters as columns
        df_pivot = df.pivot_table(
            index="timestamp",
            columns="parameter",
            values="value",
            aggfunc="mean"
        )

        # Sort by timestamp
        df_pivot = df_pivot.sort_index()

        # Add time-based features
        df_pivot["hour"] = df_pivot.index.hour
        df_pivot["day_of_year"] = df_pivot.index.dayofyear
        df_pivot["month"] = df_pivot.index.month
        df_pivot["day_of_week"] = df_pivot.index.dayofweek

        return df_pivot

    def _train_parameter_model(self, df: pd.DataFrame, parameter: WeatherParameter) -> Tuple[Any, Any]:
        """Train model for a specific parameter."""
        # Skip if insufficient data
        if parameter not in df.columns or df[parameter].count() < 20:
            return None, None

        # Prepare features and target
        feature_columns = [col for col in df.columns if col != parameter and pd.api.types.is_numeric_dtype(df[col])]
        X = df[feature_columns].fillna(method="ffill").fillna(method="bfill")
        y = df[parameter].fillna(method="ffill").fillna(method="bfill")

        # Remove rows with NaN
        valid_idx = ~(X.isnull().any(axis=1) | y.isnull())
        X = X[valid_idx]
        y = y[valid_idx]

        if len(X) < 10:
            return None, None

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train model
        model = LinearRegression()
        model.fit(X_scaled, y)

        return model, scaler

    def _prepare_prediction_features(
        self,
        historical_data: List[WeatherDataResponse],
        forecast_time: datetime,
        hour_ahead: int
    ) -> pd.DataFrame:
        """Prepare features for prediction."""
        # Create DataFrame from historical data
        records = {}
        for data in historical_data:
            if data.parameter not in records:
                records[data.parameter] = []
            records[data.parameter].append({
                "timestamp": data.timestamp,
                "value": data.value
            })

        # Calculate recent averages (last 6 hours)
        recent_data = [
            d for d in historical_data
            if (datetime.utcnow() - d.timestamp).total_seconds() / 3600 <= 6
        ]

        features = {}

        # Recent averages
        for parameter in WeatherParameter:
            param_data = [d.value for d in recent_data if d.parameter == parameter]
            if param_data:
                features[f"{parameter}_avg"] = np.mean(param_data)
                features[f"{parameter}_trend"] = self._calculate_trend(param_data)
            else:
                features[f"{parameter}_avg"] = 0
                features[f"{parameter}_trend"] = 0

        # Time-based features
        features["hour"] = forecast_time.hour
        features["day_of_year"] = forecast_time.dayofyear
        features["month"] = forecast_time.month
        features["day_of_week"] = forecast_time.dayofweek
        features["hour_ahead"] = hour_ahead

        return pd.DataFrame([features])

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend in values."""
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values))
        y = np.array(values)
        return np.polyfit(x, y, 1)[0]  # Slope of linear fit

    def _predict_parameter(self, parameter: WeatherParameter, features: pd.DataFrame) -> float:
        """Predict a specific parameter."""
        if parameter not in self.models or self.models[parameter] is None:
            return 0.0

        model = self.models[parameter]
        scaler = self.scalers[parameter]

        # Scale features
        features_scaled = scaler.transform(features)

        # Make prediction
        prediction = model.predict(features_scaled)[0]

        # Apply physical constraints
        return self._apply_physical_constraints(parameter, prediction)

    def _apply_physical_constraints(self, parameter: WeatherParameter, value: float) -> float:
        """Apply physical constraints to predictions."""
        constraints = {
            WeatherParameter.TEMPERATURE: (-50, 60),
            WeatherParameter.HUMIDITY: (0, 100),
            WeatherParameter.WIND_SPEED: (0, 50),
            WeatherParameter.WIND_DIRECTION: (0, 360),
            WeatherParameter.PRESSURE: (800, 1100),
            WeatherParameter.CLOUD_COVER: (0, 100),
        }

        min_val, max_val = constraints.get(parameter, (float('-inf'), float('inf')))
        return max(min_val, min(max_val, value))

    def _calculate_confidence(self, historical_data: List[WeatherDataResponse], hours: int) -> float:
        """Calculate forecast confidence."""
        # Base confidence
        confidence = 0.9

        # Reduce confidence with forecast horizon
        confidence -= (hours / 72) * 0.3  # Max 30% reduction for 72-hour forecasts

        # Adjust based on data quality and quantity
        recent_data = [
            d for d in historical_data
            if (datetime.utcnow() - d.timestamp).total_seconds() / 3600 <= 24
        ]

        if len(recent_data) < 10:
            confidence -= 0.2
        elif len(recent_data) < 50:
            confidence -= 0.1

        # Adjust based on data quality
        good_quality_ratio = sum(1 for d in recent_data if d.quality == "good") / len(recent_data) if recent_data else 0
        confidence *= good_quality_ratio

        return max(0.1, min(0.95, confidence))

    def _get_source(self) -> WeatherDataSource:
        """Get the data source for this model."""
        return WeatherDataSource.MANUAL  # Override in specific implementations


class PersistenceModel(ForecastModel):
    """Persistence forecast model (naive approach)."""

    def __init__(self):
        super().__init__("persistence", list(WeatherParameter))
        self.is_trained = True  # Persistence model doesn't need training

    async def predict(
        self,
        station_id: str,
        wind_farm_id: str,
        start_time: datetime,
        hours: int,
        historical_data: List[WeatherDataResponse]
    ) -> ForecastSeries:
        """Generate persistence forecast."""
        forecast_points = []

        # Get latest values for each parameter
        latest_values = {}
        for data in sorted(historical_data, key=lambda x: x.timestamp, reverse=True):
            if data.parameter not in latest_values:
                latest_values[data.parameter] = data.value

        for hour in range(1, hours + 1):
            forecast_time = start_time + timedelta(hours=hour)

            forecast_point = ForecastPoint(
                time=forecast_time,
                temperature=latest_values.get(WeatherParameter.TEMPERATURE),
                wind_speed=latest_values.get(WeatherParameter.WIND_SPEED),
                wind_direction=latest_values.get(WeatherParameter.WIND_DIRECTION),
                pressure=latest_values.get(WeatherParameter.PRESSURE),
                humidity=latest_values.get(WeatherParameter.HUMIDITY),
                precipitation=latest_values.get(WeatherParameter.PRECIPITATION),
                cloud_cover=latest_values.get(WeatherParameter.CLOUD_COVER)
            )

            forecast_points.append(forecast_point)

        return ForecastSeries(
            station_id=station_id,
            wind_farm_id=wind_farm_id,
            forecast_made=datetime.utcnow(),
            forecast_points=forecast_points,
            source=WeatherDataSource.MANUAL,
            confidence=0.6 - (hours / 72) * 0.4  # Confidence decreases with time
        )

    def _get_source(self) -> WeatherDataSource:
        return WeatherDataSource.MANUAL


class ClimatologyModel(ForecastModel):
    """Climatology-based forecast model."""

    def __init__(self):
        super().__init__("climatology", list(WeatherParameter))
        self.climatology_data = {}

    async def train(self, training_data: List[WeatherDataResponse]) -> bool:
        """Train climatology model."""
        try:
            # Group data by month and hour
            climatology = defaultdict(list)

            for data in training_data:
                month = data.timestamp.month
                hour = data.timestamp.hour
                key = (month, hour, data.parameter)
                climatology[key].append(data.value)

            # Calculate averages
            for key, values in climatology.items():
                if len(values) >= 3:  # Need at least 3 data points
                    self.climatology_data[key] = {
                        "mean": np.mean(values),
                        "std": np.std(values),
                        "count": len(values)
                    }

            self.is_trained = True
            logger.info("Climatology model trained successfully")
            return True

        except Exception as e:
            logger.error(f"Error training climatology model: {e}")
            return False

    async def predict(
        self,
        station_id: str,
        wind_farm_id: str,
        start_time: datetime,
        hours: int,
        historical_data: List[WeatherDataResponse]
    ) -> ForecastSeries:
        """Generate climatology-based forecast."""
        forecast_points = []

        for hour in range(1, hours + 1):
            forecast_time = start_time + timedelta(hours=hour)
            month = forecast_time.month
            hour_of_day = forecast_time.hour

            predicted_params = {}

            for parameter in self.parameters:
                key = (month, hour_of_day, parameter)
                if key in self.climatology_data:
                    climatology = self.climatology_data[key]
                    # Add some random variation based on historical std
                    predicted_value = climatology["mean"] + np.random.normal(0, climatology["std"] * 0.3)
                    predicted_params[parameter] = predicted_value

            forecast_point = ForecastPoint(
                time=forecast_time,
                temperature=predicted_params.get(WeatherParameter.TEMPERATURE),
                wind_speed=predicted_params.get(WeatherParameter.WIND_SPEED),
                wind_direction=predicted_params.get(WeatherParameter.WIND_DIRECTION),
                pressure=predicted_params.get(WeatherParameter.PRESSURE),
                humidity=predicted_params.get(WeatherParameter.HUMIDITY),
                precipitation=predicted_params.get(WeatherParameter.PRECIPITATION),
                cloud_cover=predicted_params.get(WeatherParameter.CLOUD_COVER)
            )

            forecast_points.append(forecast_point)

        return ForecastSeries(
            station_id=station_id,
            wind_farm_id=wind_farm_id,
            forecast_made=datetime.utcnow(),
            forecast_points=forecast_points,
            source=WeatherDataSource.MANUAL,
            confidence=0.7 - (hours / 72) * 0.2
        )

    def _get_source(self) -> WeatherDataSource:
        return WeatherDataSource.MANUAL


class ForecastService:
    """Weather forecasting service."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.models = {
            "persistence": PersistenceModel(),
            "climatology": ClimatologyModel(),
            "ml_regression": ForecastModel("ml_regression", list(WeatherParameter)),
        }
        self.model_weights = {
            "persistence": 0.4,      # Good for short-term
            "climatology": 0.3,      # Good for long-term
            "ml_regression": 0.3,    # Good overall
        }

    async def generate_forecast(
        self,
        station_id: str,
        wind_farm_id: str,
        hours: int = 24,
        include_ensemble: bool = True
    ) -> Dict[str, Any]:
        """Generate weather forecast for a station."""
        try:
            self.logger.info(f"Generating forecast for station {station_id}, hours: {hours}")

            # Get historical data for training and prediction
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=14)  # Use last 14 days

            historical_data = await weather_data_crud.get_time_series(
                None, station_id, None, start_time, end_time
            )

            if len(historical_data) < 50:
                self.logger.warning(f"Insufficient historical data for forecast: {len(historical_data)} records")
                return self._generate_naive_forecast(station_id, wind_farm_id, hours)

            # Train models if needed
            await self._train_models(historical_data)

            # Generate forecasts from different models
            forecasts = {}

            for model_name, model in self.models.items():
                try:
                    forecast = await model.predict(
                        station_id, wind_farm_id, datetime.utcnow(), hours, historical_data
                    )
                    forecasts[model_name] = forecast
                except Exception as e:
                    self.logger.error(f"Error generating forecast with {model_name}: {e}")

            # Generate ensemble forecast
            if include_ensemble and len(forecasts) > 1:
                ensemble_forecast = self._generate_ensemble_forecast(forecasts)
                forecasts["ensemble"] = ensemble_forecast

            # Store forecasts in database
            await self._store_forecasts(forecasts)

            return {
                "station_id": station_id,
                "wind_farm_id": wind_farm_id,
                "forecast_time": datetime.utcnow().isoformat(),
                "forecast_horizon": hours,
                "forecasts": forecasts,
                "model_info": {
                    "available_models": list(self.models.keys()),
                    "model_weights": self.model_weights,
                    "ensemble_enabled": include_ensemble
                }
            }

        except Exception as e:
            self.logger.error(f"Error generating forecast: {e}")
            raise

    async def _train_models(self, training_data: List[WeatherDataResponse]):
        """Train all forecast models."""
        for model_name, model in self.models.items():
            if not model.is_trained:
                try:
                    success = await model.train(training_data)
                    if success:
                        self.logger.info(f"Model {model_name} trained successfully")
                    else:
                        self.logger.warning(f"Failed to train model {model_name}")
                except Exception as e:
                    self.logger.error(f"Error training model {model_name}: {e}")

    def _generate_ensemble_forecast(self, forecasts: Dict[str, ForecastSeries]) -> ForecastSeries:
        """Generate ensemble forecast by combining multiple models."""
        if not forecasts:
            raise ValueError("No forecasts available for ensemble")

        # Use the first forecast as template
        template = next(iter(forecasts.values()))
        ensemble_points = []

        # Combine forecasts point by point
        for i, template_point in enumerate(template.forecast_points):
            ensemble_point = ForecastPoint(
                time=template_point.time,
                temperature=self._weighted_average(forecasts, i, "temperature"),
                wind_speed=self._weighted_average(forecasts, i, "wind_speed"),
                wind_direction=self._circular_average(forecasts, i, "wind_direction"),
                pressure=self._weighted_average(forecasts, i, "pressure"),
                humidity=self._weighted_average(forecasts, i, "humidity"),
                precipitation=self._weighted_average(forecasts, i, "precipitation"),
                cloud_cover=self._weighted_average(forecasts, i, "cloud_cover")
            )
            ensemble_points.append(ensemble_point)

        return ForecastSeries(
            station_id=template.station_id,
            wind_farm_id=template.wind_farm_id,
            forecast_made=datetime.utcnow(),
            forecast_points=ensemble_points,
            source=WeatherDataSource.MANUAL,
            confidence=self._calculate_ensemble_confidence(forecasts)
        )

    def _weighted_average(self, forecasts: Dict[str, ForecastSeries], point_index: int, attribute: str) -> Optional[float]:
        """Calculate weighted average of a forecast attribute."""
        values = []
        weights = []

        for model_name, forecast in forecasts.items():
            if hasattr(forecast.forecast_points[point_index], attribute):
                value = getattr(forecast.forecast_points[point_index], attribute)
                if value is not None:
                    values.append(value)
                    weights.append(self.model_weights.get(model_name, 1.0))

        if not values:
            return None

        return np.average(values, weights=weights)

    def _circular_average(self, forecasts: Dict[str, ForecastSeries], point_index: int, attribute: str) -> Optional[float]:
        """Calculate circular average for directional data."""
        values = []
        weights = []

        for model_name, forecast in forecasts.items():
            if hasattr(forecast.forecast_points[point_index], attribute):
                value = getattr(forecast.forecast_points[point_index], attribute)
                if value is not None:
                    values.append(value)
                    weights.append(self.model_weights.get(model_name, 1.0))

        if not values:
            return None

        # Convert to radians and calculate vector average
        angles_rad = np.radians(values)
        sin_sum = np.sum(np.sin(angles_rad) * weights)
        cos_sum = np.sum(np.cos(angles_rad) * weights)

        avg_angle_rad = np.arctan2(sin_sum, cos_sum)
        return np.degrees(avg_angle_rad) % 360

    def _calculate_ensemble_confidence(self, forecasts: Dict[str, ForecastSeries]) -> float:
        """Calculate ensemble forecast confidence."""
        if not forecasts:
            return 0.5

        # Base confidence from individual model confidences
        individual_confidences = [f.confidence for f in forecasts.values()]
        base_confidence = np.mean(individual_confidences)

        # Adjust based on model agreement
        agreement_factor = self._calculate_model_agreement(forecasts)

        return base_confidence * agreement_factor

    def _calculate_model_agreement(self, forecasts: Dict[str, ForecastSeries]) -> float:
        """Calculate agreement between different forecast models."""
        if len(forecasts) < 2:
            return 1.0

        # Calculate coefficient of variation for key parameters
        agreement_scores = []

        for i, point in enumerate(next(iter(forecasts.values())).forecast_points):
            # Temperature agreement
            temps = []
            for forecast in forecasts.values():
                if i < len(forecast.forecast_points):
                    temp = forecast.forecast_points[i].temperature
                    if temp is not None:
                        temps.append(temp)

            if len(temps) > 1:
                cv = np.std(temps) / np.mean(temps) if np.mean(temps) != 0 else 0
                agreement_scores.append(max(0, 1 - cv))

            # Wind speed agreement
            wind_speeds = []
            for forecast in forecasts.values():
                if i < len(forecast.forecast_points):
                    wind = forecast.forecast_points[i].wind_speed
                    if wind is not None:
                        wind_speeds.append(wind)

            if len(wind_speeds) > 1:
                cv = np.std(wind_speeds) / np.mean(wind_speeds) if np.mean(wind_speeds) != 0 else 0
                agreement_scores.append(max(0, 1 - cv))

        return np.mean(agreement_scores) if agreement_scores else 1.0

    def _generate_naive_forecast(self, station_id: str, wind_farm_id: str, hours: int) -> Dict[str, Any]:
        """Generate naive forecast when insufficient data."""
        forecast_points = []

        for hour in range(1, hours + 1):
            forecast_time = datetime.utcnow() + timedelta(hours=hour)

            # Seasonal averages (simplified)
            month = forecast_time.month
            if month in [12, 1, 2]:  # Winter
                temp, wind = 5, 8
            elif month in [3, 4, 5]:  # Spring
                temp, wind = 15, 6
            elif month in [6, 7, 8]:  # Summer
                temp, wind = 25, 5
            else:  # Fall
                temp, wind = 15, 7

            forecast_point = ForecastPoint(
                time=forecast_time,
                temperature=temp,
                wind_speed=wind,
                wind_direction=180,  # South
                pressure=1013,
                humidity=60,
                precipitation=0,
                cloud_cover=30
            )

            forecast_points.append(forecast_point)

        naive_forecast = ForecastSeries(
            station_id=station_id,
            wind_farm_id=wind_farm_id,
            forecast_made=datetime.utcnow(),
            forecast_points=forecast_points,
            source=WeatherDataSource.MANUAL,
            confidence=0.3
        )

        return {
            "station_id": station_id,
            "wind_farm_id": wind_farm_id,
            "forecast_time": datetime.utcnow().isoformat(),
            "forecast_horizon": hours,
            "forecasts": {"naive": naive_forecast},
            "model_info": {
                "available_models": ["naive"],
                "note": "Insufficient historical data for advanced forecasting"
            }
        }

    async def _store_forecasts(self, forecasts: Dict[str, ForecastSeries]):
        """Store forecasts in database."""
        try:
            for model_name, forecast in forecasts.items():
                if model_name == "ensemble":  # Skip ensemble storage for now
                    continue

                for point in forecast.forecast_points:
                    forecast_data = WeatherForecastCreate(
                        station_id=forecast.station_id,
                        wind_farm_id=forecast.wind_farm_id,
                        forecast_time=point.time,
                        forecast_hours=int((point.time - datetime.utcnow()).total_seconds() / 3600),
                        parameters={
                            "temperature": point.temperature,
                            "wind_speed": point.wind_speed,
                            "wind_direction": point.wind_direction,
                            "pressure": point.pressure,
                            "humidity": point.humidity,
                            "precipitation": point.precipitation,
                            "cloud_cover": point.cloud_cover
                        },
                        source=forecast.source,
                        model_version=model_name
                    )

                    # Store in database (would need db session)
                    # await weather_forecast_crud.create(db_session, forecast_data.dict())

        except Exception as e:
            logger.error(f"Error storing forecasts: {e}")

    async def evaluate_forecast_accuracy(
        self,
        station_id: str,
        forecast_hours: int,
        period_days: int = 7
    ) -> Dict[str, Any]:
        """Evaluate forecast accuracy against actual observations."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=period_days)

            # Get forecasts for the period
            forecasts = await weather_forecast_crud.get_forecast_series(
                None, station_id, start_time, end_time
            )

            # Get actual observations for the same period
            observations = {}
            for parameter in WeatherParameter:
                obs_data = await weather_data_crud.get_time_series(
                    None, station_id, parameter, start_time, end_time
                )
                observations[parameter] = obs_data

            # Calculate accuracy metrics
            accuracy_metrics = {}

            for parameter in WeatherParameter:
                if parameter in observations and observations[parameter]:
                    metrics = self._calculate_accuracy_metrics(
                        forecasts, observations[parameter], parameter, forecast_hours
                    )
                    accuracy_metrics[parameter] = metrics

            return {
                "station_id": station_id,
                "forecast_hours": forecast_hours,
                "evaluation_period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "days": period_days
                },
                "accuracy_metrics": accuracy_metrics,
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error evaluating forecast accuracy: {e}")
            raise

    def _calculate_accuracy_metrics(
        self,
        forecasts: List[WeatherForecastResponse],
        observations: List[WeatherDataResponse],
        parameter: WeatherParameter,
        forecast_hours: int
    ) -> Dict[str, Any]:
        """Calculate accuracy metrics for a specific parameter."""
        # Match forecasts with observations
        pairs = []

        for forecast in forecasts:
            if forecast.forecast_hours != forecast_hours:
                continue

            forecast_value = forecast.parameters.get(parameter)
            if forecast_value is None:
                continue

            # Find corresponding observation
            for obs in observations:
                if abs((forecast.forecast_time - obs.timestamp).total_seconds()) < 1800:  # Within 30 minutes
                    pairs.append((forecast_value, obs.value))
                    break

        if len(pairs) < 5:
            return {"error": "Insufficient data pairs for accuracy calculation"}

        forecast_values = [p[0] for p in pairs]
        observed_values = [p[1] for p in pairs]

        # Calculate metrics
        errors = np.array(forecast_values) - np.array(observed_values)

        mae = np.mean(np.abs(errors))
        rmse = np.sqrt(np.mean(errors ** 2))
        mape = np.mean(np.abs(errors / np.array(observed_values))) * 100
        correlation = np.corrcoef(forecast_values, observed_values)[0, 1]

        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "mape": float(mape),
            "correlation": float(correlation),
            "sample_size": len(pairs),
            "bias": float(np.mean(errors))
        }

    async def get_forecast_summary(
        self,
        wind_farm_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get forecast summary for a wind farm."""
        try:
            # This would aggregate forecasts across all stations in the wind farm
            # For now, return a basic summary
            return {
                "wind_farm_id": wind_farm_id,
                "forecast_horizon": hours,
                "forecast_time": datetime.utcnow().isoformat(),
                "summary": {
                    "temperature_range": {"min": -10, "max": 35},
                    "wind_speed_range": {"min": 0, "max": 25},
                    "precipitation_probability": 0.2,
                    "confidence_level": 0.75
                }
            }

        except Exception as e:
            self.logger.error(f"Error getting forecast summary: {e}")
            raise