"""Shared auto-pre-train orchestration for short/middle pipelines.

This module contains all the shared logic for the training and prediction
monitoring loop.  Each variant (``auto_pre_train.py`` in ``short/`` and
``middle/``) provides a small ``VARIANT`` dict with the few parameters that
differ and then calls :func:`run_main` from this module.
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from threading import Event, Lock, Thread

import joblib
import numpy as np
import pandas as pd

from services.extreme_weather_detector import ExtremeWeatherDetector
from services.prediction_corrector import PredictionCorrector

# ---------------------------------------------------------------------------
# Module-level shared state
# ---------------------------------------------------------------------------
model_lock = Lock()
model_available = Event()
logger = logging.getLogger()

# These are set by the variant wrapper *before* any function is called.
# They mirror the values from the variant's config module.
LOG_DIR = None  # type: str | None

# Imported lazily by the variant wrapper via set_variant().
_predict_fn = None
_load_data = None
_preprocess_data = None
_split_data = None
_feature_engineering = None
_scale_data = None
_create_time_window = None
_filter_data_by_date = None
_update_training_csv_from_db = None
_get_lightgbm_params = None
_train_and_evaluate = None
_train_multiple_datasets = None
_save_predictions = None
_visualize_results = None

# Config values injected by variant
WINDOW_SIZE = None
TRAIN_RATIO = None
LAGS = None
OUTPUT_DIR_TRAIN = None
Today = None
PREC_SV_FOLDER = None
DATASET_FOLDER = None
MODEL_FOLDER = None
OUTPUT_DIR_PRE = None

# Variant descriptor dict (set by wrapper)
VARIANT = None  # type: dict | None


def set_variant(
    variant: dict,
    *,
    predict_fn,
    load_data, preprocess_data, split_data, feature_engineering,
    scale_data, create_time_window, filter_data_by_date,
    update_training_csv_from_db,
    get_lightgbm_params,
    train_and_evaluate, train_multiple_datasets, save_predictions,
    visualize_results,
    window_size, train_ratio, lags,
    output_dir_train, today,
    prec_sv_folder, dataset_folder, model_folder, output_dir_pre,
    auto_pre_train_log_dir,
):
    """Inject variant-specific functions and config into this module.

    This must be called by the wrapper *before* any other function.
    """
    global VARIANT, LOG_DIR
    global _predict_fn, _load_data, _preprocess_data, _split_data
    global _feature_engineering, _scale_data, _create_time_window
    global _filter_data_by_date, _update_training_csv_from_db
    global _get_lightgbm_params, _train_and_evaluate
    global _train_multiple_datasets, _save_predictions, _visualize_results
    global WINDOW_SIZE, TRAIN_RATIO, LAGS, OUTPUT_DIR_TRAIN, Today
    global PREC_SV_FOLDER, DATASET_FOLDER, MODEL_FOLDER, OUTPUT_DIR_PRE

    VARIANT = variant
    LOG_DIR = auto_pre_train_log_dir

    _predict_fn = predict_fn
    _load_data = load_data
    _preprocess_data = preprocess_data
    _split_data = split_data
    _feature_engineering = feature_engineering
    _scale_data = scale_data
    _create_time_window = create_time_window
    _filter_data_by_date = filter_data_by_date
    _update_training_csv_from_db = update_training_csv_from_db
    _get_lightgbm_params = get_lightgbm_params
    _train_and_evaluate = train_and_evaluate
    _train_multiple_datasets = train_multiple_datasets
    _save_predictions = save_predictions
    _visualize_results = visualize_results

    WINDOW_SIZE = window_size
    TRAIN_RATIO = train_ratio
    LAGS = lags
    OUTPUT_DIR_TRAIN = output_dir_train
    Today = today
    PREC_SV_FOLDER = prec_sv_folder
    DATASET_FOLDER = dataset_folder
    MODEL_FOLDER = model_folder
    OUTPUT_DIR_PRE = output_dir_pre

    # Setup logging
    logger.setLevel(logging.INFO)
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{Today}.log")
    formatter = logging.Formatter("%(asctime)s - %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')


# ---------------------------------------------------------------------------
# Flag-file helpers (identical across variants)
# ---------------------------------------------------------------------------

def get_train_flag_file(date_str):
    return os.path.join(LOG_DIR, f"{date_str}_train_done.flag")


def is_train_done(date_str):
    flag_file = get_train_flag_file(date_str)
    if os.path.exists(flag_file):
        logging.info(f"检测到{date_str}的训练已经执行过 (标志文件: {flag_file})")
        return True
    return False


def mark_train_done(date_str):
    flag_file = get_train_flag_file(date_str)
    with open(flag_file, 'w') as f:
        f.write(f'Training done for {date_str} on '
                f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    logging.info(f"训练完成，已创建标志文件: {flag_file}")


def get_predict_flag_file(date_str):
    return os.path.join(LOG_DIR, f"{date_str}_predict_done.flag")


def is_predict_done(date_str):
    flag_file = get_predict_flag_file(date_str)
    if os.path.exists(flag_file):
        logging.info(f"检测到{date_str}的预测已经执行过 (标志文件: {flag_file})")
        return True
    return False


def mark_predict_done(date_str):
    flag_file = get_predict_flag_file(date_str)
    with open(flag_file, 'w') as f:
        f.write(f'Prediction done for {date_str} on '
                f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    logging.info(f"预测完成，已创建标志文件: {flag_file}")


def print_section(title):
    separator = "=" * 80
    print(f"\n{separator}")
    print(f">>> {title} <<<")
    print(f"{separator}\n")
    logging.info(f"\n{separator}")
    logging.info(f">>> {title} <<<")
    logging.info(f"{separator}\n")


def is_model_available(model_folder_today):
    print(f"检查模型目录: {model_folder_today}")
    logging.info(f"检查模型目录: {model_folder_today}")
    best_models_dir = os.path.join(model_folder_today, 'best_models')

    if os.path.exists(best_models_dir):
        print(f"发现best_models目录: {best_models_dir}")
        logging.info(f"发现best_models目录: {best_models_dir}")
        for algo_type in ['GBDT', 'DART', 'GOSS']:
            model_file = os.path.join(best_models_dir, f'{algo_type}.joblib')
            if os.path.exists(model_file):
                print(f"✅ 发现{algo_type}模型文件: {model_file}")
                logging.info(f"发现{algo_type}模型文件: {model_file}")
                return True
            else:
                print(f"❌ 未找到{algo_type}模型文件")
                logging.info(f"未找到{algo_type}模型文件")
    else:
        print(f"未找到best_models目录，检查传统模型文件")
        logging.info(f"未找到best_models目录，检查传统模型文件")

    model_file = os.path.join(model_folder_today, 'model.joblib')
    exists = os.path.exists(model_file)
    if exists:
        print(f"✅ 发现传统模型文件: {model_file}")
        logging.info(f"发现传统模型文件: {model_file}")
    else:
        print(f"❌ 未找到任何可用模型文件")
        logging.info(f"未找到任何可用模型文件")
    return exists


# ---------------------------------------------------------------------------
# Path helpers (parameterised by variant)
# ---------------------------------------------------------------------------

def _csv_training_file(farm_code: str) -> str:
    """Return the training CSV path for the current variant."""
    if VARIANT["USE_FARM_CODE"]:
        return os.path.join(DATASET_FOLDER,
                            f'training_data_{VARIANT["TASK_TYPE"]}_{farm_code}.csv')
    return os.path.join(DATASET_FOLDER,
                        f'training_data_{VARIANT["TASK_TYPE"]}.csv')


def _model_folder_today(today_date: str, farm_code: str) -> str:
    """Return today's model directory path."""
    if VARIANT["USE_FARM_CODE"]:
        return os.path.join(MODEL_FOLDER, f'{today_date}_{farm_code}')
    return os.path.join(MODEL_FOLDER, today_date)


