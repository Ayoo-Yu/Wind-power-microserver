"""训练流程的可复用封装。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from backend.scripts.train_run import train_run


@dataclass
class TrainingResult:
    forecast_file: Path
    model_file: Path
    scaler_file: Path


def run_training(
    data_file: Path,
    model: str,
    train_ratio: float = 0.9,
    custom_params: Optional[Dict[str, Any]] = None,
) -> TrainingResult:
    forecast_path, model_path, scaler_path = train_run(
        DATA_FILE_PATH=str(data_file),
        MODEL=model,
        TRAIN_RATIO=train_ratio,
        CUSTOM_PARAMS=custom_params,
    )

    return TrainingResult(
        forecast_file=Path(forecast_path),
        model_file=Path(model_path),
        scaler_file=Path(scaler_path),
    )


