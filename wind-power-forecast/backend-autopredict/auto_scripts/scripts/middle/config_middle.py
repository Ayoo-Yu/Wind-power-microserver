"""Middle-term (72h) pipeline configuration.

Thin wrapper around :pymod:`config_base` with middle-specific parameters.
"""
import os
import sys

# Ensure parent directory is importable so config_base can be found
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_current_dir, '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from config_base import init_config, VARIANT_PARAMS

# Variant-specific overrides for middle
VARIANT_PARAMS["TASK_TYPE"] = "medium"
VARIANT_PARAMS["TIME_HORIZON_HOURS"] = 72
VARIANT_PARAMS["USE_FARM_CODE"] = False
VARIANT_PARAMS["LOG_PREFIX"] = "(中期)"
VARIANT_PARAMS["THREAD_NAME_SUFFIX"] = "-Middle"

_cfg = init_config(_current_dir)

# Re-export all keys as module-level names (backward compatibility)
Today = _cfg["Today"]
WINDOW_SIZE = _cfg["WINDOW_SIZE"]
TRAIN_RATIO = _cfg["TRAIN_RATIO"]
CURRENT_DIR = _cfg["CURRENT_DIR"]
DATASET_FOLDER = _cfg["DATASET_FOLDER"]
PREC_SV_FOLDER = _cfg["PREC_SV_FOLDER"]
MODEL_FOLDER = _cfg["MODEL_FOLDER"]
OUTPUT_DIR_PRE = _cfg["OUTPUT_DIR_PRE"]
FEATURE_IMPORTANCE_DIR = _cfg["FEATURE_IMPORTANCE_DIR"]
OUTPUT_DIR_TRAIN = _cfg["OUTPUT_DIR_TRAIN"]
LAGS = _cfg["LAGS"]
PARAM_OPT_ITERATIONS = _cfg["PARAM_OPT_ITERATIONS"]
PARAM_OPT_WEEKLY = _cfg["PARAM_OPT_WEEKLY"]
PARAM_OPT_MIN_IMPROVEMENT = _cfg["PARAM_OPT_MIN_IMPROVEMENT"]
PARAM_OPT_LOG_DIR = _cfg["PARAM_OPT_LOG_DIR"]
AUTO_PRE_TRAIN_LOG_DIR = _cfg["AUTO_PRE_TRAIN_LOG_DIR"]