def _predict_input_file(tomorrow_date_str: str, farm_code: str) -> str:
    """Return the prediction input CSV path."""
    if VARIANT["USE_FARM_CODE"]:
        return os.path.join(PREC_SV_FOLDER,
                            f"predict_input_{tomorrow_date_str}_{farm_code}.csv")
    return os.path.join(PREC_SV_FOLDER,
                        f"predict_input_{tomorrow_date_str}.csv")


def _predict_output_dir(today_date: str, farm_code: str) -> str:
    """Return the prediction output directory path."""
    if VARIANT["USE_FARM_CODE"]:
        return os.path.join(OUTPUT_DIR_PRE, f'{today_date}_{farm_code}')
    return os.path.join(OUTPUT_DIR_PRE, today_date)


def _predict_output_file(output_dir: str, today_date: str,
                         farm_code: str) -> str:
    """Return the prediction output file path."""
    if VARIANT["USE_FARM_CODE"]:
        return os.path.join(output_dir,
                            f"predict_output_{today_date}_{farm_code}.csv")
    return os.path.join(output_dir,
                        f"predict_output_{today_date}.csv")


# ---------------------------------------------------------------------------
# Core training logic
# ---------------------------------------------------------------------------

def train_model(data_file_path, model_folder_today):
    """Execute model training and evaluation (using CSV file path)."""
    print_section("开始模型训练")
    window_size = WINDOW_SIZE
    lags = LAGS
    train_ratio = TRAIN_RATIO
    output_dir = OUTPUT_DIR_TRAIN

    for label, val in [("窗口大小", window_size), ("滞后特征数", lags),
                       ("训练集比例", train_ratio), ("输出目录", output_dir),
                       ("模型存储路径", model_folder_today)]:
        print(f"  - {label}: {val}")
        logging.info(f"  - {label}: {val}")
    logging.info(f"输出结果将保存到: {output_dir}")

    print_section("数据加载与预处理")
    print(f"加载数据文件: {data_file_path}")
    logging.info(f"加载数据文件: {data_file_path}")
    logging.info("开始加载和预处理数据...")

    data = _load_data(data_file_path)

    if data.empty:
        msg = f"从 CSV 文件加载的数据为空或加载失败，无法继续训练: {data_file_path}"
        print(f"❌ {msg}")
        logging.error(msg)
        return

    print(f"数据加载完成，共 {len(data)} 条记录")
    print(f"数据前5行预览: \n{data.head()}")
    logging.info(f"数据加载完成，共 {len(data)} 条记录")
    logging.info(f"数据前5行预览: \n{data.head()}")

    months_list = [None]

    if 'Timestamp' in data.columns:
        if not pd.api.types.is_datetime64_any_dtype(data['Timestamp']):
            data['Timestamp'] = pd.to_datetime(data['Timestamp'])

        earliest_date = data['Timestamp'].min()
        latest_date = data['Timestamp'].max()
        date_range_months = (
            (latest_date.year - earliest_date.year) * 12
            + latest_date.month - earliest_date.month
        )
        print(f"数据集时间范围: "
              f"{earliest_date.strftime('%Y-%m-%d')} 至 "
              f"{latest_date.strftime('%Y-%m-%d')}, 共 {date_range_months} 个月")
        logging.info(f"数据集时间范围: "
                     f"{earliest_date.strftime('%Y-%m-%d')} 至 "
                     f"{latest_date.strftime('%Y-%m-%d')}, 共 {date_range_months} 个月")

        optimized_months = [m for m in months_list
                            if m is None or m <= date_range_months]
        if len(optimized_months) < len(months_list):
            print(f"根据数据集实际时间范围({date_range_months}个月)，"
                  f"优化months_list: {months_list} -> {optimized_months}")
            logging.info(f"根据数据集实际时间范围({date_range_months}个月)，"
                         f"优化months_list: {months_list} -> {optimized_months}")
            months_list = optimized_months

    print(f"将使用以下时间段训练模型: {months_list}")
    logging.info(f"将使用以下时间段训练模型: {months_list}")

    try:
        print_section("开始多数据集训练")
        print("将使用多种时间跨度的数据训练模型...")
        logging.info("将使用多种时间跨度的数据训练模型...")

        training_output = _train_multiple_datasets(
            data, months_list, train_ratio, lags, window_size,
            model_folder_today)
        best_models_info = training_output['models']
        all_training_results = training_output['results']
        print("多数据集训练完成! 已为每种算法选择最佳模型")
        logging.info("多数据集训练完成! 已为每种算法选择最佳模型")

        for algo_type, model_info in best_models_info.items():
            if model_info['model'] is not None:
                months_desc = (f"{model_info['months']}个月"
                               if model_info['months'] else "全部数据")
                print(f"  - 最佳{algo_type}模型: "
                      f"使用{months_desc}数据, "
                      f"评分={model_info['score']:.4f}")
                logging.info(f"  - 最佳{algo_type}模型: "
                             f"使用{months_desc}数据, "
                             f"评分={model_info['score']:.4f}")

        # --- Register models to ModelRegistry ---
        _register_models_to_registry(best_models_info, model_folder_today)

        # --- Select global best model ---
        _select_global_best_model(best_models_info, model_folder_today)

        # Skip weight calculation
        print_section("跳过模型权重计算")
        logging.info("根据需求跳过模型权重计算步骤，将仅使用单个最佳模型进行预测。")

    except Exception as e:
        print_section("多数据集训练失败")
        logging.error("多数据集训练失败")
        print(f"❌ 错误信息: {str(e)}")
        logging.error(f"❌ 错误信息: {str(e)}")
        print("回退到传统的单一模型训练方法...")
        logging.info("回退到传统的单一模型训练方法...")

        _fallback_train(data, train_ratio, lags, window_size,
                        model_folder_today, output_dir)


