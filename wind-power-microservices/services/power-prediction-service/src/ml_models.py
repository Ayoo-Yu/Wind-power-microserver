"""
Machine Learning Models for Power Prediction Service
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import xgboost as xgb
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import joblib
import logging
from datetime import datetime, timedelta
import os

from .config import MODEL_HYPERPARAMETERS, get_settings
from .exceptions import ModelTrainingException, FeatureEngineeringException

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseMLModel:
    """Base class for ML models."""

    def __init__(self, model_name: str, model_type: str):
        self.model_name = model_name
        self.model_type = model_type
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.is_trained = False
        self.training_date = None
        self.performance_metrics = {}

    def preprocess_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Preprocess features for training/prediction."""
        # Handle missing values
        X = X.fillna(X.mean())

        # Remove infinite values
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(X.mean())

        return X

    def scale_features(self, X: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """Scale features using StandardScaler."""
        if self.scaler is None:
            self.scaler = StandardScaler()

        if fit:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = self.scaler.transform(X)

        return pd.DataFrame(X_scaled, columns=X.columns, index=X.index)

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, float]:
        """Train the model."""
        raise NotImplementedError("Subclasses must implement train method")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        raise NotImplementedError("Subclasses must implement predict method")

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluate model performance."""
        if not self.is_trained:
            raise ModelTrainingException("Model is not trained")

        predictions = self.predict(X)

        metrics = {
            'mae': mean_absolute_error(y, predictions),
            'mse': mean_squared_error(y, predictions),
            'rmse': np.sqrt(mean_squared_error(y, predictions)),
            'r2': r2_score(y, predictions),
            'mape': np.mean(np.abs((y - predictions) / y)) * 100 if np.all(y != 0) else float('inf')
        }

        return metrics

    def save_model(self, file_path: str):
        """Save trained model to file."""
        if not self.is_trained:
            raise ModelTrainingException("Cannot save untrained model")

        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained,
            'training_date': self.training_date,
            'performance_metrics': self.performance_metrics,
            'model_name': self.model_name,
            'model_type': self.model_type
        }

        joblib.dump(model_data, file_path)
        logger.info(f"Model saved to {file_path}")

    def load_model(self, file_path: str):
        """Load trained model from file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Model file not found: {file_path}")

        model_data = joblib.load(file_path)

        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.is_trained = model_data['is_trained']
        self.training_date = model_data['training_date']
        self.performance_metrics = model_data['performance_metrics']

        logger.info(f"Model loaded from {file_path}")


