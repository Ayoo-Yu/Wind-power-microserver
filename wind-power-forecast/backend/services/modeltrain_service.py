from pathlib import Path

from scripts.prediction_timestamp import post_process_predictions
from windpower_core.training import run_training


def run_modeltrain(upload_path, model, train_ratio=0.9, custom_params=None):
    result = run_training(
        data_file=Path(upload_path),
        model=model,
        train_ratio=train_ratio,
        custom_params=custom_params,
    )

    forecast_file_path = post_process_predictions(upload_path, str(result.forecast_file))
    return forecast_file_path, str(result.model_file), str(result.scaler_file)