def _register_models_to_registry(best_models_info, model_folder_today):
    """Register trained models to ModelRegistry."""
    try:
        from model_registry import ModelRegistry
        farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')
        registry = ModelRegistry()
        wfcapacity = float(os.environ.get('WF_CAPACITY', '779.0'))
        task_type = VARIANT["TASK_TYPE"]

        for algo_type, model_info_dict in best_models_info.items():
            if model_info_dict.get('model') is None:
                continue

            model_path = os.path.join(model_folder_today, 'best_models',
                                      f'{algo_type}.joblib')
            if not os.path.exists(model_path):
                best_dir = os.path.join(model_folder_today, 'best_models')
                os.makedirs(best_dir, exist_ok=True)
                model_path = os.path.join(best_dir, f'{algo_type}.joblib')
                joblib.dump(model_info_dict['model'], model_path)

            rmse = model_info_dict.get('rmse', model_info_dict.get('score'))
            if rmse is not None and rmse < 0:
                import numpy as np
                rmse = np.sqrt(-rmse)
            val_accuracy = (1 - (rmse / wfcapacity)
                            if rmse is not None and wfcapacity > 0
                            else None)

            registry.register(
                farm_code=farm_code,
                task_type=task_type,
                algorithm=f"lightgbm_{algo_type.lower()}",
                model_path=model_path,
                hyperparams=model_info_dict.get('params'),
                val_rmse=float(rmse) if rmse is not None else None,
                val_accuracy=(float(val_accuracy)
                              if val_accuracy is not None else None),
                training_samples=model_info_dict.get('training_samples'),
            )
            print(f"  ✅ 已注册 {algo_type} 模型到 ModelRegistry "
                  f"({task_type})")
            logging.info(f"已注册 %s 模型到 ModelRegistry (%s)",
                         algo_type, task_type)

        # Register quantile models — reuse the best point model's val_accuracy
        # so that quantile models pass _should_activate() and get activated.
        _best_algo_for_q = None
        _best_score_for_q = float('-inf')
        _best_val_accuracy_for_q = None
        for _at, _mi in best_models_info.items():
            if (_mi.get('model') is not None
                    and _mi.get('score', float('-inf')) > _best_score_for_q):
                _best_score_for_q = _mi['score']
                _best_algo_for_q = _at
                # Compute val_accuracy the same way as point models above
                _rmse_q = _mi.get('rmse', _mi.get('score'))
                if _rmse_q is not None and _rmse_q < 0:
                    import numpy as np
                    _rmse_q = np.sqrt(-_rmse_q)
                _best_val_accuracy_for_q = (
                    1 - (_rmse_q / wfcapacity)
                    if _rmse_q is not None and wfcapacity > 0
                    else None
                )

        quantile_model_dir = os.path.join(model_folder_today, 'best_models')
        for q_key in ['q05', 'q95']:
            q_path = os.path.join(quantile_model_dir,
                                  f'production_model_{q_key}.joblib')
            if os.path.exists(q_path):
                algo_label = (
                    f"{_best_algo_for_q.lower()}_{q_key}"
                    if _best_algo_for_q
                    else f"unknown_{q_key}"
                )
                registry.register(
                    farm_code=farm_code,
                    task_type=task_type,
                    algorithm=algo_label,
                    model_path=q_path,
                    val_accuracy=(float(_best_val_accuracy_for_q)
                                  if _best_val_accuracy_for_q is not None
                                  else None),
                )
                logging.info("已注册分位数模型 %s 到 ModelRegistry (%s, "
                             "val_accuracy=%.4f)",
                             q_key, task_type,
                             _best_val_accuracy_for_q or 0)
    except Exception as reg_e:
        print(f"  ⚠️ 模型注册失败（不影响训练结果）: {reg_e}")
        logging.warning(f"模型注册失败（不影响训练结果）: {reg_e}", exc_info=True)


