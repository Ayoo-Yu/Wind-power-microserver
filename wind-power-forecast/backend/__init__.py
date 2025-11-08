"""
backend 包初始化。

为兼容旧代码，保留对 Base、engine 等符号的导出，但通过惰性加载避免在
导入包时立即建立数据库连接或触发副作用。
"""

from __future__ import annotations

from typing import Any, Dict

__all__ = ["Base", "engine", "get_db", "Dataset", "Model", "TrainingRecord"]


def __getattr__(name: str) -> Any:
    if name == "Base":
        from .base import Base as _Base

        return _Base

    if name in {"engine", "get_db"}:
        from .database_config import engine as _engine, get_db as _get_db

        mapping: Dict[str, Any] = {"engine": _engine, "get_db": _get_db}
        return mapping[name]

    if name in {"Dataset", "Model", "TrainingRecord"}:
        from .models import Dataset as _Dataset, Model as _Model, TrainingRecord as _TrainingRecord

        mapping: Dict[str, Any] = {
            "Dataset": _Dataset,
            "Model": _Model,
            "TrainingRecord": _TrainingRecord,
        }
        return mapping[name]

    raise AttributeError(f"module 'backend' has no attribute '{name}'")