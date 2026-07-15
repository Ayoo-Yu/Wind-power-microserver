"""预测模型与运行时特征之间的契约校验。"""

from __future__ import annotations

from collections import Counter
from numbers import Integral
from typing import Iterable, Mapping, Sequence


SHORT_MID_FEATURE_CONTRACT_VERSION = "short-mid-grid-v1"
LEGACY_COORDINATE_FEATURE_CONTRACT_VERSION = "legacy-coordinate-v1"
UNKNOWN_FEATURE_CONTRACT_VERSION = "unknown"


class ForecastContractError(RuntimeError):
    """模型、特征清单或运行时输入不兼容。"""


def normalize_feature_columns(feature_columns: Sequence[str] | None) -> list[str]:
    """校验并返回保持原顺序的特征清单。"""
    if not isinstance(feature_columns, (list, tuple)) or not feature_columns:
        raise ForecastContractError("模型缺少有效的 feature_columns 特征清单")

    normalized = list(feature_columns)
    invalid = [column for column in normalized if not isinstance(column, str) or not column.strip()]
    if invalid:
        raise ForecastContractError("feature_columns 包含空值或非字符串字段")

    duplicates = sorted(column for column, count in Counter(normalized).items() if count > 1)
    if duplicates:
        preview = ", ".join(duplicates[:8])
        raise ForecastContractError(f"feature_columns 包含重复字段: {preview}")
    return normalized


def infer_feature_contract_version(feature_columns: Sequence[str] | None) -> str:
    """根据已保存的特征清单识别历史契约版本。"""
    columns = normalize_feature_columns(feature_columns)
    if "grid_air_density" in columns and any(column.startswith("ws100_") for column in columns):
        return SHORT_MID_FEATURE_CONTRACT_VERSION
    if "air_density" in columns and any(column.startswith("wind_speed_100m") for column in columns):
        return LEGACY_COORDINATE_FEATURE_CONTRACT_VERSION
    return UNKNOWN_FEATURE_CONTRACT_VERSION


def validate_runtime_features(
    feature_columns: Sequence[str] | None,
    available_columns: Iterable[str],
) -> list[str]:
    """确认预测输入完整覆盖模型训练时保存的特征。"""
    expected = normalize_feature_columns(feature_columns)
    available = set(available_columns)
    missing = [column for column in expected if column not in available]
    if missing:
        preview = ", ".join(missing[:12])
        suffix = f"，另有 {len(missing) - 12} 个" if len(missing) > 12 else ""
        raise ForecastContractError(
            f"预测输入缺少 {len(missing)} 个模型特征: {preview}{suffix}"
        )
    return expected


def _model_feature_count(model: object) -> int | None:
    """读取常见模型实现保存的训练特征数量。"""
    count = getattr(model, "n_features_in_", None)
    if isinstance(count, Integral) and count > 0:
        return int(count)

    feature_names = getattr(model, "feature_names_", None)
    if isinstance(feature_names, (list, tuple)) and feature_names:
        return len(feature_names)

    count = getattr(model, "n_features_", None)
    if isinstance(count, Integral) and count > 0:
        return int(count)
    return None


def validate_model_bundle(
    models: Mapping[str, object],
    feature_columns: Sequence[str] | None,
) -> list[str]:
    """确认模型内部特征数量与 feature_columns 一致。"""
    expected = normalize_feature_columns(feature_columns)
    mismatches: list[str] = []
    for name in ("lgb", "xgb", "cb"):
        model = models.get(name)
        if model is None:
            continue
        count = _model_feature_count(model)
        if count is not None and count != len(expected):
            mismatches.append(f"{name}={count}")

    if mismatches:
        details = ", ".join(mismatches)
        raise ForecastContractError(
            f"模型特征数量与 feature_columns 不一致，清单={len(expected)}，模型={details}"
        )
    return expected