def _select_global_best_model(best_models_info, model_folder_today):
    """Choose the overall best model and write a marker file."""
    print_section("选择全局最优模型")
    logging.info("选择全局最优模型")
    best_overall_score = float('-inf')
    best_overall_type = None

    for algo_type, model_info in best_models_info.items():
        if (model_info and model_info.get('model') is not None
                and 'score' in model_info):
            current_score = model_info['score']
            if current_score > best_overall_score:
                best_overall_score = current_score
                best_overall_type = algo_type

    if best_overall_type:
        print(f"✅ 全局最优模型类型为: {best_overall_type}，"
              f"评分为: {best_overall_score:.4f}")
        logging.info(f"✅ 全局最优模型类型为: {best_overall_type}，"
                     f"评分为: {best_overall_score:.4f}")
        marker_file_path = os.path.join(model_folder_today,
                                        'best_model_type.txt')
        try:
            with open(marker_file_path, 'w') as f:
                f.write(best_overall_type)
            print(f"✅ 全局最优模型类型已写入标记文件: {marker_file_path}")
            logging.info(f"✅ 全局最优模型类型已写入标记文件: "
                         f"{marker_file_path}")
        except IOError as e:
            print(f"❌ 写入最优模型标记文件失败: {e}")
            logging.error(f"❌ 写入最优模型标记文件失败: {e}")
    else:
        print("❌ 未能确定全局最优模型。")
        logging.error("❌ 未能确定全局最优模型。")


def _fallback_train(data, train_ratio, lags, window_size,
                    model_folder_today, output_dir):
    """Traditional single-model training fallback."""
    print_section("开始传统单一模型训练")
    logging.info("开始传统单一模型训练")
    print("使用全部数据进行预处理...")
    logging.info("使用全部数据进行预处理...")

    X, y = _preprocess_data(data)
    X_train, X_val, y_train, y_val = _split_data(X, y, train_ratio)
    print(f"数据集划分完成，训练集: {X_train.shape}, 验证集: {X_val.shape}")
    logging.info(f"数据集划分完成，训练集: {X_train.shape}, 验证集: {X_val.shape}")

    print("执行特征工程...")
    logging.info("执行特征工程...")
    X_train_fe, X_val_fe = _feature_engineering(X_train, X_val, lags)
    print(f"特征工程后的数据集大小 - 训练: {X_train_fe.shape}, "
          f"验证: {X_val_fe.shape}")
    logging.info(f"特征工程后的数据集大小 - 训练: {X_train_fe.shape}, "
                 f"验证: {X_val_fe.shape}")

    print("执行数据标准化...")
    logging.info("执行数据标准化...")
    X_train_scaled, X_val_scaled, scaler = _scale_data(X_train_fe, X_val_fe)
    print("数据标准化完成")
    logging.info("数据标准化完成")

    print(f"创建时间窗口，窗口大小: {window_size}...")
    logging.info(f"创建时间窗口，窗口大小: {window_size}...")
    X_train_windows, y_train_windows = _create_time_window(
        X_train_scaled, y_train.values, window_size)
    X_val_windows, y_val_windows = _create_time_window(
        X_val_scaled, y_val.values, window_size)
    print(f"时间窗口创建完成，窗口数量 - 训练: {len(X_train_windows)}, "
          f"验证: {len(X_val_windows)}")
    logging.info(f"时间窗口创建完成，窗口数量 - 训练: {len(X_train_windows)}, "
                 f"验证: {len(X_val_windows)}")

    print("获取模型参数...")
    logging.info("获取模型参数...")
    params_list = _get_lightgbm_params()
    print(f"模型参数获取完成，共 {len(params_list)} 种参数配置")
    logging.info(f"模型参数获取完成，共 {len(params_list)} 种参数配置")

    print_section("开始模型训练与评估")
    logging.info("开始模型训练与评估")
    print("训练3种不同的LightGBM模型: GBDT, DART, GOSS")
    logging.info("训练3种不同的LightGBM模型: GBDT, DART, GOSS")

    original_feature_names = (
        X_train.columns.tolist()
        if hasattr(X_train, 'columns')
        else [f'feature_{i}' for i in range(X_train.shape[1])]
    )
    flat_feature_names = []
    for i in range(window_size):
        time_lag_label = window_size - 1 - i
        for name in original_feature_names:
            flat_feature_names.append(f"{name}_t-{time_lag_label}")

    results_dict = _train_and_evaluate(
        X_train_windows, y_train_windows,
        X_val_windows, y_val_windows,
        params_list, scaler, model_folder_today,
        None, flat_feature_names,
        save_importance=True,
    )
    print("模型训练与评估完成!")
    logging.info("模型训练与评估完成!")
    for model_name, result in results_dict.items():
        print(f"  - {model_name}: RMSE={result['rmse']:.4f}, "
              f"K={result['k']:.4f}")
        logging.info(f"  - {model_name}: RMSE={result['rmse']:.4f}, "
                     f"K={result['k']:.4f}")

    print(f"保存预测结果到 {output_dir}...")
    logging.info(f"保存预测结果到 {output_dir}...")
    _save_predictions(results_dict, y_val_windows, output_base_dir=output_dir)
    print("预测结果保存完成")
    logging.info("预测结果保存完成")

    print("创建可视化结果...")
    logging.info("创建可视化结果...")
    _visualize_results(results_dict, y_val_windows, output_dir)
    print("可视化结果创建完成")
    logging.info("可视化结果创建完成")


