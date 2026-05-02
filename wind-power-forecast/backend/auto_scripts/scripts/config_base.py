"""Shared configuration base for short/middle training pipelines.

This module provides the common configuration logic used by both the short-term
(24h) and middle-term (72h) prediction pipelines. Each variant (config_short,
config_middle) is a thin wrapper that sets VARIANT_PARAMS and then calls
``init_config`` from this module.
"""
import os
from datetime import datetime


# ---------------------------------------------------------------------------
# Variant-specific parameter defaults (overridden by wrappers before init)
# ---------------------------------------------------------------------------

VARIANT_PARAMS = {
    # Key            short default  medium default  (set by wrapper)
    "TASK_TYPE":     "short",       # "short" | "medium"
    "TIME_HORIZON_HOURS": 24,       # hours for prediction window
    "USE_FARM_CODE": True,          # whether filenames include farm_code
    "LOG_PREFIX":    "",            # e.g. "(中期)" for middle
    "THREAD_NAME_SUFFIX": "",       # e.g. "-Middle" for middle
}


def init_config(current_dir: str) -> dict:
    """Initialise and return all configuration values.

    Parameters
    ----------
    current_dir : str
        The directory of the calling variant config (``__file__`` dir).

    Returns
    -------
    dict
        All config keys expected by the training/prediction pipeline.
    """
    Today = datetime.now().strftime('%Y%m%d')
    WINDOW_SIZE = 16
    TRAIN_RATIO = 0.9

    # Paths – all relative to *current_dir* (the variant's directory)
    DATASET_FOLDER = os.path.join(current_dir, 'datasets')
    PREC_SV_FOLDER = os.path.join(current_dir, 'predict_inputs')
    MODEL_FOLDER = os.path.join(current_dir, 'models')
    OUTPUT_DIR_PRE = os.path.join(current_dir, 'predict_outputs')
    FEATURE_IMPORTANCE_DIR = os.path.join(current_dir, 'feature_importance')
    OUTPUT_DIR_TRAIN = os.path.join(current_dir, 'train_predictions')

    # Logging paths
    PARAM_OPT_ITERATIONS = 10
    PARAM_OPT_WEEKLY = True
    PARAM_OPT_MIN_IMPROVEMENT = 0.05
    PARAM_OPT_LOG_DIR = os.path.join(current_dir, 'logs', 'param_optimizer')
    AUTO_PRE_TRAIN_LOG_DIR = os.path.join(current_dir, 'logs', 'auto_pre_train')

    LAGS = 4

    # Ensure directories exist
    for d in (OUTPUT_DIR_PRE, OUTPUT_DIR_TRAIN, PREC_SV_FOLDER,
              DATASET_FOLDER, MODEL_FOLDER, FEATURE_IMPORTANCE_DIR,
              AUTO_PRE_TRAIN_LOG_DIR):
        os.makedirs(d, exist_ok=True)

    # Print for debug visibility (same as original)
    for label, path in [
        ("DATASET_FOLDER", DATASET_FOLDER),
        ("PREC_SV_FOLDER", PREC_SV_FOLDER),
        ("MODEL_FOLDER", MODEL_FOLDER),
        ("OUTPUT_DIR_PRE", OUTPUT_DIR_PRE),
        ("FEATURE_IMPORTANCE_DIR", FEATURE_IMPORTANCE_DIR),
        ("OUTPUT_DIR_TRAIN", OUTPUT_DIR_TRAIN),
    ]:
        print(f"{label} ({_label_for(path)}): {path}")

    return {
        "Today": Today,
        "WINDOW_SIZE": WINDOW_SIZE,
        "TRAIN_RATIO": TRAIN_RATIO,
        "CURRENT_DIR": current_dir,
        "DATASET_FOLDER": DATASET_FOLDER,
        "PREC_SV_FOLDER": PREC_SV_FOLDER,
        "MODEL_FOLDER": MODEL_FOLDER,
        "OUTPUT_DIR_PRE": OUTPUT_DIR_PRE,
        "FEATURE_IMPORTANCE_DIR": FEATURE_IMPORTANCE_DIR,
        "OUTPUT_DIR_TRAIN": OUTPUT_DIR_TRAIN,
        "LAGS": LAGS,
        "PARAM_OPT_ITERATIONS": PARAM_OPT_ITERATIONS,
        "PARAM_OPT_WEEKLY": PARAM_OPT_WEEKLY,
        "PARAM_OPT_MIN_IMPROVEMENT": PARAM_OPT_MIN_IMPROVEMENT,
        "PARAM_OPT_LOG_DIR": PARAM_OPT_LOG_DIR,
        "AUTO_PRE_TRAIN_LOG_DIR": AUTO_PRE_TRAIN_LOG_DIR,
    }


def _label_for(path: str) -> str:
    """Return a short Chinese label for a path category (mirrors originals)."""
    mapping = {
        'datasets': '数据集',
        'predict_inputs': '预测输入',
        'models': '模型',
        'predict_outputs': '预测输出',
        'feature_importance': '特征重要性',
        'train_predictions': '训练预测输出',
    }
    basename = os.path.basename(path)
    return mapping.get(basename, basename)