class LSTMModel(BaseMLModel):
    """LSTM model for time series power prediction."""

    def __init__(self, model_name: str, lookback_window: int = 24):
        super().__init__(model_name, "lstm")
        self.lookback_window = lookback_window
        self.model = None
        self.scaler = MinMaxScaler()

    def create_sequences(self, X: pd.DataFrame, y: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM training."""
        sequences = []
        targets = []

        for i in range(len(X) - self.lookback_window):
            sequences.append(X.iloc[i:(i + self.lookback_window)].values)
            targets.append(y.iloc[i + self.lookback_window])

        return np.array(sequences), np.array(targets)

    def build_model(self, input_shape: Tuple[int, int]) -> keras.Model:
        """Build LSTM model architecture."""
        model = keras.Sequential([
            layers.LSTM(
                MODEL_HYPERPARAMETERS['lstm']['units'][0],
                return_sequences=True,
                input_shape=input_shape,
                dropout=MODEL_HYPERPARAMETERS['lstm']['dropout'],
                recurrent_dropout=MODEL_HYPERPARAMETERS['lstm']['recurrent_dropout']
            ),
            layers.LSTM(
                MODEL_HYPERPARAMETERS['lstm']['units'][1],
                return_sequences=True,
                dropout=MODEL_HYPERPARAMETERS['lstm']['dropout'],
                recurrent_dropout=MODEL_HYPERPARAMETERS['lstm']['recurrent_dropout']
            ),
            layers.LSTM(
                MODEL_HYPERPARAMETERS['lstm']['units'][2],
                dropout=MODEL_HYPERPARAMETERS['lstm']['dropout'],
                recurrent_dropout=MODEL_HYPERPARAMETERS['lstm']['recurrent_dropout']
            ),
            layers.Dense(32, activation='relu'),
            layers.Dense(1, activation='linear')
        ])

        model.compile(
            optimizer=MODEL_HYPERPARAMETERS['lstm']['optimizer'],
            loss=MODEL_HYPERPARAMETERS['lstm']['loss'],
            metrics=['mae']
        )

        return model

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, float]:
        """Train LSTM model."""
        try:
            logger.info(f"Training LSTM model: {self.model_name}")

            # Preprocess features
            X_processed = self.preprocess_features(X)
            self.feature_names = X_processed.columns.tolist()

            # Scale features
            X_scaled = self.scale_features(X_processed, fit=True)
            y_scaled = self.scaler.fit_transform(y.values.reshape(-1, 1)).flatten()

            # Create sequences
            X_sequences, y_sequences = self.create_sequences(
                pd.DataFrame(X_scaled, columns=X_processed.columns),
                pd.Series(y_scaled)
            )

            # Build model
            self.model = self.build_model((X_sequences.shape[1], X_sequences.shape[2]))

            # Train model
            history = self.model.fit(
                X_sequences, y_sequences,
                epochs=kwargs.get('epochs', MODEL_HYPERPARAMETERS['lstm']['epochs']),
                batch_size=kwargs.get('batch_size', MODEL_HYPERPARAMETERS['lstm']['batch_size']),
                validation_split=MODEL_HYPERPARAMETERS['lstm']['validation_split'],
                verbose=1
            )

            self.is_trained = True
            self.training_date = datetime.utcnow()

            # Calculate training metrics
            self.performance_metrics = {
                'training_mae': float(history.history['mae'][-1]),
                'training_loss': float(history.history['loss'][-1]),
                'validation_mae': float(history.history['val_mae'][-1]),
                'validation_loss': float(history.history['val_loss'][-1])
            }

            logger.info(f"LSTM model training completed: {self.performance_metrics}")
            return self.performance_metrics

        except Exception as e:
            logger.error(f"LSTM model training failed: {e}")
            raise ModelTrainingException(f"LSTM training failed: {str(e)}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using LSTM model."""
        if not self.is_trained:
            raise ModelTrainingException("LSTM model is not trained")

        # Preprocess and scale features
        X_processed = self.preprocess_features(X)
        X_scaled = self.scale_features(X_processed)

        # Create sequences for prediction
        X_sequences, _ = self.create_sequences(
            pd.DataFrame(X_scaled, columns=self.feature_names),
            pd.Series(np.zeros(len(X_scaled)))  # Dummy target
        )

        # Make predictions
        predictions_scaled = self.model.predict(X_sequences)

        # Inverse transform predictions
        predictions = self.scaler.inverse_transform(predictions_scaled).flatten()

        return predictions


class XGBoostModel(BaseMLModel):
    """XGBoost model for power prediction."""

    def __init__(self, model_name: str):
        super().__init__(model_name, "xgboost")

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, float]:
        """Train XGBoost model."""
        try:
            logger.info(f"Training XGBoost model: {self.model_name}")

            # Preprocess features
            X_processed = self.preprocess_features(X)
            self.feature_names = X_processed.columns.tolist()

            # Create and train model
            self.model = xgb.XGBRegressor(
                n_estimators=kwargs.get('n_estimators', MODEL_HYPERPARAMETERS['xgboost']['n_estimators']),
                max_depth=kwargs.get('max_depth', MODEL_HYPERPARAMETERS['xgboost']['max_depth']),
                learning_rate=kwargs.get('learning_rate', MODEL_HYPERPARAMETERS['xgboost']['learning_rate']),
                subsample=kwargs.get('subsample', MODEL_HYPERPARAMETERS['xgboost']['subsample']),
                colsample_bytree=kwargs.get('colsample_bytree', MODEL_HYPERPARAMETERS['xgboost']['colsample_bytree']),
                random_state=MODEL_HYPERPARAMETERS['xgboost']['random_state']
            )

            self.model.fit(X_processed, y)

            self.is_trained = True
            self.training_date = datetime.utcnow()

            # Calculate training metrics
            predictions = self.model.predict(X_processed)
            self.performance_metrics = {
                'training_mae': float(mean_absolute_error(y, predictions)),
                'training_mse': float(mean_squared_error(y, predictions)),
                'training_rmse': float(np.sqrt(mean_squared_error(y, predictions))),
                'training_r2': float(r2_score(y, predictions))
            }

            logger.info(f"XGBoost model training completed: {self.performance_metrics}")
            return self.performance_metrics

        except Exception as e:
            logger.error(f"XGBoost model training failed: {e}")
            raise ModelTrainingException(f"XGBoost training failed: {str(e)}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using XGBoost model."""
        if not self.is_trained:
            raise ModelTrainingException("XGBoost model is not trained")

        X_processed = self.preprocess_features(X)
        predictions = self.model.predict(X_processed)
        return predictions


class RandomForestModel(BaseMLModel):
    """Random Forest model for power prediction."""

    def __init__(self, model_name: str):
        super().__init__(model_name, "random_forest")

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, float]:
        """Train Random Forest model."""
        try:
            logger.info(f"Training Random Forest model: {self.model_name}")

            # Preprocess features
            X_processed = self.preprocess_features(X)
            self.feature_names = X_processed.columns.tolist()

            # Create and train model
            self.model = RandomForestRegressor(
                n_estimators=kwargs.get('n_estimators', MODEL_HYPERPARAMETERS['random_forest']['n_estimators']),
                max_depth=kwargs.get('max_depth', MODEL_HYPERPARAMETERS['random_forest']['max_depth']),
                min_samples_split=kwargs.get('min_samples_split', MODEL_HYPERPARAMETERS['random_forest']['min_samples_split']),
                min_samples_leaf=kwargs.get('min_samples_leaf', MODEL_HYPERPARAMETERS['random_forest']['min_samples_leaf']),
                random_state=MODEL_HYPERPARAMETERS['random_forest']['random_state']
            )

            self.model.fit(X_processed, y)

            self.is_trained = True
            self.training_date = datetime.utcnow()

            # Calculate training metrics
            predictions = self.model.predict(X_processed)
            self.performance_metrics = {
                'training_mae': float(mean_absolute_error(y, predictions)),
                'training_mse': float(mean_squared_error(y, predictions)),
                'training_rmse': float(np.sqrt(mean_squared_error(y, predictions))),
                'training_r2': float(r2_score(y, predictions))
            }

            # Feature importance
            if hasattr(self.model, 'feature_importances_'):
                self.performance_metrics['feature_importance'] = dict(
                    zip(self.feature_names, self.model.feature_importances_.tolist())
                )

            logger.info(f"Random Forest model training completed: {self.performance_metrics}")
            return self.performance_metrics

        except Exception as e:
            logger.error(f"Random Forest model training failed: {e}")
            raise ModelTrainingException(f"Random Forest training failed: {str(e)}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using Random Forest model."""
        if not self.is_trained:
            raise ModelTrainingException("Random Forest model is not trained")

        X_processed = self.preprocess_features(X)
        predictions = self.model.predict(X_processed)
        return predictions


class PersistenceModel(BaseMLModel):
    """Persistence model (baseline) for power prediction."""

    def __init__(self, model_name: str):
        super().__init__(model_name, "persistence")
        self.last_value = None

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, float]:
        """Train persistence model (just store last value)."""
        try:
            logger.info(f"Training Persistence model: {self.model_name}")

            # Store the last value for persistence prediction
            self.last_value = y.iloc[-1]
            self.is_trained = True
            self.training_date = datetime.utcnow()

            # Calculate training metrics (predict current value for each point)
            predictions = y.shift(1).fillna(y.mean())
            self.performance_metrics = {
                'training_mae': float(mean_absolute_error(y, predictions)),
                'training_mse': float(mean_squared_error(y, predictions)),
                'training_rmse': float(np.sqrt(mean_squared_error(y, predictions))),
                'training_r2': float(r2_score(y, predictions))
            }

            logger.info(f"Persistence model training completed: {self.performance_metrics}")
            return self.performance_metrics

        except Exception as e:
            logger.error(f"Persistence model training failed: {e}")
            raise ModelTrainingException(f"Persistence training failed: {str(e)}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using persistence model."""
        if not self.is_trained:
            raise ModelTrainingException("Persistence model is not trained")

        # Return last known value for all predictions
        predictions = np.full(len(X), self.last_value)
        return predictions


class EnsembleModel(BaseMLModel):
    """Ensemble model that combines predictions from multiple models."""

    def __init__(self, model_name: str, models: Dict[str, BaseMLModel], weights: Optional[Dict[str, float]] = None):
        super().__init__(model_name, "ensemble")
        self.models = models
        self.weights = weights or {name: 1.0 / len(models) for name in models.keys()}
        self.is_trained = False
        self.training_date = None

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> Dict[str, float]:
        """Train all ensemble models."""
        try:
            logger.info(f"Training Ensemble model: {self.model_name}")

            ensemble_metrics = {}

            # Train each individual model
            for model_name, model in self.models.items():
                logger.info(f"Training {model_name} for ensemble...")
                metrics = model.train(X, y, **kwargs)
                ensemble_metrics[f"{model_name}_metrics"] = metrics

            self.is_trained = True
            self.training_date = datetime.utcnow()

            # Calculate ensemble training metrics
            predictions = self.predict(X)
            self.performance_metrics = {
                'training_mae': float(mean_absolute_error(y, predictions)),
                'training_mse': float(mean_squared_error(y, predictions)),
                'training_rmse': float(np.sqrt(mean_squared_error(y, predictions))),
                'training_r2': float(r2_score(y, predictions))
            }

            ensemble_metrics['ensemble_metrics'] = self.performance_metrics

            logger.info(f"Ensemble model training completed: {self.performance_metrics}")
            return ensemble_metrics

        except Exception as e:
            logger.error(f"Ensemble model training failed: {e}")
            raise ModelTrainingException(f"Ensemble training failed: {str(e)}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make ensemble predictions."""
        if not self.is_trained:
            raise ModelTrainingException("Ensemble model is not trained")

        # Get predictions from all models
        predictions = {}
        for model_name, model in self.models.items():
            predictions[model_name] = model.predict(X)

        # Calculate weighted average
        ensemble_predictions = np.zeros(len(X))
        total_weight = sum(self.weights.values())

        for model_name, pred in predictions.items():
            weight = self.weights[model_name] / total_weight
            ensemble_predictions += weight * pred

        return ensemble_predictions

    def predict_with_confidence(self, X: pd.DataFrame, confidence_level: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Make ensemble predictions with confidence intervals."""
        # Get predictions from all models
        predictions = []
        for model_name, model in self.models.items():
            pred = model.predict(X)
            predictions.append(pred)

        predictions_array = np.array(predictions)

        # Calculate mean prediction
        mean_predictions = np.mean(predictions_array, axis=0)

        # Calculate confidence intervals
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        lower_bound = np.percentile(predictions_array, lower_percentile, axis=0)
        upper_bound = np.percentile(predictions_array, upper_percentile, axis=0)

        return mean_predictions, lower_bound, upper_bound


# Model factory
class ModelFactory:
    """Factory for creating ML models."""

    @staticmethod
    def create_model(model_type: str, model_name: str, **kwargs) -> BaseMLModel:
        """Create ML model based on type."""
        if model_type == "lstm":
            return LSTMModel(model_name, **kwargs)
        elif model_type == "xgboost":
            return XGBoostModel(model_name)
        elif model_type == "random_forest":
            return RandomForestModel(model_name)
        elif model_type == "persistence":
            return PersistenceModel(model_name)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    @staticmethod
    def create_ensemble_model(model_name: str, models: Dict[str, BaseMLModel], weights: Optional[Dict[str, float]] = None) -> EnsembleModel:
        """Create ensemble model."""
        return EnsembleModel(model_name, models, weights)