# ---------------------------------------------------------------------------
# Training monitor
# ---------------------------------------------------------------------------

def monitor_training(today_date):
    """Monitor training process, update CSV before training."""
    farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')
    prefix = VARIANT["LOG_PREFIX"]

    print_section(f"启动训练监视线程{prefix} (场站: {farm_code})")
    logging.info(f"启动训练监视线程{prefix} (场站: {farm_code})")

    csv_file = _csv_training_file(farm_code)
    model_folder_today = _model_folder_today(today_date, farm_code)

    os.makedirs(model_folder_today, exist_ok=True)
    os.makedirs(DATASET_FOLDER, exist_ok=True)

    print(f"训练 CSV 文件路径: {csv_file}")
    print(f"模型存储目录: {model_folder_today}")
    print(f"训练完成标志文件: {get_train_flag_file(today_date)}")
    logging.info(f"训练 CSV 文件路径: {csv_file}")
    logging.info(f"模型存储目录: {model_folder_today}")
    logging.info(f"训练完成标志文件: {get_train_flag_file(today_date)}")
    logging.info("开始监视训练任务 (基于标志文件和 CSV 更新)...")

    while True:
        if is_train_done(today_date):
            print("⚠️ 检测到今天的训练已经执行过，跳过...")
            logging.info("⚠️ 检测到今天的训练已经执行过，跳过...")
            if is_model_available(model_folder_today):
                model_available.set()
                print("✅ (跳过训练后) 模型已设置为可用状态")
                logging.info("✅ (跳过训练后) 模型已设置为可用状态")
            break

        print(f"ℹ️ 尝试更新训练 CSV 文件: {csv_file}")
        logging.info(f"ℹ️ 尝试更新训练 CSV 文件: {csv_file}")
        update_successful = _update_training_csv_from_db(csv_file)

        if not update_successful:
            print("❌ 更新训练 CSV 文件失败，本次将跳过训练。请检查日志获取详细信息。")
            logging.error("❌ 更新训练 CSV 文件失败，本次将跳过训练。")
            break
        else:
            print("✅ CSV 文件更新检查完成。")
            logging.info("✅ CSV 文件更新检查完成。")

        if is_train_done(today_date):
            logging.info("在 CSV 更新后检测到训练已完成，跳过执行训练。")
            break

        print(f"ℹ️ 今天 ({today_date}) 的训练尚未完成，"
              f"开始执行训练 (使用 {csv_file})...")
        logging.info(f"ℹ️ 今天 ({today_date}) 的训练尚未完成，"
                     f"开始执行训练 (使用 {csv_file})...")
        with model_lock:
            train_model(csv_file, model_folder_today)

        mark_train_done(today_date)
        print("✅ 训练完成，已创建标志文件")
        logging.info("✅ 训练完成，已创建标志文件")

        if is_model_available(model_folder_today):
            model_available.set()
            print(f"✅ 模型已成功保存到 {model_folder_today}，模型可用。")
            logging.info(f"✅ 模型已成功保存到 {model_folder_today}，模型可用。")
        else:
            print(f"❌ 模型文件未找到在 {model_folder_today}，模型不可用。")
            logging.info(f"❌ 模型文件未找到在 {model_folder_today}，模型不可用。")
        break


# ---------------------------------------------------------------------------
# DB prediction input loader
# ---------------------------------------------------------------------------

def _try_load_from_db(farm_code, target_dt):
    """Try loading prediction input from the ECMWF table.

    Returns DataFrame or None on failure.
    """
    prefix = VARIANT["LOG_PREFIX"]
    try:
        from db_session import db_session
        from services.ecmwf_ingest_service import query_prediction_data

        start_time = target_dt - timedelta(hours=4)
        end_time = target_dt + timedelta(hours=VARIANT["TIME_HORIZON_HOURS"])

        with db_session() as session:
            df = query_prediction_data(
                db=session,
                farm_code=farm_code,
                start_time=start_time,
                end_time=end_time,
                data_type='DQ',
            )

        if df is not None and not df.empty:
            logging.info(f"DB查询成功{prefix}: {len(df)} rows "
                         f"for {target_dt.strftime('%Y%m%d')}")
            return df
        return None
    except Exception as e:
        logging.warning(f"DB预测输入加载失败{prefix}: {e}")
        return None


# ---------------------------------------------------------------------------
# Prediction monitor
# ---------------------------------------------------------------------------

