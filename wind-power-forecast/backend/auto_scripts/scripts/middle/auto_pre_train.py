# merged_auto_script.py — middle-term (72h) variant
import os
import logging
import sys

# --- Dynamically Add Project Root to sys.path ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logging.info(f"(auto_pre_train) 将项目根目录添加到 sys.path: {project_root}")
    print(f"DEBUG: Calculated project_root: {project_root}")
    print(f"DEBUG: Current sys.path: {sys.path}")
    logging.info(f"DEBUG: Calculated project_root: {project_root}")
    logging.info(f"DEBUG: Current sys.path: {sys.path}")
except Exception as path_e:
    logging.error(f"(auto_pre_train) 动态计算项目根目录时出错: {path_e}", exc_info=True)

# Ensure parent directory is importable for base modules
_parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Variant-specific imports
from predict_middle import predict
from data_processor_middle import (
    load_data,
    preprocess_data,
    split_data,
    feature_engineering,
    scale_data,
    create_time_window,
    filter_data_by_date,
    update_training_csv_from_db,
)
from models_middle import get_lightgbm_params, get_unified_params
from train_middle import train_and_evaluate, train_multiple_datasets, calculate_model_weights, save_predictions
from utils_middle import visualize_results
from config_middle import (
    WINDOW_SIZE, TRAIN_RATIO, LAGS, OUTPUT_DIR_TRAIN, Today,
    PREC_SV_FOLDER, DATASET_FOLDER, MODEL_FOLDER, OUTPUT_DIR_PRE,
    AUTO_PRE_TRAIN_LOG_DIR,
)

from config_base import VARIANT_PARAMS

# Import the shared base and wire everything together
from auto_pre_train_base import set_variant, run_main

set_variant(
    variant={
        "TASK_TYPE": "medium",
        "TIME_HORIZON_HOURS": 72,
        "USE_FARM_CODE": True,
        "LOG_PREFIX": "(中期)",
        "THREAD_NAME_SUFFIX": "-Middle",
    },
    predict_fn=predict,
    load_data=load_data,
    preprocess_data=preprocess_data,
    split_data=split_data,
    feature_engineering=feature_engineering,
    scale_data=scale_data,
    create_time_window=create_time_window,
    filter_data_by_date=filter_data_by_date,
    update_training_csv_from_db=update_training_csv_from_db,
    get_lightgbm_params=get_lightgbm_params,
    train_and_evaluate=train_and_evaluate,
    train_multiple_datasets=train_multiple_datasets,
    save_predictions=save_predictions,
    visualize_results=visualize_results,
    window_size=WINDOW_SIZE,
    train_ratio=TRAIN_RATIO,
    lags=LAGS,
    output_dir_train=OUTPUT_DIR_TRAIN,
    today=Today,
    prec_sv_folder=PREC_SV_FOLDER,
    dataset_folder=DATASET_FOLDER,
    model_folder=MODEL_FOLDER,
    output_dir_pre=OUTPUT_DIR_PRE,
    auto_pre_train_log_dir=AUTO_PRE_TRAIN_LOG_DIR,
)


def main():
    """Middle-term main entry point (accepts --farm_code)."""
    run_main(has_farm_code_arg=True)


if __name__ == '__main__':
    main()
