"""Shared utility functions for short/middle training pipelines.

Contains visualisation helpers, RMSE / K-value calculators, and time-weighted
evaluation. Both ``utils_short`` and ``utils_middle`` re-export everything from
this module for backward compatibility.
"""

from __future__ import annotations

import math
import logging
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ``Today`` is injected by the thin wrapper that imports this module.
# It is stored as a module-level variable that can be overridden.
Today = None  # type: str | None

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_current_farm_code() -> str:
    return os.environ.get('FARM_CODE', os.environ.get('DEFAULT_FARM_CODE', 'DEFAULT_FARM'))


def get_farm_capacity(farm_code: str) -> float:
    """Look up installed capacity from wind_farms table, fallback to env var."""
    try:
        from db_session import db_session
        from sqlalchemy import text
        with db_session() as session:
            row = session.execute(
                text("SELECT installed_capacity FROM wind_farms WHERE farm_code = :code"),
                {"code": farm_code},
            ).fetchone()
            if row and row[0]:
                return float(row[0])
    except Exception:
        pass
    return float(os.environ.get('WF_CAPACITY_FALLBACK', '779.0'))


def get_evaluation_capacity(farm_code: str | None = None, capacity: float | None = None) -> float:
    if capacity is not None:
        return float(capacity)
    return get_farm_capacity(farm_code or get_current_farm_code())


def normalize_rmse_score(rmse: float, farm_code: str | None = None, capacity: float | None = None) -> float:
    effective_capacity = get_evaluation_capacity(farm_code=farm_code, capacity=capacity)
    if effective_capacity <= 0:
        raise ValueError(f"capacity must be positive, got {effective_capacity}")
    return min(1.0, rmse / effective_capacity)


def set_today(value: str) -> None:
    """Set the module-level ``Today`` date string (called by wrapper)."""
    global Today
    Today = value


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

def visualize_results(results_dict, y_val, output_path):
    """Visualise prediction results of different models against actual values."""
    plt.figure(figsize=(20, 10))
    for model_name, result in results_dict.items():
        plt.plot(range(len(result['y_pred'])), result['y_pred'],
                 label=f'{model_name} Predicted Power')

    plt.plot(range(len(y_val)), y_val, label='Actual Power', linestyle='dashed')
    plt.xlabel('Index')
    plt.ylabel('Power')
    plt.title('Verify set power predictions - Different LightGBM Models')
    plt.legend()

    output_dir = os.path.join(output_path, Today)
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, 'Predictions.png')
    plt.savefig(output_file)
    plt.close()
    print(f"图像已保存为 {output_file}")


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def calculate_rmse(y_true, y_pred):
    """Calculate RMSE (Root Mean Square Error)."""
    if len(y_true) != len(y_pred):
        raise ValueError("实际值和预测值长度必须相同")
    return np.sqrt(np.mean((y_true - y_pred) ** 2))


def calculate_k(y_true, y_pred, threshold=None, capacity=None, farm_code=None):
    """Calculate qualification rate K-value (overall).

    Note: This computes a single K-value for all data as a whole.
    For per-day averaged K, use :func:`calculate_daily_averaged_k`.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("实际值和预测值长度必须相同")

    if threshold is None:
        threshold = get_evaluation_capacity(farm_code=farm_code, capacity=capacity) * 0.2

    denominators = np.maximum(np.abs(y_true), threshold)
    m_values = ((y_pred - y_true) / denominators) ** 2
    k_value = 1 - np.sqrt(np.mean(m_values))
    return k_value


def calculate_daily_averaged_k(y_true, y_pred, capacity=None,
                                threshold=None, points_per_day=96):
    """Calculate daily-averaged qualification rate K-value.

    K is computed per-day (each day has *points_per_day* data points).
    If the last day has fewer points it is computed on the available count.
    Returns the arithmetic mean of all daily K-values.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    if len(y_true) != len(y_pred):
        raise ValueError("实际值和预测值长度必须相同")

    n_points = len(y_true)
    if n_points == 0:
        print("警告: 输入数据为空，返回 NaN。")
        return np.nan

    if threshold is None:
        effective_capacity = get_evaluation_capacity(capacity=capacity)
        effective_threshold = effective_capacity * 0.2
    else:
        effective_threshold = threshold

    if effective_threshold <= 0:
        raise ValueError(
            f"计算出的阈值必须为正数, 但得到的是 {effective_threshold}")

    daily_k_values = []
    num_days = math.ceil(n_points / points_per_day)

    for i in range(num_days):
        start_index = i * points_per_day
        end_index = min((i + 1) * points_per_day, n_points)

        y_true_day = y_true[start_index:end_index]
        y_pred_day = y_pred[start_index:end_index]

        if len(y_true_day) == 0:
            continue

        denominators = np.maximum(np.abs(y_true_day), effective_threshold)
        with np.errstate(divide='ignore', invalid='ignore'):
            m_values = ((y_pred_day - y_true_day) / denominators) ** 2

        m_values = np.nan_to_num(
            m_values, nan=0.0,
            posinf=np.finfo(m_values.dtype).max,
            neginf=np.finfo(m_values.dtype).min,
        )

        if m_values.size > 0:
            mean_m_value = np.mean(m_values)
            k_day = 1 - np.sqrt(max(0, mean_m_value))
            daily_k_values.append(k_day)
        else:
            print(f"警告: 索引 {start_index} 开始的当天没有有效的 M 值，已跳过。")

    if not daily_k_values:
        print("警告: 未能计算出任何有效的日K值 (可能是因为输入长度问题或数据导致计算错误)。返回 NaN。")
        return np.nan

    return float(np.mean(daily_k_values))