def monitor_prediction(today_date):
    """Monitor prediction process, ensure prediction completes."""
    farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')
    prefix = VARIANT["LOG_PREFIX"]
    use_farm = VARIANT["USE_FARM_CODE"]

    print(f"开始监控预测过程{prefix}，日期: {today_date} "
          f"(将预测 {today_date} 的下一天), 场站: {farm_code}")
    logging.info(f"开始监控预测过程{prefix}，日期: {today_date} "
                 f"(将预测 {today_date} 的下一天), 场站: {farm_code}")

    if is_predict_done(today_date):
        print(f"今天 ({today_date}) 的预测任务已运行完成，无需再次执行")
        logging.info(f"今天 ({today_date}) 的预测任务已运行完成，无需再次执行")
        return

    try:
        today_dt = datetime.strptime(today_date, '%Y%m%d')
        tomorrow_dt = today_dt + timedelta(days=1)
        tomorrow_date_str = tomorrow_dt.strftime('%Y%m%d')
        print(f"将查找明天的预测输入文件，日期: {tomorrow_date_str}")
        logging.info(f"将查找明天的预测输入文件，日期: {tomorrow_date_str}")
    except ValueError:
        logging.error(f"无法解析日期: {today_date}，无法确定明天的输入文件名。")
        return

    model_folder_today = _model_folder_today(today_date, farm_code)
    max_wait_time = 7200
    wait_interval = 60
    start_time = time.time()

    print(f"等待今天的模型目录可用: {model_folder_today}")
    logging.info(f"等待今天的模型目录可用: {model_folder_today}")

    while True:
        if time.time() - start_time > max_wait_time:
            print("等待模型超时，预测任务终止")
            logging.error("等待模型超时，预测任务终止")
            return

        if is_predict_done(today_date):
            print(f"在等待期间，今天 ({today_date}) 的预测任务已完成，退出等待")
            logging.info(f"在等待期间，今天 ({today_date}) 的预测任务已完成，"
                         "退出等待")
            return

        if not os.path.exists(model_folder_today):
            print(f"今天的模型目录不存在，等待 {wait_interval} 秒后重试...")
            logging.info(f"今天的模型目录不存在，等待 {wait_interval} 秒后重试...")
            time.sleep(wait_interval)
            continue

        if not is_model_available(model_folder_today):
            print(f"今天的模型目录中没有可用的模型文件，"
                  f"等待 {wait_interval} 秒后重试...")
            logging.info(f"今天的模型目录中没有可用的模型文件，"
                         f"等待 {wait_interval} 秒后重试...")
            time.sleep(wait_interval)
            continue

        csv_file = _predict_input_file(tomorrow_date_str, farm_code)
        if not os.path.exists(csv_file):
            db_prediction_enabled = (
                os.environ.get('DB_PREDICTION_ENABLED', 'false').lower()
                == 'true'
            )
            if db_prediction_enabled:
                db_df = _try_load_from_db(farm_code, tomorrow_dt)
                if db_df is not None and not db_df.empty:
                    os.makedirs(PREC_SV_FOLDER, exist_ok=True)
                    db_df.to_csv(csv_file, index=False)
                    print(f"✅ 从数据库加载预测输入成功{prefix}，"
                          f"已保存到: {csv_file}")
                    logging.info(f"从数据库加载预测输入成功{prefix}，"
                                 f"已保存到: {csv_file}")
                else:
                    print(f"数据库中也无数据，等待 {wait_interval} 秒后重试")
                    logging.info(f"数据库中也无数据，等待 {wait_interval} "
                                 "秒后重试")
                    time.sleep(wait_interval)
                    continue
            else:
                farm_label = f"_{farm_code}" if use_farm else ""
                print(f"明天的预测输入文件 ({tomorrow_date_str}{farm_label}) "
                      f"不存在，等待 {wait_interval} 秒后重试: {csv_file}")
                logging.info(f"明天的预测输入文件 "
                             f"({tomorrow_date_str}{farm_label}) 不存在，"
                             f"等待 {wait_interval} 秒后重试: {csv_file}")
                time.sleep(wait_interval)
                continue

        print(f"✅ 发现明天的预测文件：{csv_file}，使用今天的模型执行预测{prefix}...")
        logging.info(f"✅ 发现明天的预测文件：{csv_file}，"
                     f"使用今天的模型执行预测{prefix}...")

        # Check production model and type file
        _check_production_model(model_folder_today)

        # Create output directory
        output_dir = _predict_output_dir(today_date, farm_code)
        os.makedirs(output_dir, exist_ok=True)
        output_file = _predict_output_file(output_dir, today_date, farm_code)

        print(f"输出文件将保存到: {output_file}")
        logging.info(f"输出文件将保存到: {output_file}")

        predict_success = False
        try:
            combined_pred, pred_timestamps = _predict_fn(
                input_file=csv_file,
                models_dir=model_folder_today,
                output_file=output_file,
                window_size=WINDOW_SIZE,
                lags=LAGS,
            )

            if combined_pred is not None and pred_timestamps is not None:
                # --- Extreme weather detection + correction ---
                try:
                    input_df = pd.read_csv(csv_file)
                    ecmwf_features = _extract_ecmwf_features_for_detection(
                        input_df
                    )
                    detector = ExtremeWeatherDetector()
                    conditions = [detector.detect(row) for row in ecmwf_features]
                    active = detector.get_active_conditions(conditions)

                    if active:
                        capacity = float(
                            os.environ.get('WF_CAPACITY', '779.0')
                        )
                        pred_array = np.asarray(combined_pred, dtype=float)
                        # Pad conditions if prediction has more timesteps
                        if len(pred_array) > len(conditions):
                            conditions_extended = conditions + [
                                conditions[-1]
                            ] * (len(pred_array) - len(conditions))
                        else:
                            conditions_extended = conditions[:len(pred_array)]

                        corrector = PredictionCorrector()
                        corrected, correction_records = corrector.correct(
                            pred_array, conditions_extended, capacity
                        )
                        combined_pred = corrected.tolist()

                        summary = corrector.get_correction_summary(
                            correction_records
                        )
                        logging.info(
                            "极端天气校正完成: %d corrections / %d predictions, "
                            "by_type=%s",
                            summary["total_corrections"],
                            len(pred_array),
                            summary["by_type"],
                        )
                        print(f"⚠️ 极端天气校正: "
                              f"{summary['total_corrections']} corrections "
                              f"applied, types: {summary['by_type']}")

                        # Re-save corrected predictions to output file
                        try:
                            result_df = pd.read_csv(output_file)
                            if len(result_df) == len(combined_pred):
                                # Find the power column
                                power_col = None
                                for col_name in ('power', 'Power',
                                                 'predicted_power',
                                                 'prediction'):
                                    if col_name in result_df.columns:
                                        power_col = col_name
                                        break
                                if power_col is None:
                                    power_col = result_df.columns[-1]
                                result_df[power_col] = combined_pred
                                result_df.to_csv(output_file, index=False)
                                logging.info(
                                    "校正后预测结果已覆盖保存到 %s",
                                    output_file,
                                )
                            else:
                                logging.warning(
                                    "输出文件行数(%d)与校正结果(%d)不匹配，"
                                    "跳过覆盖保存",
                                    len(result_df),
                                    len(combined_pred),
                                )
                        except Exception as save_err:
                            logging.warning(
                                "校正后结果保存失败（不影响预测完成标记）: %s",
                                save_err,
                            )

                        _inject_extreme_weather_alarms(active, farm_code)
                    else:
                        logging.info("未检测到极端天气条件，预测结果无需校正")
                except Exception as ew_err:
                    logging.warning(
                        "极端天气检测/校正失败（不影响预测结果）: %s",
                        ew_err,
                    )

                predict_success = True
                print(f"✅ 预测成功完成，结果已保存到 {output_file}")
                logging.info(f"✅ 预测成功完成，结果已保存到 {output_file}")
            else:
                print("❌ predict 函数未成功返回结果，跳过标记完成")
                logging.error("❌ predict 函数未成功返回结果，跳过标记完成")
        except Exception as e:
            print(f"❌ 调用 predict 函数时发生意外错误: {e}")
            logging.error(f"❌ 调用 predict 函数时发生意外错误: {e}")
            import traceback
            traceback.print_exc()
            logging.error(traceback.format_exc())

        if predict_success:
            mark_predict_done(today_date)
            print(f"✅ 今天 ({today_date}) 的预测执行完成")
            logging.info(f"✅ 今天 ({today_date}) 的预测执行完成")
        else:
            print("❌ 预测未成功执行或失败，不标记完成")
            logging.error("❌ 预测未成功执行或失败，不标记完成")

        break

    print(f"预测监控结束{prefix} ({today_date})")
    logging.info(f"预测监控结束{prefix} ({today_date})")


