"""预测流程的可复用封装。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.scripts.predict import (
    LAGS,
    OUTPUT_DIR,
    load_models_and_scaler,
    make_predictions,
    preprocess_new_data,
    save_predictions_to_csv,
)


@dataclass
class PredictionResult:
    output_file: Path
    predictions: pd.DataFrame


def run_prediction(
    csv_path: Path,
    model_path: Path,
    scaler_path: Path,
    window_size: int = 16,
) -> PredictionResult:
    model, scaler = load_models_and_scaler(str(model_path), str(scaler_path))
    features, timestamps = preprocess_new_data(str(csv_path), LAGS)
    predictions = make_predictions(model, scaler, features, window_size, LAGS)

    predictions_df = pd.DataFrame({
        "Timestamp": timestamps[LAGS + window_size - 1 : LAGS + window_size - 1 + len(predictions)],
        "Predicted Power": predictions,
    })

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = Path(
        save_predictions_to_csv(predictions, timestamps, str(output_dir), str(model_path))
    )

    return PredictionResult(output_file=output_file, predictions=predictions_df)