def evaluate_with_time_weights(y_true, y_pred, timestamps,
                                rmse_weight=0.2, k_weight=0.8,
                                time_decay=0.9, points_per_day=96,
                                farm_code=None, capacity=None):
    """Compute composite score using time-weighted RMSE and K-value.

    Returns
    -------
    tuple[float, float, float, float, float]
        (composite_score, standard_rmse, standard_k, weighted_rmse, weighted_k)
    """
    if len(y_true) != len(y_pred) or len(y_true) != len(timestamps):
        print("实际值长度", len(y_true))
        print("预测值长度", len(y_pred))
        print("时间戳长度", len(timestamps))
        logger.info(f"实际值长度: {len(y_true)}")
        logger.info(f"预测值长度: {len(y_pred)}")
        logger.info(f"时间戳长度: {len(timestamps)}")
        raise ValueError("实际值、预测值和时间戳长度必须相同")

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps),
        'y_true': y_true,
        'y_pred': y_pred,
    })

    # Time weights
    latest_time = df['timestamp'].max()
    time_deltas = []
    for t in df['timestamp']:
        time_diff = latest_time - t
        if hasattr(time_diff, 'total_seconds'):
            seconds = time_diff.total_seconds()
        else:
            seconds = time_diff / np.timedelta64(1, 's')
        time_deltas.append(seconds / 3600)

    max_delta = max(time_deltas) if time_deltas else 1
    time_weights = np.array(
        [time_decay ** (delta / max_delta) for delta in time_deltas])
    time_weights = time_weights / sum(time_weights)
    df['time_weight'] = time_weights

    squared_errors = (df['y_true'] - df['y_pred']) ** 2
    weighted_rmse = np.sqrt(np.sum(squared_errors * df['time_weight']))

    if len(df) == 0:
        print("警告: 输入数据为空，返回默认值。")
        logger.warning("警告: 输入数据为空，返回默认值。")
        return 0.0, 0.0, 0.0, 0.0, 0.0

    effective_capacity = get_evaluation_capacity(farm_code=farm_code, capacity=capacity)
    df['date'] = df['timestamp'].dt.date
    daily_groups = df.groupby('date')

    daily_k_values = []
    daily_time_weights = []
    daily_data_counts = []
    threshold = effective_capacity * 0.2

    for date, group in daily_groups:
        day_data_count = len(group)
        daily_data_counts.append(day_data_count)
        if day_data_count == 0:
            continue

        y_true_day = group['y_true'].values
        y_pred_day = group['y_pred'].values
        day_time_weights = group['time_weight'].values

        denominators = np.maximum(np.abs(y_true_day), threshold)
        with np.errstate(divide='ignore', invalid='ignore'):
            m_values = ((y_pred_day - y_true_day) / denominators) ** 2

        m_values = np.nan_to_num(
            m_values, nan=0.0,
            posinf=np.finfo(m_values.dtype).max,
            neginf=np.finfo(m_values.dtype).min,
        )

        if m_values.size > 0:
            mean_m_value = np.mean(m_values)
            k_day = 1 - np.sqrt(max(0, mean_m_value))
            daily_k_values.append(k_day)
            avg_day_weight = np.mean(day_time_weights)
            daily_time_weights.append(avg_day_weight)
            print(f"📊 {date}: {day_data_count}/{points_per_day} 个点, "
                  f"K值: {k_day:.4f}, 平均时间权重: {avg_day_weight:.6f}")
            logger.info(f"📊 {date}: {day_data_count}/{points_per_day} 个点, "
                        f"K值: {k_day:.4f}, 平均时间权重: {avg_day_weight:.6f}")

    if daily_k_values and daily_time_weights:
        daily_time_weights = np.array(daily_time_weights)
        daily_time_weights = daily_time_weights / np.sum(daily_time_weights)
        weighted_k = float(np.sum(np.array(daily_k_values) * daily_time_weights))
        print(f"✅ 成功计算 {len(daily_k_values)} 天的K值进行时间加权")
        logger.info(f"✅ 成功计算 {len(daily_k_values)} 天的K值进行时间加权")
    else:
        print("⚠️ 未能计算出任何有效的日K值，weighted_k设为0")
        logger.warning("⚠️ 未能计算出任何有效的日K值，weighted_k设为0")
        weighted_k = 0.0

    rmse = calculate_rmse(y_true, y_pred)
    k = calculate_daily_averaged_k(y_true, y_pred, capacity=effective_capacity,
                                    threshold=None,
                                    points_per_day=points_per_day)

    total_expected_points = len(set(df['date'])) * points_per_day
    actual_points = len(df)
    completeness_ratio = (actual_points / total_expected_points
                          if total_expected_points > 0 else 0)
    print(f"📈 数据完整性: {actual_points}/{total_expected_points} "
          f"({completeness_ratio:.1%})")
    logger.info(f"📈 数据完整性: {actual_points}/{total_expected_points} "
                f"({completeness_ratio:.1%})")

    norm_rmse = normalize_rmse_score(weighted_rmse, capacity=effective_capacity)
    norm_weighted_rmse = 1 - norm_rmse
    score = norm_weighted_rmse * rmse_weight + weighted_k * k_weight

    return score, rmse, k, weighted_rmse, weighted_k