def _check_production_model(model_folder_today):
    """Check for production model and best-model-type marker file."""
    production_model_path = os.path.join(model_folder_today, 'best_models',
                                         'production_model.joblib')
    best_model_type_path = os.path.join(model_folder_today,
                                        'best_model_type.txt')

    prod_model_exists = os.path.exists(production_model_path)
    type_file_content = None
    if os.path.exists(best_model_type_path):
        try:
            with open(best_model_type_path, 'r') as f:
                type_file_content = f.read().strip()
        except Exception as e:
            logging.error(f"读取 best_model_type.txt 文件失败: {e}")

    if prod_model_exists and type_file_content == "production_model":
        print("✅ 检测到生产模型 (production_model.joblib) 存在，"
              "且类型文件正确标记。预测将优先使用生产模型。")
        logging.info("✅ 检测到生产模型 (production_model.joblib) 存在，"
                     "且类型文件正确标记。预测将优先使用生产模型。")
    elif prod_model_exists and type_file_content != "production_model":
        print(f"⚠️ 检测到生产模型存在，但类型文件标记为 "
              f"'{type_file_content}'。预测行为将取决于 predict 函数的内部逻辑。")
        logging.warning(f"⚠️ 检测到生产模型存在，但类型文件标记为 "
                        f"'{type_file_content}'。预测行为将取决于 predict "
                        "函数的内部逻辑。")
    elif not prod_model_exists and type_file_content == "production_model":
        print("⚠️ 类型文件标记为 'production_model'，"
              "但生产模型文件缺失！预测行为将取决于 predict 函数的内部逻辑"
              "（可能失败或回退）。")
        logging.warning("⚠️ 类型文件标记为 'production_model'，"
                        "但生产模型文件缺失！预测行为将取决于 predict "
                        "函数的内部逻辑（可能失败或回退）。")
    else:
        print(f"ℹ️ 未检测到生产模型，或类型文件标记为 "
              f"'{type_file_content}'。预测将尝试使用评估阶段的最佳模型。")
        logging.info(f"ℹ️ 未检测到生产模型，或类型文件标记为 "
                     f"'{type_file_content}'。预测将尝试使用评估阶段的"
                     "最佳模型。")


# ---------------------------------------------------------------------------
# Extreme weather detection helpers
# ---------------------------------------------------------------------------

def _extract_ecmwf_features_for_detection(input_df: pd.DataFrame) -> list[dict]:
    """Extract averaged ECMWF meteorological features for extreme weather detection.

    For each row in *input_df*, computes averaged values across grid-point
    columns and returns a list of dicts suitable for
    :meth:`ExtremeWeatherDetector.detect`.

    Parameters
    ----------
    input_df:
        DataFrame containing ECMWF columns such as ``ws100_1..ws100_15``,
        ``2t_23.8_103.2``, ``tcwv_*``, etc.

    Returns
    -------
    list[dict]
        One dict per row with keys ``ws100_avg``, ``temp_2t_avg``,
        ``tcwv_avg``, ``temp_24h_drop``.
    """
    import re

    ws100_cols = [c for c in input_df.columns
                  if re.match(r'^ws100_\d', c)]
    temp_2t_cols = [c for c in input_df.columns if c.startswith('2t_')]
    tcwv_cols = [c for c in input_df.columns if c.startswith('tcwv_')]

    def _safe_mean(row: pd.Series, cols: list[str]) -> float:
        """Average of *cols* for one row, skipping NaN/None."""
        if not cols:
            return 0.0
        vals = row[cols]
        numeric = vals.dropna()
        if numeric.empty:
            return 0.0
        return float(numeric.mean())

    results: list[dict] = []
    for _, row in input_df.iterrows():
        results.append({
            "ws100_avg": _safe_mean(row, ws100_cols),
            "temp_2t_avg": _safe_mean(row, temp_2t_cols),
            "tcwv_avg": _safe_mean(row, tcwv_cols),
            "temp_24h_drop": 0.0,
        })
    return results


