import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


CAPACITY_MW = 47.5


def _make_forecast_frame(n: int = 500) -> pd.DataFrame:
    """生成列名和时间粒度均贴近生产 NWP 表的固定测试数据。"""
    position = np.arange(n, dtype=float)
    return pd.DataFrame({
        "Timestamp": pd.date_range("2026-01-01", periods=n, freq="15min"),
        "Total_Power": np.clip(22 + 8 * np.sin(position / 20), 0, CAPACITY_MW),
        "100u_23.8_103.2": 4 + np.sin(position / 13),
        "100v_23.8_103.2": 3 + np.cos(position / 17),
        "2t_23.8_103.2": 288.15 + 2 * np.sin(position / 96),
        "sp_23.8_103.2": 101325 + 150 * np.cos(position / 96),
    })


class _FakeRegressor:
    """让契约测试覆盖训练流程，同时避免运行耗时的真实模型训练。"""

    def __init__(self, **_kwargs):
        self.value = 0.0
        self.n_features_in_ = 0

    def fit(self, X, y, *_args, **_kwargs):
        self.value = float(np.mean(np.asarray(y, dtype=float)))
        self.n_features_in_ = int(X.shape[1])
        return self

    def predict(self, X):
        return np.full(len(X), self.value, dtype=float)


@pytest.fixture
def fake_ensemble_dependencies(monkeypatch):
    """用轻量替身锁定服务调用契约。"""
    monkeypatch.setitem(sys.modules, "lightgbm", SimpleNamespace(LGBMRegressor=_FakeRegressor))
    monkeypatch.setitem(sys.modules, "xgboost", SimpleNamespace(XGBRegressor=_FakeRegressor))
    monkeypatch.setitem(sys.modules, "catboost", SimpleNamespace(CatBoostRegressor=_FakeRegressor))


def test_build_features_adds_temporal_and_grid_columns():
    from services.forecast_service import build_features

    df = _make_forecast_frame(192)
    result = build_features(df, cap=CAPACITY_MW)

    assert "hour_sin" in result.columns
    assert "hour_cos" in result.columns
    assert "wind_u_100m_23.8_103.2" in result.columns
    assert "ws100_1" in result.columns
    assert "wd100_1" in result.columns
    assert "power_lag_1d" in result.columns
    expected_speed = np.hypot(df.loc[0, "100u_23.8_103.2"], df.loc[0, "100v_23.8_103.2"])
    assert result.loc[0, "ws100_1"] == pytest.approx(expected_speed)


def test_build_features_uses_grid_density_contract():
    from services.forecast_service import build_features

    df = _make_forecast_frame(192)
    result = build_features(df, cap=CAPACITY_MW)

    assert "temperature_2m_23.8_103.2" in result.columns
    assert "surface_pressure_23.8_103.2" in result.columns
    assert "grid_air_density" in result.columns
    assert "grid_power_density_100m" in result.columns
    expected_density = df.loc[0, "sp_23.8_103.2"] / (287.05 * df.loc[0, "2t_23.8_103.2"])
    assert result.loc[0, "grid_air_density"] == pytest.approx(expected_density)


def test_prepare_xy_excludes_time_and_target():
    from services.forecast_service import build_features, prepare_xy

    featured = build_features(_make_forecast_frame(192), cap=CAPACITY_MW)
    X, y, cols = prepare_xy(featured)

    assert "Timestamp" not in X.columns
    assert "Total_Power" not in X.columns
    assert len(X) == len(y) == 192
    assert cols == list(X.columns)


def test_fit_affine_returns_valid_params():
    from services.forecast_service import fit_affine

    np.random.seed(42)
    y = np.random.rand(100) * CAPACITY_MW
    p = y * 0.95 + 1.0
    alpha, beta = fit_affine(y, p, cap=CAPACITY_MW)
    assert 0.5 < alpha < 1.5
    assert -20 < beta < 20


def test_split_train_calibrate_uses_chronological_three_way_split():
    from services.forecast_service import split_train_calibrate

    df = pd.DataFrame({"x": range(1000)})
    train, val, test = split_train_calibrate(df)

    assert (len(train), len(val), len(test)) == (700, 150, 150)
    assert train.iloc[-1]["x"] == 699
    assert val.iloc[0]["x"] == 700
    assert val.iloc[-1]["x"] == 849
    assert test.iloc[0]["x"] == 850


def test_train_ensemble_returns_models_and_current_contract(fake_ensemble_dependencies):
    from services.forecast_contract import SHORT_MID_FEATURE_CONTRACT_VERSION
    from services.forecast_service import split_train_calibrate, train_ensemble

    train_df, val_df, test_df = split_train_calibrate(_make_forecast_frame())
    models, feature_columns, meta = train_ensemble(
        train_df,
        val_df,
        test_df,
        cap=CAPACITY_MW,
    )

    assert set(models) == {"lgb", "xgb", "cb"}
    assert "ws100_1" in feature_columns
    assert "grid_air_density" in feature_columns
    assert meta["feature_contract_version"] == SHORT_MID_FEATURE_CONTRACT_VERSION
    assert "train_date" in meta
    assert "cal_accuracy" in meta


def test_predict_with_ensemble_uses_complete_saved_feature_contract(fake_ensemble_dependencies):
    from services.forecast_service import (
        build_features,
        predict_with_ensemble,
        split_train_calibrate,
        train_ensemble,
    )

    source = _make_forecast_frame()
    train_df, val_df, test_df = split_train_calibrate(source)
    models, feature_columns, _ = train_ensemble(
        train_df,
        val_df,
        test_df,
        cap=CAPACITY_MW,
    )

    prediction_source = source.copy()
    prediction_source.loc[prediction_source.index[-100:], "Total_Power"] = np.nan
    featured = build_features(prediction_source, cap=CAPACITY_MW)
    prediction_df = featured.iloc[-100:].copy()
    predictions = predict_with_ensemble(
        models,
        feature_columns,
        prediction_df,
        cap=CAPACITY_MW,
    )

    assert len(predictions) == 100
    assert np.all(predictions >= 0)
    assert np.all(predictions <= CAPACITY_MW)


def test_predict_with_ensemble_rejects_missing_model_features():
    from services.forecast_contract import ForecastContractError
    from services.forecast_service import predict_with_ensemble

    model = _FakeRegressor().fit(
        pd.DataFrame({"ws100_1": [1.0], "grid_air_density": [1.2]}),
        np.array([1.0]),
    )
    with pytest.raises(ForecastContractError, match="预测输入缺少 1 个模型特征"):
        predict_with_ensemble(
            {"lgb": model},
            ["ws100_1", "grid_air_density"],
            pd.DataFrame({"ws100_1": [5.0]}),
            cap=CAPACITY_MW,
        )
