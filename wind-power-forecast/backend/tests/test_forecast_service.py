import numpy as np
import pandas as pd
import pytest


def test_build_features_adds_temporal_columns():
    from services.forecast_service import build_features
    df = pd.DataFrame({
        "Timestamp": pd.date_range("2026-05-01", periods=96, freq="15min"),
        "Total_Power": np.random.rand(96) * 50,
        "100u_23.8_103.2": np.random.rand(96),
        "100v_23.8_103.2": np.random.rand(96),
    })
    result = build_features(df, cap=47.5)
    assert "hour_sin" in result.columns
    assert "hour_cos" in result.columns
    # NWP columns are renamed with suffix preserved: wind_u_100m_23.8_103.2
    assert "wind_u_100m_23.8_103.2" in result.columns
    # Wind speed derived from matched u/v pair with same suffix
    assert "wind_speed_100m_23.8_103.2" in result.columns
    assert "power_lag_1d" in result.columns


def test_build_features_renames_nwp_columns():
    from services.forecast_service import build_features
    df = pd.DataFrame({
        "Timestamp": pd.date_range("2026-05-01", periods=96, freq="15min"),
        "Total_Power": np.random.rand(96) * 50,
        "100u_23.8_103.2": np.random.rand(96),
        "100v_23.8_103.2": np.random.rand(96),
        "2t_23.8_103.2": np.random.rand(96) * 300,
        "sp_23.8_103.2": np.random.rand(96) * 100000,
    })
    result = build_features(df, cap=47.5)
    # NWP rename preserves location suffix
    assert "wind_u_100m_23.8_103.2" in result.columns
    assert "temperature_2m_23.8_103.2" in result.columns
    assert "surface_pressure_23.8_103.2" in result.columns
    # Aggregated features use averaged grid points
    assert "air_density" in result.columns
    # wind_shear_index only when both 10m and 100m wind data present
    # (not present here because no 10u/10v columns)


def test_prepare_xy_excludes_time_and_target():
    from services.forecast_service import build_features, prepare_xy
    df = pd.DataFrame({
        "Timestamp": pd.date_range("2026-05-01", periods=96, freq="15min"),
        "Total_Power": np.random.rand(96) * 50,
        "100u_23.8_103.2": np.random.rand(96),
        "100v_23.8_103.2": np.random.rand(96),
    })
    featured = build_features(df, cap=47.5)
    X, y, cols = prepare_xy(featured)
    assert "Timestamp" not in X.columns
    assert "Total_Power" not in X.columns
    assert len(X) > 0


def test_fit_affine_returns_valid_params():
    from services.forecast_service import fit_affine
    np.random.seed(42)
    y = np.random.rand(100) * 47.5
    p = y * 0.95 + 1.0
    alpha, beta = fit_affine(y, p, cap=47.5)
    assert 0.5 < alpha < 1.5
    assert -20 < beta < 20


def test_split_train_calibrate():
    from services.forecast_service import split_train_calibrate
    df = pd.DataFrame({"x": range(1000)})
    train, cal = split_train_calibrate(df)
    assert len(train) == 850
    assert len(cal) == 150


def test_train_ensemble_returns_models_and_features():
    from services.forecast_service import build_features, train_ensemble
    np.random.seed(42)
    n = 500
    df = pd.DataFrame({
        "Timestamp": pd.date_range("2026-01-01", periods=n, freq="15min"),
        "Total_Power": np.random.rand(n) * 47.5,
        "100u_23.8_103.2": np.random.rand(n) * 10,
        "100v_23.8_103.2": np.random.rand(n) * 10,
    })
    featured = build_features(df, cap=47.5)
    train_df = featured.iloc[:400]
    cal_df = featured.iloc[400:]
    models, feature_columns, meta = train_ensemble(train_df, cal_df, cap=47.5)
    assert "lgb" in models
    assert "xgb" in models
    assert "cb" in models
    assert len(feature_columns) > 0
    assert "train_date" in meta
    assert "cal_accuracy" in meta


def test_predict_with_ensemble():
    from services.forecast_service import build_features, train_ensemble, predict_with_ensemble
    np.random.seed(42)
    n = 500
    df = pd.DataFrame({
        "Timestamp": pd.date_range("2026-01-01", periods=n, freq="15min"),
        "Total_Power": np.random.rand(n) * 47.5,
        "100u_23.8_103.2": np.random.rand(n) * 10,
        "100v_23.8_103.2": np.random.rand(n) * 10,
    })
    featured = build_features(df, cap=47.5)
    train_df = featured.iloc[:400]
    cal_df = featured.iloc[400:]
    models, feature_columns, _ = train_ensemble(train_df, cal_df, cap=47.5)
    test_data = featured.iloc[400:].copy()
    test_data["Total_Power"] = np.nan
    preds = predict_with_ensemble(models, feature_columns, test_data, cap=47.5)
    assert len(preds) == 100
    assert all(preds >= 0)
    assert all(preds <= 47.5)