def _inject_extreme_weather_alarms(conditions: list, farm_code: str) -> None:
    """Create alarm records for warning/danger weather conditions.

    Parameters
    ----------
    conditions:
        List of :class:`WeatherCondition` instances.
    farm_code:
        Wind farm identifier.

    This is a best-effort operation -- failures are logged but never
    propagated, so the prediction pipeline is never broken by alarm issues.
    """
    alarming = [c for c in conditions
                if c.severity in ("warning", "danger")]
    if not alarming:
        return

    try:
        from db_session import db_session
        from db_models.alarm import AlarmRecord

        with db_session() as session:
            for cond in alarming:
                msg = (f"[极端天气] 类型={cond.condition_type}, "
                       f"严重级别={cond.severity}, "
                       f"详情={cond.details}")
                record = AlarmRecord(
                    source="extreme_weather",
                    farm_code=farm_code,
                    module="prediction",
                    level=cond.severity,
                    message=msg,
                    status="open",
                )
                session.add(record)
        logging.info("已注入 %d 条极端天气告警 (场站: %s)",
                     len(alarming), farm_code)
    except Exception as alarm_err:
        logging.warning("极端天气告警注入失败（不影响预测结果）: %s",
                        alarm_err)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_main(*, has_farm_code_arg=False):
    """Run the main training/prediction orchestration.

    Parameters
    ----------
    has_farm_code_arg : bool
        If *True* (short variant), accept ``--farm_code`` CLI argument.
        If *False* (middle variant), skip it.
    """
    prefix = VARIANT["LOG_PREFIX"]
    thread_suffix = VARIANT["THREAD_NAME_SUFFIX"]

    parser = argparse.ArgumentParser(
        description="Auto Pre-Train script for short/middle term models.")
    parser.add_argument("--mode", type=str,
                        choices=['train', 'predict', 'all'],
                        default='all',
                        help="Run mode: 'train' for training only, "
                             "'predict' for prediction only, "
                             "'all' for both.")
    if has_farm_code_arg:
        parser.add_argument("--farm_code", type=str, default='DEFAULT_FARM',
                            help="Farm code for multi-farm support "
                                 "(DEFAULT_FARM, zyx01, zyx02, etc.)")
    args = parser.parse_args()

    # Validate farm code (short only)
    if has_farm_code_arg:
        valid_farm_codes = ['DEFAULT_FARM', 'zyx01', 'zyx02']
        if args.farm_code not in valid_farm_codes:
            print(f"无效的场站代码: {args.farm_code}，"
                  f"有效场站: {valid_farm_codes}")
            logging.error(f"无效的场站代码: {args.farm_code}，"
                          f"有效场站: {valid_farm_codes}")
            return
        farm_code = args.farm_code
    else:
        farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')

    print_section(f"自动训练预测系统启动{prefix} - 模式: {args.mode.upper()}, "
                  f"场站: {farm_code}")
    logging.info(f"自动训练预测系统启动{prefix} - 模式: {args.mode.upper()}, "
                 f"场站: {farm_code}")
    today_date = Today
    print(f"今天的日期是: {today_date}")
    logging.info(f"今天的日期是: {today_date}")

    if has_farm_code_arg:
        os.environ['FARM_CODE'] = args.farm_code
        print(f"设置环境变量 FARM_CODE = {args.farm_code}")
        logging.info(f"设置环境变量 FARM_CODE = {args.farm_code}")

    train_thread = None
    predict_thread = None

    if args.mode in ('train', 'all'):
        print(f"创建训练监视线程{prefix}...")
        logging.info(f"创建训练监视线程{prefix}...")
        train_thread = Thread(
            target=monitor_training, args=(today_date,),
            name=f"TrainThread{thread_suffix}")
        print(f"启动训练线程{prefix}...")
        logging.info(f"启动训练线程{prefix}...")
        train_thread.start()
        if args.mode == 'train':
            print(f"等待训练线程完成{prefix}...")
            logging.info(f"等待训练线程完成{prefix}...")
            train_thread.join()
            print_section(f"训练模式完成{prefix}")
            logging.info(f"训练模式完成{prefix}")
            return

    if args.mode in ('predict', 'all'):
        if (args.mode == 'all' and train_thread is not None
                and train_thread.is_alive()):
            print(f"模式 'all': 等待训练线程完成{prefix}才能安全开始预测...")
            logging.info(f"模式 'all': 等待训练线程完成{prefix}"
                         "才能安全开始预测...")
            train_thread.join()

        print(f"创建预测监视线程{prefix}...")
        logging.info(f"创建预测监视线程{prefix}...")
        predict_thread = Thread(
            target=monitor_prediction, args=(today_date,),
            name=f"PredictThread{thread_suffix}")
        print(f"启动预测线程{prefix}...")
        logging.info(f"启动预测线程{prefix}...")
        predict_thread.start()
        if args.mode == 'predict':
            print(f"等待预测线程完成{prefix}...")
            logging.info(f"等待预测线程完成{prefix}...")
            predict_thread.join()
            print_section(f"预测模式完成{prefix}")
            logging.info(f"预测模式完成{prefix}")
            return

    if args.mode == 'all':
        if train_thread is not None and train_thread.is_alive():
            train_thread.join()
        if predict_thread is not None and predict_thread.is_alive():
            print(f"模式 'all': 等待预测线程完成{prefix}...")
            logging.info(f"模式 'all': 等待预测线程完成{prefix}...")
            predict_thread.join()

    print_section(f"系统任务完成{prefix} (基于模式)")
    logging.info(f"系统任务完成{prefix} (基于模式)")
