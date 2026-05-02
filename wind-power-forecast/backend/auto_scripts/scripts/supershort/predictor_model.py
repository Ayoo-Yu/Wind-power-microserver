import os
import sys
import logging

import joblib
import numpy as np
import pandas as pd

current_file_dir = os.path.dirname(os.path.abspath(__file__))
path_to_scripts = os.path.abspath(os.path.join(current_file_dir, ".."))
path_to_backend = os.path.abspath(os.path.join(current_file_dir, "..", "..", ".."))
for path in (path_to_scripts, path_to_backend):
    if path not in sys.path:
        sys.path.insert(0, path)

from optimized_ensemble import (
    ULTRA_BUNDLE_NAME,
    fit_ultrashort_shift,
    predict_ultrashort_shift,
)


class WindPowerPredictor:
    """Ultra-short optimized ensemble wrapper.

    Keeps the old public methods used by train_supershort.py and
    predict_supershort.py, while replacing the single XGBoost model with the
    benchmark ensemble: LGBM-DART + XGBoost + optional CatBoost, trained on
    delta targets for each shift.
    """

    def __init__(self, n_shift):
        self.n_shift = int(n_shift)
        self.bundle = None
        self.numeric_features = None
        self.target_col_name = f"power_diff_{self.n_shift}"
        self.feature_power_t_minus_N_col_name = f"power_actual_at_t_minus_{self.n_shift}"
        self._is_fitted = False

    def train(self, train_data):
        try:
            # Use an in-memory training directory until save_state() writes the
            # final artifact path expected by the scheduler.
            temp_dir = os.path.join(current_file_dir, "saved_models", f"_tmp_shift_{self.n_shift}")
            self.bundle = fit_ultrashort_shift(train_data, self.n_shift, temp_dir)
            self.numeric_features = self.bundle.get("feature_cols", [])
            self.feature_power_t_minus_N_col_name = self.bundle.get(
                "power_feature", self.feature_power_t_minus_N_col_name
            )
            self._is_fitted = True
            logging.info("optimized ultra-short shift %s trained", self.n_shift)
            return True
        except Exception as exc:
            logging.error("optimized ultra-short shift %s training failed: %s", self.n_shift, exc, exc_info=True)
            self._is_fitted = False
            return False

    def train_quantile(self, data, alpha=0.5):
        # The optimized benchmark does not include quantile heads. Existing
        # prediction code treats missing quantile models as optional.
        logging.info("skip quantile training for optimized ultra-short shift %s alpha=%s", self.n_shift, alpha)
        return False

    def predict(self, test_data):
        if not self._is_fitted:
            logging.error("optimized ultra-short shift %s is not loaded", self.n_shift)
            return pd.Series(index=test_data.index, dtype=float)
        try:
            if self._loaded_dir:
                return predict_ultrashort_shift(test_data, self._loaded_dir)
        except AttributeError:
            pass
        except Exception as exc:
            logging.error("optimized ultra-short shift %s prediction failed: %s", self.n_shift, exc, exc_info=True)
            return pd.Series(index=test_data.index, dtype=float)

        if not self.bundle:
            return pd.Series(index=test_data.index, dtype=float)
        tmp_dir = os.path.join(current_file_dir, "saved_models", f"_tmp_predict_shift_{self.n_shift}")
        os.makedirs(tmp_dir, exist_ok=True)
        joblib.dump(self.bundle, os.path.join(tmp_dir, ULTRA_BUNDLE_NAME))
        return predict_ultrashort_shift(test_data, tmp_dir)

    def save_state(self, directory):
        if not self._is_fitted or not self.bundle:
            logging.warning("optimized ultra-short shift %s has no trained state to save", self.n_shift)
            return False
        try:
            os.makedirs(directory, exist_ok=True)
            joblib.dump(self.bundle, os.path.join(directory, ULTRA_BUNDLE_NAME))
            joblib.dump(self.bundle, os.path.join(directory, "model.joblib"))
            joblib.dump(self.numeric_features or [], os.path.join(directory, "numeric_features.joblib"))
            joblib.dump(
                {
                    "n_shift_saved": self.n_shift,
                    "target_col_name": self.target_col_name,
                    "feature_power_t_minus_N_col_name": self.feature_power_t_minus_N_col_name,
                },
                os.path.join(directory, "predictor_config.joblib"),
            )
            logging.info("optimized ultra-short shift %s saved to %s", self.n_shift, directory)
            return True
        except Exception as exc:
            logging.error("optimized ultra-short shift %s save failed: %s", self.n_shift, exc, exc_info=True)
            return False

    def load_state(self, directory):
        try:
            bundle_path = os.path.join(directory, ULTRA_BUNDLE_NAME)
            if not os.path.exists(bundle_path):
                bundle_path = os.path.join(directory, "model.joblib")
            self.bundle = joblib.load(bundle_path)
            if not isinstance(self.bundle, dict) or self.bundle.get("kind") != "optimized_ultrashort_ensemble":
                raise ValueError("artifact is not an optimized ultra-short ensemble")
            saved_shift = int(self.bundle.get("shift", self.n_shift))
            if saved_shift != self.n_shift:
                logging.warning("current shift %s differs from saved shift %s", self.n_shift, saved_shift)
            self.numeric_features = self.bundle.get("feature_cols", [])
            self.feature_power_t_minus_N_col_name = self.bundle.get(
                "power_feature", self.feature_power_t_minus_N_col_name
            )
            self._loaded_dir = directory
            self._is_fitted = True
            logging.info("optimized ultra-short shift %s loaded from %s", self.n_shift, directory)
            return True
        except Exception as exc:
            logging.error("optimized ultra-short shift %s load failed: %s", self.n_shift, exc, exc_info=True)
            self._is_fitted = False
            return False


def preprocess_data(data_input: pd.DataFrame) -> pd.DataFrame:
    data = data_input.copy()
    if "Timestamp" in data.columns:
        data["Timestamp"] = pd.to_datetime(data["Timestamp"], errors="coerce")
    if "Unnamed: 0" in data.columns:
        data = data.drop(columns=["Unnamed: 0"])
    data = data.drop_duplicates()
    numeric_cols = data.select_dtypes(include=[np.number]).columns
    data[numeric_cols] = data[numeric_cols].replace([np.inf, -np.inf], np.nan)
    data = data.ffill().bfill()
    return data
