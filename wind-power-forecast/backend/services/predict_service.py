from pathlib import Path

from windpower_core.training import run_prediction


def run_predict(csv_path, model_path, scaler_path, window_size=16):
    result = run_prediction(
        csv_path=Path(csv_path),
        model_path=Path(model_path),
        scaler_path=Path(scaler_path),
        window_size=window_size,
    )

    return str(result.output_file)
