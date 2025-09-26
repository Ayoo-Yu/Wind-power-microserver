"""
Feature engineering utilities for Power Prediction Service
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from scipy import stats
from sklearn.preprocessing import StandardScaler, MinMaxScaler

from .config import FEATURE_ENGINEERING_CONFIG, get_settings
from .exceptions import FeatureEngineeringException, DataQualityException

logger = logging.getLogger(__name__)
settings = get_settings()


class FeatureEngineer:
    """Feature engineering for power prediction models."""

    def __init__(self):
        self.config = FEATURE_ENGINEERING_CONFIG
        self.scalers = {}
        self.feature_stats = {}

    def create_time_features(self, df: pd.DataFrame, datetime_col: str = 'timestamp') -> pd.DataFrame:
        """Create time-based features."""
        try:
            df = df.copy()
            df['datetime'] = pd.to_datetime(df[datetime_col])

            # Basic time features
            df['hour'] = df['datetime'].dt.hour
            df['day_of_week'] = df['datetime'].dt.dayofweek
            df['month'] = df['datetime'].dt.month
            df['day_of_year'] = df['datetime'].dt.dayofyear
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

            # Cyclical encoding for time features
            df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
            df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
            df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
            df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
            df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
            df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

            # Season features
            df['season'] = df['month'].apply(self._get_season)
            df['is_winter'] = (df['season'] == 'winter').astype(int)
            df['is_spring'] = (df['season'] == 'spring').astype(int)
            df['is_summer'] = (df['season'] == 'summer').astype(int)
            df['is_autumn'] = (df['season'] == 'autumn').astype(int)

            return df

        except Exception as e:
            logger.error(f"Time feature creation failed: {e}")
            raise FeatureEngineeringException(f"Time feature creation failed: {str(e)}")

    def _get_season(self, month: int) -> str:
        """Get season from month."""
        if month in [12, 1, 2]:
            return 'winter'
        elif month in [3, 4, 5]:
            return 'spring'
        elif month in [6, 7, 8]:
            return 'summer'
        else:
            return 'autumn'

    def create_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create weather-based features."""
        try:
            df = df.copy()

            # Wind speed features
            if 'wind_speed' in df.columns:
                df = self._create_wind_speed_features(df)

            # Wind direction features
            if 'wind_direction' in df.columns:
                df = self._create_wind_direction_features(df)

            # Temperature features
            if 'temperature' in df.columns:
                df = self._create_temperature_features(df)

            # Pressure features
            if 'pressure' in df.columns:
                df = self._create_pressure_features(df)

            # Humidity features
            if 'humidity' in df.columns:
                df = self._create_humidity_features(df)

            # Combined weather features
            if all(col in df.columns for col in ['wind_speed', 'temperature', 'pressure']):
                df = self._create_combined_weather_features(df)

            return df

        except Exception as e:
            logger.error(f"Weather feature creation failed: {e}")
            raise FeatureEngineeringException(f"Weather feature creation failed: {str(e)}")

    def _create_wind_speed_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create wind speed related features."""
        # Basic statistics
        df['wind_speed_mean_3h'] = df['wind_speed'].rolling(window=3, min_periods=1).mean()
        df['wind_speed_mean_6h'] = df['wind_speed'].rolling(window=6, min_periods=1).mean()
        df['wind_speed_mean_12h'] = df['wind_speed'].rolling(window=12, min_periods=1).mean()
        df['wind_speed_mean_24h'] = df['wind_speed'].rolling(window=24, min_periods=1).mean()

        df['wind_speed_std_3h'] = df['wind_speed'].rolling(window=3, min_periods=1).std()
        df['wind_speed_std_6h'] = df['wind_speed'].rolling(window=6, min_periods=1).std()
        df['wind_speed_std_12h'] = df['wind_speed'].rolling(window=12, min_periods=1).std()

        # Rate of change
        df['wind_speed_diff'] = df['wind_speed'].diff()
        df['wind_speed_diff_3h'] = df['wind_speed'].diff(3)
        df['wind_speed_diff_6h'] = df['wind_speed'].diff(6)

        # Acceleration (second derivative)
        df['wind_speed_accel'] = df['wind_speed_diff'].diff()

        # Extremes
        df['wind_speed_min_3h'] = df['wind_speed'].rolling(window=3, min_periods=1).min()
        df['wind_speed_max_3h'] = df['wind_speed'].rolling(window=3, min_periods=1).max()
        df['wind_speed_range_3h'] = df['wind_speed_max_3h'] - df['wind_speed_min_3h']

        # Wind speed categories
        df['wind_speed_category'] = pd.cut(
            df['wind_speed'],
            bins=[0, 3, 7, 12, 18, 25, float('inf')],
            labels=['calm', 'light', 'moderate', 'fresh', 'strong', 'gale']
        )

        # One-hot encode wind speed categories
        wind_speed_dummies = pd.get_dummies(df['wind_speed_category'], prefix='wind_speed_cat')
        df = pd.concat([df, wind_speed_dummies], axis=1)

        return df

    def _create_wind_direction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create wind direction related features."""
        # Convert degrees to radians
        df['wind_direction_rad'] = np.radians(df['wind_direction'])

        # Cyclical encoding
        df['wind_direction_sin'] = np.sin(df['wind_direction_rad'])
        df['wind_direction_cos'] = np.cos(df['wind_direction_rad'])

        # Wind direction categories
        df['wind_direction_category'] = pd.cut(
            df['wind_direction'],
            bins=[0, 45, 90, 135, 180, 225, 270, 315, 360],
            labels=['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        )

        # One-hot encode wind direction categories
        wind_dir_dummies = pd.get_dummies(df['wind_direction_category'], prefix='wind_dir_cat')
        df = pd.concat([df, wind_dir_dummies], axis=1)

        # Rate of change
        df['wind_direction_diff'] = df['wind_direction'].diff()
        df['wind_direction_change_rate'] = df['wind_direction_diff'].abs()

        # Direction consistency (how consistent is the direction over time)
        df['wind_direction_consistency_3h'] = (
            df['wind_direction'].rolling(window=3, min_periods=1).std()
        )

        return df

    def _create_temperature_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create temperature related features."""
        # Rolling statistics
        df['temperature_mean_3h'] = df['temperature'].rolling(window=3, min_periods=1).mean()
        df['temperature_mean_6h'] = df['temperature'].rolling(window=6, min_periods=1).mean()
        df['temperature_mean_24h'] = df['temperature'].rolling(window=24, min_periods=1).mean()

        df['temperature_std_3h'] = df['temperature'].rolling(window=3, min_periods=1).std()
        df['temperature_std_6h'] = df['temperature'].rolling(window=6, min_periods=1).std()

        # Rate of change
        df['temperature_diff'] = df['temperature'].diff()
        df['temperature_diff_3h'] = df['temperature'].diff(3)
        df['temperature_gradient'] = df['temperature_diff'].rolling(window=3, min_periods=1).mean()

        # Temperature categories
        df['temperature_category'] = pd.cut(
            df['temperature'],
            bins=[-float('inf'), -10, 0, 10, 20, 30, float('inf')],
            labels=['very_cold', 'cold', 'cool', 'mild', 'warm', 'hot']
        )

        # One-hot encode temperature categories
        temp_dummies = pd.get_dummies(df['temperature_category'], prefix='temp_cat')
        df = pd.concat([df, temp_dummies], axis=1)

        return df

    def _create_pressure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create pressure related features."""
        # Rolling statistics
        df['pressure_mean_3h'] = df['pressure'].rolling(window=3, min_periods=1).mean()
        df['pressure_mean_6h'] = df['pressure'].rolling(window=6, min_periods=1).mean()
        df['pressure_mean_24h'] = df['pressure'].rolling(window=24, min_periods=1).mean()

        # Rate of change
        df['pressure_diff'] = df['pressure'].diff()
        df['pressure_diff_3h'] = df['pressure'].diff(3)
        df['pressure_change_rate'] = df['pressure_diff'].rolling(window=3, min_periods=1).mean()

        # Pressure tendency (rising, falling, steady)
        df['pressure_tendency'] = pd.cut(
            df['pressure_change_rate'],
            bins=[-float('inf'), -2, 2, float('inf')],
            labels=['falling', 'steady', 'rising']
        )

        # One-hot encode pressure tendency
        pressure_dummies = pd.get_dummies(df['pressure_tendency'], prefix='pressure_tend')
        df = pd.concat([df, pressure_dummies], axis=1)

        return df

    def _create_humidity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create humidity related features."""
        # Rolling statistics
        df['humidity_mean_3h'] = df['humidity'].rolling(window=3, min_periods=1).mean()
        df['humidity_mean_6h'] = df['humidity'].rolling(window=6, min_periods=1).mean()

        # Rate of change
        df['humidity_diff'] = df['humidity'].diff()
        df['humidity_gradient'] = df['humidity_diff'].rolling(window=3, min_periods=1).mean()

        # Humidity categories
        df['humidity_category'] = pd.cut(
            df['humidity'],
            bins=[0, 30, 60, 80, 100],
            labels=['low', 'moderate', 'high', 'very_high']
        )

        # One-hot encode humidity categories
        humidity_dummies = pd.get_dummies(df['humidity_category'], prefix='humidity_cat')
        df = pd.concat([df, humidity_dummies], axis=1)

        return df

    def _create_combined_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create combined weather features."""
        # Wind power density approximation
        df['wind_power_density'] = 0.5 * 1.225 * (df['wind_speed'] ** 3)  # Air density ~ 1.225 kg/m³

        # Wind chill index
        if 'temperature' in df.columns and 'wind_speed' in df.columns:
            df['wind_chill'] = (
                13.12 + 0.6215 * df['temperature'] - 11.37 * (df['wind_speed'] ** 0.16) +
                0.3965 * df['temperature'] * (df['wind_speed'] ** 0.16)
            )

        # Weather stability index (simplified)
        if all(col in df.columns for col in ['temperature', 'pressure', 'humidity']):
            df['weather_stability'] = (
                df['temperature'] * 0.4 + df['pressure'] * 0.3 + df['humidity'] * 0.3
            )

        return df

    def create_lag_features(self, df: pd.DataFrame, target_cols: List[str], lags: List[int]) -> pd.DataFrame:
        """Create lag features for specified columns."""
        df = df.copy()

        for col in target_cols:
            if col in df.columns:
                for lag in lags:
                    df[f'{col}_lag_{lag}h'] = df[col].shift(lag)

        return df

    def create_rolling_features(self, df: pd.DataFrame, target_cols: List[str], windows: List[int]) -> pd.DataFrame:
        """Create rolling window features for specified columns."""
        df = df.copy()

        for col in target_cols:
            if col in df.columns:
                for window in windows:
                    # Rolling statistics
                    df[f'{col}_rolling_mean_{window}h'] = df[col].rolling(window=window, min_periods=1).mean()
                    df[f'{col}_rolling_std_{window}h'] = df[col].rolling(window=window, min_periods=1).std()
                    df[f'{col}_rolling_min_{window}h'] = df[col].rolling(window=window, min_periods=1).min()
                    df[f'{col}_rolling_max_{window}h'] = df[col].rolling(window=window, min_periods=1).max()
                    df[f'{col}_rolling_range_{window}h'] = (
                        df[f'{col}_rolling_max_{window}h'] - df[f'{col}_rolling_min_{window}h']
                    )

        return df

    def create_power_specific_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create power-specific features."""
        if 'power_output' not in df.columns:
            return df

        df = df.copy()

        # Power rolling statistics
        power_windows = [3, 6, 12, 24]
        for window in power_windows:
            df[f'power_rolling_mean_{window}h'] = (
                df['power_output'].rolling(window=window, min_periods=1).mean()
            )
            df[f'power_rolling_std_{window}h'] = (
                df['power_output'].rolling(window=window, min_periods=1).std()
            )

        # Power rate of change
        df['power_diff'] = df['power_output'].diff()
        df['power_diff_3h'] = df['power_output'].diff(3)
        df['power_change_rate'] = df['power_diff'].rolling(window=3, min_periods=1).mean()

        # Power efficiency (assuming rated capacity is available)
        if 'rated_capacity' in df.columns and df['rated_capacity'].iloc[0] > 0:
            df['power_efficiency'] = df['power_output'] / df['rated_capacity']

        # Power categories
        if 'rated_capacity' in df.columns and df['rated_capacity'].iloc[0] > 0:
            df['power_output_percentage'] = (df['power_output'] / df['rated_capacity']) * 100
            df['power_category'] = pd.cut(
                df['power_output_percentage'],
                bins=[0, 25, 50, 75, 100],
                labels=['low', 'moderate', 'high', 'full']
            )

            # One-hot encode power categories
            power_dummies = pd.get_dummies(df['power_category'], prefix='power_cat')
            df = pd.concat([df, power_dummies], axis=1)

        return df

    def detect_and_handle_outliers(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Detect and handle outliers using statistical methods."""
        df = df.copy()

        for col in columns:
            if col in df.columns:
                # IQR method
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                # Z-score method
                z_scores = np.abs(stats.zscore(df[col].dropna()))
                z_score_threshold = 3

                # Identify outliers
                iqr_outliers = (df[col] < lower_bound) | (df[col] > upper_bound)
                z_score_outliers = np.abs(z_scores) > z_score_threshold

                # Handle outliers (cap them)
                df[f'{col}_outlier'] = iqr_outliers | z_score_outliers
                df[col] = df[col].clip(lower=lower_bound, upper=upper_bound)

        return df

    def create_features(self, df: pd.DataFrame, target_col: str = 'power_output') -> pd.DataFrame:
        """Create all features for power prediction."""
        try:
            logger.info("Creating features for power prediction...")
            initial_shape = df.shape

            # Time features
            df = self.create_time_features(df)

            # Weather features
            df = self.create_weather_features(df)

            # Power-specific features
            df = self.create_power_specific_features(df)

            # Lag features
            weather_cols = ['wind_speed', 'wind_direction', 'temperature', 'pressure', 'humidity']
            lag_cols = [col for col in weather_cols if col in df.columns]
            if target_col in df.columns:
                lag_cols.append(target_col)

            df = self.create_lag_features(df, lag_cols, self.config['lag_features'])

            # Rolling features
            df = self.create_rolling_features(df, lag_cols, self.config['rolling_features'])

            # Handle outliers for key columns
            outlier_cols = ['wind_speed', 'temperature', 'pressure', target_col]
            outlier_cols = [col for col in outlier_cols if col in df.columns]
            df = self.detect_and_handle_outliers(df, outlier_cols)

            logger.info(f"Feature creation completed: {initial_shape} -> {df.shape}")
            return df

        except Exception as e:
            logger.error(f"Feature creation failed: {e}")
            raise FeatureEngineeringException(f"Feature creation failed: {str(e)}")

    def select_features(self, df: pd.DataFrame, target_col: str = 'power_output',
                       correlation_threshold: float = 0.1) -> List[str]:
        """Select most relevant features based on correlation and importance."""
        try:
            # Remove non-numeric columns
            numeric_df = df.select_dtypes(include=[np.number])

            if target_col not in numeric_df.columns:
                logger.warning(f"Target column {target_col} not found in numeric columns")
                return numeric_df.columns.tolist()

            # Calculate correlation with target
            correlations = numeric_df.corr()[target_col].abs().sort_values(ascending=False)

            # Select features with correlation above threshold
            selected_features = correlations[
                (correlations > correlation_threshold) &
                (correlations.index != target_col)
            ].index.tolist()

            logger.info(f"Selected {len(selected_features)} features based on correlation")
            return selected_features

        except Exception as e:
            logger.error(f"Feature selection failed: {e}")
            raise FeatureEngineeringException(f"Feature selection failed: {str(e)}")

    def get_feature_importance(self, model: Any, feature_names: List[str]) -> Dict[str, float]:
        """Get feature importance from trained model."""
        try:
            importance = {}

            if hasattr(model, 'feature_importances_'):
                # Tree-based models
                importances = model.feature_importances_
                importance = dict(zip(feature_names, importances))
            elif hasattr(model, 'coef_'):
                # Linear models
                coefs = np.abs(model.coef_)
                importance = dict(zip(feature_names, coefs))

            # Sort by importance
            importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

            return importance

        except Exception as e:
            logger.error(f"Feature importance calculation failed: {e}")
            return {}


class DataPreprocessor:
    """Data preprocessing utilities."""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()

    def preprocess_power_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess power data for model training."""
        try:
            logger.info("Preprocessing power data...")
            initial_rows = len(df)

            # Remove duplicates
            df = df.drop_duplicates(subset=['timestamp', 'wind_farm_id', 'turbine_id'])

            # Sort by timestamp
            df = df.sort_values('timestamp')

            # Handle missing values
            # Forward fill for weather data
            weather_cols = ['wind_speed', 'wind_direction', 'temperature', 'pressure', 'humidity']
            for col in weather_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(method='ffill').fillna(method='bfill')

            # Interpolate power output
            if 'power_output' in df.columns:
                df['power_output'] = df['power_output'].interpolate(method='linear')

            # Remove rows with too many missing values
            threshold = 0.5  # 50% missing values threshold
            df = df.dropna(thresh=len(df.columns) * (1 - threshold))

            # Data quality checks
            if 'power_output' in df.columns:
                # Remove negative power values
                df = df[df['power_output'] >= 0]

                # Remove unrealistic power values (assuming max capacity)
                if 'rated_capacity' in df.columns:
                    max_power = df['rated_capacity'].max() * 1.2  # 20% buffer
                    df = df[df['power_output'] <= max_power]

            # Wind speed validation
            if 'wind_speed' in df.columns:
                df = df[df['wind_speed'] >= 0]  # Wind speed cannot be negative
                df = df[df['wind_speed'] <= 50]  # Reasonable upper limit

            # Temperature validation
            if 'temperature' in df.columns:
                df = df[df['temperature'] >= -50]  # Reasonable lower limit
                df = df[df['temperature'] <= 60]   # Reasonable upper limit

            logger.info(f"Preprocessing completed: {initial_rows} -> {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Data preprocessing failed: {e}")
            raise FeatureEngineeringException(f"Data preprocessing failed: {str(e)}")

    def create_training_dataset(self, df: pd.DataFrame, target_col: str = 'power_output',
                              feature_cols: Optional[List[str]] = None,
                              test_size: float = 0.2) -> tuple:
        """Create training dataset with features and target."""
        try:
            logger.info("Creating training dataset...")

            # Create features
            df_features = self.feature_engineer.create_features(df, target_col)

            # Select features if not provided
            if feature_cols is None:
                feature_cols = self.feature_engineer.select_features(df_features, target_col)

            # Prepare features and target
            X = df_features[feature_cols].copy()
            y = df_features[target_col].copy()

            # Remove rows with missing values
            mask = ~(X.isnull().any(axis=1) | y.isnull())
            X = X[mask]
            y = y[mask]

            # Split into train and test sets
            split_index = int(len(X) * (1 - test_size))
            X_train, X_test = X[:split_index], X[split_index:]
            y_train, y_test = y[:split_index], y[split_index:]

            logger.info(f"Training dataset created: {len(X_train)} train, {len(X_test)} test samples")
            logger.info(f"Number of features: {len(feature_cols)}")

            return X_train, X_test, y_train, y_test, feature_cols

        except Exception as e:
            logger.error(f"Training dataset creation failed: {e}")
            raise FeatureEngineeringException(f"Training dataset creation failed: {str(e)}")

    def prepare_prediction_data(self, df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        """Prepare data for prediction."""
        try:
            logger.info("Preparing prediction data...")

            # Create features
            df_features = self.feature_engineer.create_features(df)

            # Select only the features used in training
            available_features = [col for col in feature_cols if col in df_features.columns]
            missing_features = [col for col in feature_cols if col not in df_features.columns]

            if missing_features:
                logger.warning(f"Missing features for prediction: {missing_features}")
                # Create dummy columns for missing features
                for feature in missing_features:
                    df_features[feature] = 0

            X = df_features[feature_cols].copy()

            # Handle missing values
            X = X.fillna(X.mean())

            logger.info(f"Prediction data prepared: {len(X)} samples, {len(feature_cols)} features")
            return X

        except Exception as e:
            logger.error(f"Prediction data preparation failed: {e}")
            raise FeatureEngineeringException(f"Prediction data preparation failed: {str(e)}")

    def calculate_data_quality_score(self, df: pd.DataFrame, target_col: str = 'power_output') -> float:
        """Calculate data quality score."""
        try:
            score = 100.0

            # Missing values penalty
            missing_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
            score -= missing_ratio * 30

            # Target variable completeness
            if target_col in df.columns:
                target_missing = df[target_col].isnull().sum() / len(df)
                score -= target_missing * 20

            # Data range validation
            if 'wind_speed' in df.columns:
                wind_speed_range = df['wind_speed'].between(0, 50).mean()
                score -= (1 - wind_speed_range) * 10

            if 'power_output' in df.columns:
                power_negative = (df['power_output'] < 0).mean()
                score -= power_negative * 15

            # Time series continuity
            if 'timestamp' in df.columns:
                df_sorted = df.sort_values('timestamp')
                time_diffs = df_sorted['timestamp'].diff().dt.total_seconds() / 3600
                expected_diff = time_diffs.mode().iloc[0] if len(time_diffs.mode()) > 0 else 1.0
                gaps = (time_diffs > expected_diff * 2).mean()
                score -= gaps * 10

            # Outlier penalty
            outlier_cols = ['wind_speed', 'temperature', 'power_output']
            for col in outlier_cols:
                if col in df.columns:
                    Q1 = df[col].quantile(0.25)
                    Q3 = df[col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    outliers = ((df[col] < lower_bound) | (df[col] > upper_bound)).mean()
                    score -= outliers * 5

            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.error(f"Data quality score calculation failed: {e}")
            return 0.0


# Global instances
feature_engineer = FeatureEngineer()
data_preprocessor = DataPreprocessor()