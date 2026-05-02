# predict_middle.py
import os
import pandas as pd
import numpy as np
import joblib
import logging
import sys
import datetime
import json
import gc  # 添加垃圾回收模块
import requests # Added for API calls
import io # Added for sending DataFrame as file
from data_processor_middle import (
    preprocess_data_pre, filter_data_by_date,
    create_time_window_pre, scale_data, feature_engineering,
    create_flattened_windows_pre
)
from config_middle import LAGS, OUTPUT_DIR_PRE, Today, FEATURE_IMPORTANCE_DIR
import pickle

# 获取logger
logger = logging.getLogger()

# 添加控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 添加scripts目录到sys.path以导入utils_base
_current_file_dir = os.path.dirname(os.path.abspath(__file__))
_path_to_scripts = os.path.abspath(os.path.join(_current_file_dir, '..'))
if _path_to_scripts not in sys.path:
    sys.path.insert(0, _path_to_scripts)

from utils_base import get_farm_capacity

# 处理Windows控制台输出编码
if sys.platform == 'win32':
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    # 确保stderr也使用utf-8编码
    sys.stderr.reconfigure(encoding='utf-8')

# Read API base URL from environment variable, default to localhost for local dev
API_BASE_URL = os.environ.get("BACKEND_API_URL", "http://localhost:5000")
logger.info(f"Using Backend API Base URL: {API_BASE_URL}") # Log the URL being used

def upload_dataframe_to_api(df, endpoint, target_table=None, file_field_name='file', filename='upload.csv', farm_code=None):
    """
    Uploads a pandas DataFrame as a CSV file to a specified API endpoint.

    Args:
        df (pd.DataFrame): The DataFrame to upload.
        endpoint (str): The API endpoint path (e.g., '/api/upload_feature_csv').
        target_table (str, optional): The target table name for feature uploads. Defaults to None.
        file_field_name (str): The name of the form field for the file. Defaults to 'file'.
        filename (str): The filename to use for the uploaded data. Defaults to 'upload.csv'.

    Returns:
        bool: True if the upload was successful (status code 2xx), False otherwise.
    """
    upload_url = f"{API_BASE_URL}{endpoint}"
    logger.info(f"准备上传数据到: {upload_url}")
    if df.empty:
        logger.warning(f"DataFrame 为空, 跳过上传到 {endpoint}。")
        return False

    try:
        # Convert DataFrame to CSV in memory
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        files = {file_field_name: (filename, csv_buffer, 'text/csv')}
        data = {}
        if target_table:
            data['table_name'] = target_table
        if farm_code:
            data['farm_code'] = farm_code

        response = requests.post(upload_url, files=files, data=data)

        if 200 <= response.status_code < 300:
            logger.info(f"成功上传数据到 {endpoint}. 状态码: {response.status_code}")
            try:
                logger.info(f"响应: {response.json()}")
            except requests.exceptions.JSONDecodeError:
                logger.info(f"响应: {response.text}")
            return True
        else:
            logger.error(f"上传数据到 {endpoint} 失败. 状态码: {response.status_code}")
            try:
                logger.error(f"响应: {response.json()}")
            except requests.exceptions.JSONDecodeError:
                logger.error(f"响应: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"连接 API 端点 {endpoint} 时出错: {e}")
        return False
    except Exception as e:
        logger.error(f"上传到 {endpoint} 时发生意外错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def print_separator(msg=None):
    """打印分隔符"""
    print("\n" + "-" * 50)
    if msg:
        print(f"【{msg}】")
    if msg:
        logger.info(f"\n{'-' * 50}\n【{msg}】\n{'-' * 50}")
    else:
        logger.info(f"\n{'-' * 50}")

def print_memory_usage():
    """打印当前内存使用情况"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        print(f"当前内存占用: {memory_mb:.2f} MB")
        logger.info(f"当前内存占用: {memory_mb:.2f} MB")
        return memory_mb
    except ImportError:
        print("psutil未安装，无法跟踪内存使用情况")
        logger.info("psutil未安装，无法跟踪内存使用情况")
        return 0

def get_top_features(algo_type, top_n=3000, current_date=None):
    """
    获取算法类型对应的特征重要性文件中的前N个重要特征

    参数:
    algo_type: 算法类型 ('GBDT', 'DART', 'GOSS')
    top_n: 要选择的前N个重要特征数量
    current_date: 当前日期，用于日志记录

    返回:
    top_features: 选择的特征名称列表
    selected_indices: 选择的特征索引列表 (原始列表中的索引)
    """
    # 确保feature_importance目录存在
    if not os.path.exists(FEATURE_IMPORTANCE_DIR):
        print(f"❌ 特征重要性目录不存在: {FEATURE_IMPORTANCE_DIR}")
        logger.error(f"❌ 特征重要性目录不存在: {FEATURE_IMPORTANCE_DIR}")
        return None, None

    importance_file = os.path.join(FEATURE_IMPORTANCE_DIR, f'{algo_type}_feature_importance.pkl')

    if not os.path.exists(importance_file):
        print(f"❌ 特征重要性文件不存在: {importance_file}")
        logger.error(f"❌ 特征重要性文件不存在: {importance_file}")
        return None, None

    # 检查文件日期是否新鲜(如果传入了current_date)
    if current_date:
        try:
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(importance_file))
            file_date_str = file_mtime.strftime("%Y%m%d")

            # 检查日期格式 - 支持YYYYMMDD格式
            if len(file_date_str) == 8 and file_date_str.isdigit():
                if file_date_str < current_date:
                    days_old = (datetime.datetime.strptime(current_date, "%Y%m%d") - file_mtime).days
                    print(f"⚠️ 特征重要性文件 {importance_file} 创建于 {file_date_str}，已过期 {days_old} 天")
                    logger.warning(f"⚠️ 特征重要性文件 {importance_file} 创建于 {file_date_str}，已过期 {days_old} 天")
        except Exception as e:
            print(f"⚠️ 检查特征重要性文件日期时出错: {str(e)}")
            logger.warning(f"⚠️ 检查特征重要性文件日期时出错: {str(e)}")

    try:
        # 加载特征重要性
        with open(importance_file, 'rb') as f:
            feature_importance = pickle.load(f)

        # 修正：检查正确的键名
        if not isinstance(feature_importance, dict) or 'features' not in feature_importance or 'importances' not in feature_importance:
            print(f"❌ 特征重要性文件格式错误或缺少键: {importance_file}. 需要 'features' 和 'importances'")
            logger.error(f"❌ 特征重要性文件格式错误或缺少键: {importance_file}. 需要 'features' 和 'importances'")
            return None, None

        # 修正：使用正确的键名加载
        all_features_list = feature_importance['features']  # 加载原始特征列表
        importances = feature_importance['importances']    # 加载重要性分数

        # 确保特征名称和重要性长度一致
        if len(all_features_list) != len(importances):
            print(f"❌ 特征列表数量 ({len(all_features_list)}) 与重要性分数数量 ({len(importances)}) 不匹配 in {importance_file}")
            logger.error(f"❌ 特征列表数量 ({len(all_features_list)}) 与重要性分数数量 ({len(importances)}) 不匹配 in {importance_file}")
            return None, None

        # 创建 DataFrame 用于排序
        importance_df = pd.DataFrame({
            'feature': all_features_list,
            'importance': importances
        }).sort_values(by='importance', ascending=False)

        # 选择TOP N个特征的名字
        top_n = min(top_n, len(importance_df))
        top_features_names = importance_df.head(top_n)['feature'].tolist()

        # 获取这些Top N特征在原始特征列表中的索引
        selected_indices = []
        missing_features_in_list = []
        # 创建一个查找字典以提高效率
        feature_to_index = {name: i for i, name in enumerate(all_features_list)}

        for feature_name in top_features_names:
            idx = feature_to_index.get(feature_name)
            if idx is not None:
                selected_indices.append(idx)
            else:
                # 这个情况理论上不应发生，如果发生了说明文件内部不一致
                missing_features_in_list.append(feature_name)
                print(f"⚠️ [get_top_features] 重要特征 '{feature_name}' 在原始特征列表中未找到索引，将被跳过")
                logger.warning(f"⚠️ [get_top_features] 重要特征 '{feature_name}' 在原始特征列表中未找到索引，将被跳过")

        if not selected_indices:  # 如果一个索引都没找到
            print(f"❌ [get_top_features] 没有有效的特征索引被选中 ({algo_type})")
            logger.error(f"❌ [get_top_features] 没有有效的特征索引被选中 ({algo_type})")
            return None, None  # 返回 None 表示失败

        # 按原始顺序排序索引，这对于LGBM等模型很重要
        selected_indices.sort()

        print(f"✅ 已从 {importance_file} 加载并选择前 {len(selected_indices)} 个重要特征索引")
        logger.info(f"✅ 已从 {importance_file} 加载并选择前 {len(selected_indices)} 个重要特征索引")

        # 返回选择的特征名列表和索引列表
        return top_features_names, selected_indices

    except Exception as e:
        print(f"❌ 加载或处理特征重要性文件时出错 ({importance_file}): {str(e)}")
        logger.error(f"❌ 加载或处理特征重要性文件时出错 ({importance_file}): {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None

def load_models_and_scalers(models_dir_base, model_types=None):
    """
    加载最优模型和对应的标准化器。
    优先尝试：
    1. 首先检查是否存在生产模型 production_model.joblib
    2. 然后检查是否存在 best_model_type.txt 文件并加载该文件指定的模型
    3. 如果未找到上述文件或加载失败，尝试加载传统的单一模型 model.joblib

    参数:
    models_dir_base: 模型基础目录
    model_types: 模型类型列表（已弃用，保留参数仅为兼容性）

    返回:
    models: 模型字典，键为模型类型，值为模型对象
    scalers: 标准化器字典，键为模型类型，值为标准化器对象
    """
    models = {}
    scalers = {}

    if not os.path.exists(models_dir_base):
        print(f"❌ 模型目录 {models_dir_base} 不存在")
        logger.error(f"❌ 模型目录 {models_dir_base} 不存在")
        return {}, {}

    # 列出目录内容以帮助诊断
    print(f"📂 模型目录内容 ({models_dir_base}):")
    logger.info(f"📂 模型目录内容 ({models_dir_base}):")
    try:
        dir_contents = os.listdir(models_dir_base)
        for item in dir_contents:
            print(f"  - {item}")
            logger.info(f"  - {item}")

        if not dir_contents:
            print(f"⚠️ 模型目录为空！")
            logger.warning(f"⚠️ 模型目录为空！")
            return {}, {}
    except Exception as e:
        print(f"❌ 读取模型目录内容时出错: {str(e)}")
        logger.error(f"❌ 读取模型目录内容时出错: {str(e)}")

    # 第零步: 检查是否存在生产模型文件
    best_models_dir = os.path.join(models_dir_base, 'best_models')
    if os.path.exists(best_models_dir):
        print(f"检查生产模型...")
        logger.info(f"检查生产模型...")

        production_model_path = os.path.join(best_models_dir, 'production_model.joblib')
        production_scaler_path = os.path.join(best_models_dir, 'production_scaler.joblib')

        if os.path.exists(production_model_path) and os.path.exists(production_scaler_path):
            print(f"✅ 发现生产模型文件: {production_model_path}")
            logger.info(f"✅ 发现生产模型文件: {production_model_path}")
            try:
                models['production_model'] = joblib.load(production_model_path)
                scalers['production_model'] = joblib.load(production_scaler_path)
                print(f"✅ 成功加载生产模型和标准化器")
                logger.info(f"✅ 成功加载生产模型和标准化器")
                return models, scalers
            except Exception as e:
                print(f"❌ 加载生产模型时出错: {str(e)}")
                logger.error(f"❌ 加载生产模型时出错: {str(e)}")
                # 继续尝试其他模型
        else:
            if not os.path.exists(production_model_path):
                print(f"生产模型文件不存在: {production_model_path}")
                logger.info(f"生产模型文件不存在: {production_model_path}")
            if not os.path.exists(production_scaler_path):
                print(f"生产标准化器文件不存在: {production_scaler_path}")
                logger.info(f"生产标准化器文件不存在: {production_scaler_path}")

    # 第一步: 尝试从 best_model_type.txt 加载最优模型
    best_model_type_path = os.path.join(models_dir_base, 'best_model_type.txt')
    if os.path.exists(best_model_type_path):
        try:
            with open(best_model_type_path, 'r') as f:
                best_model_type = f.read().strip()

            print(f"✅ 从标记文件读取到最优模型类型: {best_model_type}")
            logger.info(f"✅ 从标记文件读取到最优模型类型: {best_model_type}")

            # 特殊处理 "production_model" 标记
            if best_model_type == "production_model":
                print(f"检测到生产模型标记，尝试加载生产模型...")
                logger.info(f"检测到生产模型标记，尝试加载生产模型...")

                # 已在第零步尝试过，如果能到这里，说明加载失败了
                print(f"⚠️ 标记文件指示使用生产模型，但在第一步中未能加载生产模型，将尝试其他模型")
                logger.warning(f"⚠️ 标记文件指示使用生产模型，但在第一步中未能加载生产模型，将尝试其他模型")
                # 继续尝试加载传统模型
            else:
                # Check best_models directory
                best_models_dir = os.path.join(models_dir_base, 'best_models')
                if os.path.exists(best_models_dir):
                    print(f"📂 Found best_models directory: {best_models_dir}")

                    # Build paths for best model and scaler
                    model_path = os.path.join(best_models_dir, f"{best_model_type}.joblib")
                    scaler_path = os.path.join(best_models_dir, f"{best_model_type}_scaler.joblib")

                    if os.path.exists(model_path) and os.path.exists(scaler_path):
                        try:
                            models[best_model_type] = joblib.load(model_path)
                            scalers[best_model_type] = joblib.load(scaler_path)
                            print(f"✅ 成功加载最优模型 {best_model_type} 及其标准化器")
                            logger.info(f"✅ 成功加载最优模型 {best_model_type} 及其标准化器")
                            return models, scalers
                        except Exception as e:
                            print(f"❌ 加载最优模型 {best_model_type} 时出错: {str(e)}")
                            logger.error(f"❌ 加载最优模型 {best_model_type} 时出错: {str(e)}")
                            # 继续尝试加载传统模型
                    else:
                        print(f"❌ 最优模型或其标准化器文件不存在")
                        logger.error(f"❌ 最优模型或其标准化器文件不存在")
                        # 继续尝试加载传统模型
                else:
                    print(f"❌ best_models 目录不存在: {best_models_dir}")
                    logger.error(f"❌ best_models 目录不存在: {best_models_dir}")
                    # 继续尝试加载传统模型
        except Exception as e:
            print(f"❌ 读取最优模型类型文件时出错: {str(e)}")
            logger.error(f"❌ 读取最优模型类型文件时出错: {str(e)}")
            # 继续尝试加载传统模型
    else:
        print(f"⚠️ 未找到最优模型类型标记文件: {best_model_type_path}")
        logger.warning(f"⚠️ 未找到最优模型类型标记文件: {best_model_type_path}")

    # 第二步: 尝试加载传统的单一模型
    print(f"尝试加载传统模式下的单一模型...")
    logger.info(f"尝试加载传统模式下的单一模型...")

    model_path = os.path.join(models_dir_base, 'model.joblib')
    scaler_path = os.path.join(models_dir_base, 'scaler.joblib')

    print(f"🔍 检查传统模型文件: {model_path}")
    logger.info(f"🔍 检查传统模型文件: {model_path}")
    print(f"🔍 检查传统标准化器文件: {scaler_path}")
    logger.info(f"🔍 检查传统标准化器文件: {scaler_path}")

    if os.path.exists(model_path) and os.path.exists(scaler_path):
        print("🔄 加载传统 model.joblib...")
        logger.info("🔄 加载传统 model.joblib...")
        try:
            models['model'] = joblib.load(model_path)
            scalers['model'] = joblib.load(scaler_path)
            print(f"✅ 成功加载传统模型和标准化器")
            logger.info(f"✅ 成功加载传统模型和标准化器")
            return models, scalers
        except Exception as e:
            print(f"❌ 加载传统模型时出错: {str(e)}")
            logger.error(f"❌ 加载传统模型时出错: {str(e)}")
    else:
        if not os.path.exists(model_path):
            print(f"❌ 传统模型文件不存在: {model_path}")
            logger.warning(f"❌ 传统模型文件不存在: {model_path}")
        if not os.path.exists(scaler_path):
            print(f"❌ 传统标准化器文件不存在: {scaler_path}")
            logger.warning(f"❌ 传统标准化器文件不存在: {scaler_path}")

    # 如果没有成功加载任何模型
    print(f"❌ 未能加载任何可用模型")
    logger.error(f"❌ 未能加载任何可用模型")
    return {}, {}


# ---------------------------------------------------------------------------
# Sub-functions extracted from predict() for maintainability (Sprint 3)
# ---------------------------------------------------------------------------

def _create_flattened_windows(X_scaled, window_size, original_indices):
    """
    Create flattened 2D windows from scaled data for prediction.

    For each window of `window_size` consecutive rows, flattens all features
    into a single 1D vector. Returns the flattened array and the original-data
    index that corresponds to the *last* row of each window (the prediction
    target time-step).

    Args:
        X_scaled: DataFrame or 2D array of scaled features.
        window_size: Number of consecutive time-steps per window.
        original_indices: Array mapping each row back to the original data index.

    Returns:
        X_flat: np.ndarray of shape (num_windows, window_size * num_features).
        target_indices: np.ndarray of original-data indices for each window's target.
    """
    num_samples = len(X_scaled) - window_size + 1
    if num_samples <= 0:
        raise ValueError(
            f"数据不足 ({len(X_scaled)} 行) 无法创建大小为 {window_size} 的窗口。"
        )

    num_features = X_scaled.shape[1]
    X_flat = np.zeros((num_samples, window_size * num_features), dtype=np.float32)
    target_indices = np.zeros(num_samples, dtype=original_indices.dtype)

    for i in range(num_samples):
        window = X_scaled[i : i + window_size]
        X_flat[i] = window.values.reshape(1, -1)
        target_index_in_scaled_data = i + window_size - 1
        target_indices[i] = original_indices[target_index_in_scaled_data]

    return X_flat, target_indices


def _determine_prediction_model(models_dir, model_types=None):
    """
    Determine and load the best available prediction model and its scaler.

    Resolution order:
    1. Production model (production_model.joblib)
    2. Best model type marker (best_model_type.txt)
    3. Fallback to parameter/default model type
    4. Legacy root-directory model.joblib

    Args:
        models_dir: Root directory containing model files.
        model_types: Optional list of model type names (uses first as fallback).

    Returns:
        Tuple of (model, scaler, determined_model_type, model_file_path).
        Returns (None, None, None, None) if no model could be loaded.
    """
    print_separator("确定要加载的模型")
    logger.info("确定要加载的模型...")

    determined_model_type = None
    model_to_load = None
    scaler_to_load = None
    model_file_path = None

    best_models_subdir = os.path.join(models_dir, 'best_models')

    # 优先加载 production model
    prod_model_path = os.path.join(best_models_subdir, 'production_model.joblib')
    prod_scaler_path = os.path.join(best_models_subdir, 'production_scaler.joblib')

    if os.path.exists(prod_model_path) and os.path.exists(prod_scaler_path):
        logger.info(f"✅ 发现并尝试加载生产模型: {prod_model_path}")
        try:
            model_to_load = joblib.load(prod_model_path)
            scaler_to_load = joblib.load(prod_scaler_path)
            determined_model_type = "production_model"
            model_file_path = prod_model_path
            logger.info("✅ 成功加载生产模型和标准化器")
        except Exception as e:
            logger.error(f"❌ 加载生产模型或标准化器时出错: {e}，将尝试其他模型...")
            model_to_load = None
            scaler_to_load = None

    # 如果生产模型加载失败或不存在，尝试 best_model_type.txt
    if model_to_load is None:
        best_model_type_path = os.path.join(models_dir, 'best_model_type.txt')
        if os.path.exists(best_model_type_path):
            try:
                with open(best_model_type_path, 'r') as f:
                    best_type = f.read().strip()
                logger.info(f"✅ 从标记文件读取到最优模型类型: {best_type}")

                if best_type != "production_model":
                    best_model_path = os.path.join(best_models_subdir, f"{best_type}.joblib")
                    best_scaler_path = os.path.join(best_models_subdir, f"{best_type}_scaler.joblib")

                    if os.path.exists(best_model_path) and os.path.exists(best_scaler_path):
                        logger.info(f"尝试加载最优模型 {best_type}: {best_model_path}")
                        try:
                            model_to_load = joblib.load(best_model_path)
                            scaler_to_load = joblib.load(best_scaler_path)
                            determined_model_type = best_type
                            model_file_path = best_model_path
                            logger.info(f"✅ 成功加载最优模型 {best_type} 和其标准化器")
                        except Exception as e:
                            logger.error(f"❌ 加载最优模型 {best_type} 时出错: {e}，将尝试后续逻辑...")
                            model_to_load = None
                            scaler_to_load = None
                    else:
                        logger.warning(f"标记文件指定的最优模型 {best_type} 或其 scaler 不存在，将尝试后续逻辑...")
            except Exception as e:
                logger.error(f"❌ 读取或处理 best_model_type.txt 时出错: {e}，将尝试后续逻辑...")

    # 如果上面都没成功，再看参数或默认值
    if model_to_load is None:
        if model_types and len(model_types) > 0:
            fallback_model_type = model_types[0]
            logger.info(f"使用参数指定的模型类型: {fallback_model_type}")
        else:
            fallback_model_type = "GOSS"
            logger.info(f"未指定模型类型，默认使用: {fallback_model_type}")

        fallback_model_path = os.path.join(best_models_subdir, f"{fallback_model_type}.joblib")
        fallback_scaler_path = os.path.join(best_models_subdir, f"{fallback_model_type}_scaler.joblib")

        if os.path.exists(fallback_model_path) and os.path.exists(fallback_scaler_path):
            logger.info(f"尝试从 best_models 加载模型 {fallback_model_type}: {fallback_model_path}")
            try:
                model_to_load = joblib.load(fallback_model_path)
                scaler_to_load = joblib.load(fallback_scaler_path)
                determined_model_type = fallback_model_type
                model_file_path = fallback_model_path
                logger.info(f"✅ 成功加载模型 {fallback_model_type} 和其标准化器")
            except Exception as e:
                logger.error(f"❌ 从 best_models 加载模型 {fallback_model_type} 时出错: {e}，将尝试从根目录加载...")
                model_to_load = None
                scaler_to_load = None
        else:
            logger.warning(f"在 best_models 中未找到模型 {fallback_model_type} 或其 scaler，尝试从根目录加载...")
            fallback_model_path_root = os.path.join(models_dir, f"{fallback_model_type}.joblib")
            fallback_scaler_path_root = os.path.join(models_dir, f"{fallback_model_type}_scaler.joblib")
            if os.path.exists(fallback_model_path_root) and os.path.exists(fallback_scaler_path_root):
                logger.info(f"尝试从根目录加载模型 {fallback_model_type}: {fallback_model_path_root}")
                try:
                    model_to_load = joblib.load(fallback_model_path_root)
                    scaler_to_load = joblib.load(fallback_scaler_path_root)
                    determined_model_type = fallback_model_type
                    model_file_path = fallback_model_path_root
                    logger.info(f"✅ 成功从根目录加载模型 {fallback_model_type} 和其标准化器")
                except Exception as e:
                    logger.error(f"❌ 从根目录加载模型 {fallback_model_type} 时出错: {e}")
                    model_to_load = None
                    scaler_to_load = None

    if model_to_load is None or scaler_to_load is None:
        logger.error("❌ 错误: 未能成功加载任何有效的模型和标准化器组合。无法继续预测。")
        print("❌ 错误: 未能成功加载任何有效的模型和标准化器组合。")
        return None, None, None, None

    return model_to_load, scaler_to_load, determined_model_type, model_file_path


def _resolve_importance_file(models_dir, determined_model_type):
    """
    Resolve the feature importance file path for the given model type.

    For production_model, checks for a dedicated importance file first, then
    falls back to the original model type recorded in best_model_type.txt.

    Args:
        models_dir: Root directory containing model files.
        determined_model_type: The model type that was actually loaded.

    Returns:
        Absolute path to the importance .pkl file, or None if not found.
    """
    if determined_model_type == "production_model":
        prod_importance_path = os.path.join(FEATURE_IMPORTANCE_DIR, 'production_model_feature_importance.pkl')
        if os.path.exists(prod_importance_path):
            logger.info(f"使用生产模型特征重要性文件: {prod_importance_path}")
            return prod_importance_path

        try:
            with open(os.path.join(models_dir, 'best_model_type.txt'), 'r') as f:
                original_model_type = f.read().strip()
            if original_model_type != "production_model":
                fallback_importance_path = os.path.join(
                    FEATURE_IMPORTANCE_DIR, f'{original_model_type}_feature_importance.pkl'
                )
                if os.path.exists(fallback_importance_path):
                    logger.info(
                        f"生产模型特征重要性文件不存在，回退到原始模型 {original_model_type} 的特征重要性文件: {fallback_importance_path}"
                    )
                    return fallback_importance_path
                logger.error(f"❌ 无法找到生产模型或原始模型 {original_model_type} 的特征重要性文件")
                return None
            else:
                logger.error("❌ best_model_type.txt 指向 production_model，但找不到特征重要性文件")
                return None
        except Exception as e:
            logger.error(f"❌ 尝试回退到原始模型特征重要性时出错: {e}")
            return None

    importance_file = os.path.join(
        FEATURE_IMPORTANCE_DIR, f'{determined_model_type}_feature_importance.pkl'
    )
    logger.info(f"将使用特征重要性文件: {importance_file}")
    return importance_file


def _load_selected_features(importance_file, top_n):
    """
    Load a feature importance .pkl file and return the names of the top-N features.

    Args:
        importance_file: Path to the .pkl file with keys 'features' and 'importances'.
        top_n: Maximum number of top features to select.

    Returns:
        List of selected feature name strings, or None on failure.
    """
    print_separator("加载特征重要性")
    logger.info(f"从 {importance_file} 加载特征重要性...")

    if not os.path.exists(importance_file):
        logger.error(f"❌ 错误: 特征重要性文件不存在: {importance_file}")
        return None

    try:
        with open(importance_file, 'rb') as f:
            feature_importance_dict = pickle.load(f)

        feature_importance_df = pd.DataFrame({
            'feature': feature_importance_dict['features'],
            'importance': feature_importance_dict['importances']
        }).sort_values(by='importance', ascending=False)

        selected_feature_names = feature_importance_df.head(top_n)['feature'].tolist()
        logger.info(f"成功加载并处理特征重要性。预期 {len(selected_feature_names)} 个特征。")
        return selected_feature_names
    except Exception as e:
        logger.error(f"加载或处理特征重要性文件时出错: {e}")
        logger.error("无法继续，因为不知道训练时选择了哪些特征。")
        return None


def _load_quantile_models(models_dir):
    """
    Load the 5th and 95th percentile quantile models if available.

    Args:
        models_dir: Root directory containing model files.

    Returns:
        Tuple of (model_q05, model_q95). Either may be None if not found.
    """
    model_q05 = None
    model_q95 = None
    try:
        q05_path = os.path.join(models_dir, 'best_models', 'production_model_q05.joblib')
        q95_path = os.path.join(models_dir, 'best_models', 'production_model_q95.joblib')
        if os.path.exists(q05_path):
            model_q05 = joblib.load(q05_path)
            logging.info("已加载 5%% 分位数模型: %s", q05_path)
        if os.path.exists(q95_path):
            model_q95 = joblib.load(q95_path)
            logging.info("已加载 95%% 分位数模型: %s", q95_path)
    except Exception as qe:
        logging.warning("分位数模型加载失败（不影响点预测）: %s", qe)
    return model_q05, model_q95


def _preprocess_input_data(input_file, max_lag, wind_speeds_10, wind_speeds_100,
                           wind_speeds_200, base_wind_features):
    """
    Load the input CSV, engineer features, and handle NaN rows from lag features.

    Steps performed:
    1. Read CSV and validate required columns.
    2. Parse timestamps and extract time features (Year, Month, Day, Hour).
    3. Sort by timestamp.
    4. Build combined wind-speed difference features.
    5. Build lag features for base wind features.
    6. Drop rows with NaN (introduced by lag shifts) and track valid indices.

    Args:
        input_file: Path to the input feature CSV.
        max_lag: Maximum lag order for lag feature generation.
        wind_speeds_10: List of ws10 column names.
        wind_speeds_100: List of ws100 column names.
        wind_speeds_200: List of ws200 column names.
        base_wind_features: Combined list of all wind speed column names.

    Returns:
        Dict with keys:
            X_new_with_features (pd.DataFrame): Feature-engineered data (NaN dropped).
            new_data (pd.DataFrame): Original data (Timestamp parsed, time cols added).
            original_timestamps (pd.Series): All original timestamps before NaN drop.
            valid_original_indices (np.ndarray): Indices into original data for valid rows.
            engineered_feature_names (list[str]): Column names after feature engineering.
        Returns None on failure.
    """
    print_separator("加载并预处理数据")
    logger.info(f"从 {input_file} 加载新数据...")

    try:
        new_data = pd.read_csv(input_file)
    except FileNotFoundError:
        logger.error(f"❌ 错误: 预测数据文件不存在: {input_file}")
        return None

    logger.info(f"初始数据形状: {new_data.shape}")

    required_columns = ['Timestamp'] + base_wind_features
    missing_cols = [col for col in required_columns if col not in new_data.columns]
    if missing_cols:
        logger.error(f"❌ 错误: 新数据中缺少必需的列: {missing_cols}")
        return None

    logger.info("预处理新数据...")

    new_data['Timestamp'] = pd.to_datetime(new_data['Timestamp'])
    new_data['Year'] = new_data['Timestamp'].dt.year
    new_data['Month'] = new_data['Timestamp'].dt.month
    new_data['Day'] = new_data['Timestamp'].dt.day
    new_data['Hour'] = new_data['Timestamp'].dt.hour

    new_data = new_data.sort_values(by='Timestamp').reset_index(drop=True)
    original_timestamps = new_data['Timestamp'].copy()

    features_to_use = [col for col in new_data.columns if col not in ['Timestamp', 'wp_true']]
    X_new = new_data[features_to_use].copy()

    for col in X_new.select_dtypes(include=['float64']).columns:
        X_new[col] = X_new[col].astype(np.float32)

    for col in ['Year', 'Month', 'Day', 'Hour']:
        if col in X_new.columns and X_new[col].dtype == 'int64':
            X_new[col] = X_new[col].astype(np.int32)

    logger.info(f"初始处理后的形状: {X_new.shape}")

    print_separator("特征工程")
    logger.info("应用特征工程...")
    combined_features_new = {}
    for wind_speeds in [wind_speeds_100, wind_speeds_200]:
        for i in range(len(wind_speeds)):
            for j in range(i + 1, len(wind_speeds)):
                if wind_speeds[i] in X_new.columns and wind_speeds[j] in X_new.columns:
                    combined_features_new[f'{wind_speeds[i]}_{wind_speeds[j]}_diff1'] = (
                        X_new[wind_speeds[i]] - X_new[wind_speeds[j]]
                    )

    for wind_speeds in [wind_speeds_10]:
        for i in range(len(wind_speeds)):
            for k in range(len(wind_speeds_200)):
                if wind_speeds[i] in X_new.columns and wind_speeds_200[k] in X_new.columns:
                    combined_features_new[f'{wind_speeds[i]}_{wind_speeds_200[k]}_diff2'] = (
                        X_new[wind_speeds[i]] - X_new[wind_speeds_200[k]]
                    )

    lag_features_new = {}
    lag_cols_to_check = base_wind_features
    for lag in range(1, max_lag + 1):
        for col in lag_cols_to_check:
            if col in X_new.columns:
                lag_features_new[f'{col}_lag{lag}'] = X_new[col].shift(lag)

    combined_features_df_new = pd.DataFrame(combined_features_new, index=X_new.index).astype(np.float32)
    lag_features_df_new = pd.DataFrame(lag_features_new, index=X_new.index).astype(np.float32)
    X_new_with_features = pd.concat([X_new, combined_features_df_new, lag_features_df_new], axis=1)

    logger.info(f"特征工程后的形状: {X_new_with_features.shape}")

    engineered_feature_names = X_new_with_features.columns.tolist()
    logger.info(f"特征工程后的特征数量: {len(engineered_feature_names)}")

    initial_row_count = len(X_new_with_features)
    X_new_with_features = X_new_with_features.dropna().reset_index(drop=True)
    final_row_count = len(X_new_with_features)
    logger.info(f"删除NaN后的形状: {X_new_with_features.shape} (删除了 {initial_row_count - final_row_count} 行)")

    if final_row_count == 0:
        logger.error("❌ 错误: 删除NaN后没有剩余数据。输入数据可能太短，无法处理滞后特征。")
        return None

    valid_original_indices = np.arange(final_row_count) + (initial_row_count - final_row_count)

    return {
        'X_new_with_features': X_new_with_features,
        'new_data': new_data,
        'original_timestamps': original_timestamps,
        'valid_original_indices': valid_original_indices,
        'engineered_feature_names': engineered_feature_names,
    }


def _prepare_prediction_features(X_new_with_features, scaler, window_size,
                                 valid_original_indices, original_timestamps,
                                 engineered_feature_names, selected_feature_names):
    """
    Scale features, create time windows, and select top-N important features.

    Args:
        X_new_with_features: Feature-engineered DataFrame (NaN already dropped).
        scaler: Fitted scaler object.
        window_size: Number of time-steps per window.
        valid_original_indices: Array mapping rows to original data indices.
        original_timestamps: Full timestamp Series from original data.
        engineered_feature_names: Column names after feature engineering.
        selected_feature_names: Names of the top-N features to select.

    Returns:
        Dict with keys:
            X_selected (np.ndarray): Final feature matrix ready for prediction.
            prediction_timestamps (np.ndarray): Timestamps for each prediction row.
        Returns None on failure.
    """
    # --- 缩放特征 ---
    print_separator("标准化数据")
    logger.info("使用加载的标准化器缩放特征...")

    try:
        if hasattr(scaler, 'feature_names_in_'):
            logger.info("标准化器具有特征名称，尝试对齐列。")
            X_new_with_features = X_new_with_features[scaler.feature_names_in_]
            logger.info("列已对齐。")
        else:
            logger.warning("警告: 标准化器对象没有'feature_names_in_'属性。假设当前列顺序正确。")

        X_new_scaled = scaler.transform(X_new_with_features).astype(np.float32)
    except ValueError as e:
        logger.error(f"❌ 标准化过程中出错: {e}")
        logger.error("这可能是由于训练和预测之间的特征列/顺序不匹配导致的。")
        logger.error(f"标准化器预期的特征（如果可用）: {getattr(scaler, 'feature_names_in_', '不可用')}")
        logger.error(f"当前数据的特征: {X_new_with_features.columns.tolist()}")
        return None

    logger.info(f"标准化后的形状: {X_new_scaled.shape}")

    del X_new_with_features
    gc.collect()

    # --- 创建时间窗口 ---
    print_separator("创建时间窗口")
    logger.info(f"创建时间窗口（大小 {window_size}）...")

    X_new_flat, target_indices_from_windows = _create_flattened_windows(
        pd.DataFrame(X_new_scaled), window_size, valid_original_indices
    )
    logger.info(f"窗口化后的形状: {X_new_flat.shape}")

    prediction_timestamps = original_timestamps.iloc[target_indices_from_windows].values

    del X_new_scaled
    gc.collect()

    # --- 特征选择 ---
    print_separator("特征选择")
    logger.info(f"根据加载的重要性应用特征选择（前 {len(selected_feature_names)} 个）...")

    flat_feature_names_full = []
    for i in range(window_size):
        time_lag_label = window_size - 1 - i
        for name in engineered_feature_names:
            flat_feature_names_full.append(f"{name}_t-{time_lag_label}")

    logger.info(f"生成的扁平化特征总数: {len(flat_feature_names_full)}")

    try:
        selected_indices = [flat_feature_names_full.index(fname) for fname in selected_feature_names]
    except ValueError as e:
        logger.error(f"❌ 在生成的完整特征列表中查找所选特征时出错: {e}")
        logger.error("这可能意味着本脚本中的特征工程或命名与训练脚本不同。")
        logger.error("或者，加载的重要性文件与'engineered_feature_names'不匹配。")
        return None

    X_new_flat_selected = X_new_flat[:, selected_indices]
    logger.info(f"特征选择后的形状: {X_new_flat_selected.shape}")

    if X_new_flat_selected.shape[1] != len(selected_feature_names):
        logger.error(
            f"❌ 错误: 选择后特征数量不匹配。预期 {len(selected_feature_names)}, "
            f"得到 {X_new_flat_selected.shape[1]}"
        )
        return None

    del X_new_flat
    gc.collect()

    return {
        'X_selected': X_new_flat_selected,
        'prediction_timestamps': prediction_timestamps,
    }


def _run_prediction(model, X_selected, determined_model_type, model_file_path,
                    model_q05=None, model_q95=None):
    """
    Execute point prediction and optional quantile interval prediction.

    When quantile models are available, enforces the constraint
    lower <= point_prediction <= upper, clipped to [0, capacity].

    Args:
        model: The main prediction model.
        X_selected: Feature matrix (already selected).
        determined_model_type: String label for logging.
        model_file_path: Path string for logging.
        model_q05: Optional 5th-percentile model.
        model_q95: Optional 95th-percentile model.

    Returns:
        Dict with keys:
            predictions (np.ndarray): Point predictions.
            predictions_lower (np.ndarray or None): Lower bound of 90% interval.
            predictions_upper (np.ndarray or None): Upper bound of 90% interval.
    """
    print_separator("模型预测")
    logger.info(f"使用模型进行预测 ({determined_model_type} - 来自 {model_file_path})")
    logger.info(f"即将为模型 {determined_model_type} 开始预测。")
    predictions = model.predict(X_selected)
    logger.info(f"生成了 {len(predictions)} 个预测值。")

    predictions_lower = None
    predictions_upper = None
    if model_q05 is not None and model_q95 is not None:
        try:
            wfcapacity = get_farm_capacity(os.environ.get('FARM_CODE', 'DEFAULT_FARM'))
            predictions_lower = np.asarray(model_q05.predict(X_selected))
            predictions_upper = np.asarray(model_q95.predict(X_selected))
            predictions_lower = np.minimum(predictions_lower, predictions)
            predictions_upper = np.maximum(predictions_upper, predictions)
            predictions_lower = np.clip(predictions_lower, 0, wfcapacity)
            predictions_upper = np.clip(predictions_upper, 0, wfcapacity)
            logging.info("已生成 90%% 预测区间")
        except Exception as qe:
            logging.warning("分位数预测失败（不影响点预测）: %s", qe)
            predictions_lower = None
            predictions_upper = None

    return {
        'predictions': predictions,
        'predictions_lower': predictions_lower,
        'predictions_upper': predictions_upper,
    }


def _save_and_upload_results(predictions, prediction_timestamps, output_file,
                             determined_model_type, new_data, original_timestamps,
                             predictions_lower=None, predictions_upper=None):
    """
    Format predictions as a DataFrame, save to CSV, upload via API, and save JSON details.

    Mid-term specific:
    - Uploads features at indices [192:288] to 'train_pre_middle'.
    - Uploads predictions from index 192 onwards to '/prediction2database/batch_mid_power'.

    Args:
        predictions: Array of point predictions.
        prediction_timestamps: Array of timestamps for each prediction.
        output_file: Path to save the prediction CSV.
        determined_model_type: Model type label for JSON output.
        new_data: Original (preprocessed) input DataFrame for feature upload.
        original_timestamps: Full timestamp Series from original data.
        predictions_lower: Optional array of lower interval bounds.
        predictions_upper: Optional array of upper interval bounds.
    """
    print_separator("保存预测结果")
    logger.info("格式化并保存预测结果...")

    if len(prediction_timestamps) != len(predictions):
        logger.error(
            f"❌ 错误: 时间戳 ({len(prediction_timestamps)}) 和预测值 ({len(predictions)}) 长度不匹配。"
        )
        logger.error("作为备用方案，将只保存没有时间戳的预测。")
        predictions_df = pd.DataFrame({'Predicted_Power': predictions})
    else:
        result_data = {
            'Timestamp': prediction_timestamps,
            'Predicted_Power': predictions
        }
        if predictions_lower is not None and predictions_upper is not None:
            result_data['Lower_90'] = predictions_lower
            result_data['Upper_90'] = predictions_upper
        predictions_df = pd.DataFrame(result_data)
        predictions_df = predictions_df.sort_values(by='Timestamp')

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    predictions_df.to_csv(output_file, index=False)
    logger.info(f"✅ 预测结果已保存到 {output_file}")

    # --- 上传输入特征 (中间期：取索引 192~288) ---
    print_separator("上传输入特征 (最后96个预测点)")
    if len(prediction_timestamps) >= 288:
        last_96_timestamps = prediction_timestamps[192:288]
        if not pd.api.types.is_datetime64_any_dtype(new_data['Timestamp']):
            new_data['Timestamp'] = pd.to_datetime(new_data['Timestamp'])

        input_features_to_upload = new_data[new_data['Timestamp'].isin(last_96_timestamps)].copy()

        if not input_features_to_upload.empty:
            logger.info(f"准备上传 {len(input_features_to_upload)} 行对应的原始输入特征到 train_pre_middle...")
            upload_success_features = upload_dataframe_to_api(
                df=input_features_to_upload,
                endpoint='/api/upload_feature_csv',
                target_table='train_pre_middle',
                filename=f'input_features_{Today}_{datetime.datetime.now().strftime("%H%M%S")}.csv'
            )
            if upload_success_features:
                logger.info("✅ 成功触发输入特征上传。")
            else:
                logger.error("❌ 输入特征上传失败。")
        else:
            logger.warning("未能找到与最后96个预测时间戳匹配的原始输入数据，跳过特征上传。")
    else:
        logger.warning(f"预测数量 ({len(prediction_timestamps)}) 少于96个，跳过输入特征上传。")

    # --- 上传预测结果 (中期：仅上传从索引192开始的数据) ---
    print_separator("上传预测结果")
    logger.info("准备上传预测结果到 /prediction2database/batch_mid_power...")
    try:
        predictions_for_upload = pd.read_csv(output_file)

        # 中期预测只上传从第193行开始的数据 (0-indexed: 192)
        if len(predictions_for_upload) > 192:
            predictions_for_upload = predictions_for_upload.iloc[192:].copy()
            logger.info(f"已筛选 predictions_for_upload，保留从索引192开始的 {len(predictions_for_upload)} 行数据用于上传。")
        else:
            logger.warning(f"predictions_for_upload 的行数 ({len(predictions_for_upload)}) 不足193行，将上传所有行或为空（如果筛选后为空）。")

        if 'Predicted_Power' in predictions_for_upload.columns:
            predictions_for_upload.rename(columns={'Predicted_Power': 'Predicted Power'}, inplace=True)
            logger.info("已将 'Predicted_Power' 列重命名为 'Predicted Power'")
            if 'Lower_90' in predictions_for_upload.columns and 'Upper_90' in predictions_for_upload.columns:
                predictions_for_upload['Lower 90'] = predictions_for_upload['Lower_90']
                predictions_for_upload['Upper 90'] = predictions_for_upload['Upper_90']
        else:
            logger.warning("在预测结果文件中未找到 'Predicted_Power' 列，请检查文件内容和目标API要求。")

        if 'Timestamp' not in predictions_for_upload.columns:
            logger.error("❌ 预测结果文件中缺少 'Timestamp' 列，无法上传。")
        else:
            upload_success_predictions = upload_dataframe_to_api(
                df=predictions_for_upload,
                endpoint='/prediction2database/batch_mid_power',
                filename=os.path.basename(output_file),
                farm_code=os.environ.get('FARM_CODE', os.environ.get('DEFAULT_FARM_CODE', 'DEFAULT_FARM'))
            )
            if upload_success_predictions:
                logger.info("✅ 成功触发预测结果上传。")
            else:
                logger.error("❌ 预测结果上传失败。")

    except FileNotFoundError:
        logger.error(f"❌ 无法找到预测结果文件 {output_file} 进行上传。")
    except Exception as e:
        logger.error(f"❌ 处理或上传预测结果时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # --- 输出详细JSON结果 ---
    json_output_file = os.path.splitext(output_file)[0] + '_details.json'
    try:
        def convert_numpy_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"无法JSON序列化类型: {type(obj)}")

        predictions_dict = {determined_model_type: predictions.tolist()}
        with open(json_output_file, 'w') as f:
            json.dump(predictions_dict, f, indent=2, default=convert_numpy_types)
        logger.info(f"✅ 详细预测结果已保存到 {json_output_file}")
    except Exception as json_e:
        logger.error(f"❌ 保存详细JSON时发生错误: {json_e}")


# ---------------------------------------------------------------------------
# Main predict() orchestrator
# ---------------------------------------------------------------------------

def predict(input_file, models_dir, output_file, window_size=16, lags=4, model_types=None, weights=None, months_back=None):
    """
    预测风电功率，使用单个最优模型

    参数:
    input_file: 输入特征文件路径
    models_dir: 模型目录路径
    output_file: 输出预测结果文件路径
    window_size: 时间窗口大小
    lags: 滞后特征数
    model_types: 要使用的模型类型列表，None表示使用所有可用模型
    weights: 已弃用，保留参数仅为兼容性
    months_back: 只使用最近几个月的数据，None表示使用所有数据

    返回:
    combined_pred: 单个模型的预测结果
    timestamps: 对应的时间戳
    """
    print_separator("开始预测风电功率")
    print(f"输入文件: {input_file}")
    print(f"模型目录: {models_dir}")
    print(f"输出文件: {output_file}")
    print(f"窗口大小: {window_size}")
    print(f"滞后特征数: {lags}")
    print(f"模型类型: {model_types}")
    if weights:
        print(f"警告: 权重参数已弃用，将使用单个最优模型进行预测")
        logger.warning(f"警告: 权重参数已弃用，将使用单个最优模型进行预测")
    print(f"使用最近几个月的数据: {months_back}")

    logger.info(f"输入文件: {input_file}")
    logger.info(f"模型目录: {models_dir}")
    logger.info(f"输出文件: {output_file}")
    logger.info(f"窗口大小: {window_size}")
    logger.info(f"滞后特征数: {lags}")
    logger.info(f"模型类型: {model_types}")
    logger.info(f"使用最近几个月的数据: {months_back}")

    # 记录初始内存
    try:
        from optimized_ensemble import predict_shortterm_ensemble

        optimized_result = predict_shortterm_ensemble(input_file, models_dir, output_file)
        if optimized_result is not None:
            predictions, prediction_timestamps = optimized_result
            logger.info("Used optimized medium-term ensemble prediction path")
            input_df = pd.read_csv(input_file)
            _save_and_upload_results(
                predictions=predictions,
                prediction_timestamps=prediction_timestamps,
                output_file=output_file,
                determined_model_type="optimized_middleterm_ensemble",
                new_data=input_df,
                original_timestamps=prediction_timestamps,
            )
            return predictions, prediction_timestamps
    except Exception as optimized_exc:
        logger.warning(
            "Optimized medium-term ensemble prediction failed, falling back to legacy flow: %s",
            optimized_exc,
            exc_info=True,
        )

    try:
        initial_memory = print_memory_usage()
    except:
        initial_memory = 0
        pass

    # 设置手动脚本所需的配置参数
    logger.info("--- 使用优化后的手动预测逻辑开始预测 ---")
    max_lag = lags
    top_n_features_selected = 3000

    # 定义用于特征工程的基本特征组
    wind_speeds_10 = [f'ws10_{i}' for i in range(1, 16)]
    wind_speeds_100 = [f'ws100_{i}' for i in range(1, 16)]
    wind_speeds_200 = [f'ws200_{i}' for i in range(1, 16)]
    base_wind_features = wind_speeds_10 + wind_speeds_100 + wind_speeds_200

    try:
        # --- Step 1: Determine and load model ---
        model, scaler, determined_model_type, model_file_path = _determine_prediction_model(
            models_dir, model_types
        )
        if model is None:
            return None, None

        # --- Step 2: Resolve and load feature importance ---
        importance_file = _resolve_importance_file(models_dir, determined_model_type)
        if importance_file is None:
            return None, None

        selected_feature_names = _load_selected_features(importance_file, top_n_features_selected)
        if selected_feature_names is None:
            return None, None

        # --- Step 3: Load quantile models ---
        model_q05, model_q95 = _load_quantile_models(models_dir)

        # --- Step 4: Preprocess input data ---
        prep_result = _preprocess_input_data(
            input_file, max_lag, wind_speeds_10, wind_speeds_100,
            wind_speeds_200, base_wind_features
        )
        if prep_result is None:
            return None, None

        # --- Step 5: Scale, window, and select features ---
        feat_result = _prepare_prediction_features(
            prep_result['X_new_with_features'], scaler, window_size,
            prep_result['valid_original_indices'],
            prep_result['original_timestamps'],
            prep_result['engineered_feature_names'],
            selected_feature_names
        )
        if feat_result is None:
            return None, None

        # --- Step 6: Run prediction ---
        pred_result = _run_prediction(
            model, feat_result['X_selected'], determined_model_type,
            model_file_path, model_q05, model_q95
        )

        # --- Step 7: Save and upload results ---
        _save_and_upload_results(
            pred_result['predictions'],
            feat_result['prediction_timestamps'],
            output_file,
            determined_model_type,
            prep_result['new_data'],
            prep_result['original_timestamps'],
            pred_result['predictions_lower'],
            pred_result['predictions_upper'],
        )

        # 记录最终内存
        try:
            final_memory = print_memory_usage()
            logger.info(f"内存使用增加: {final_memory - initial_memory:.2f} MB")
        except:
            pass

        # 返回与原函数一致的值
        return pred_result['predictions'], feat_result['prediction_timestamps']

    except Exception as e:
        logger.error(f"❌ 预测过程中出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None

# 如果直接运行此脚本
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='预测风电功率')
    parser.add_argument('--input', type=str, required=True, help='输入特征文件路径')
    parser.add_argument('--models_dir', type=str, required=True, help='模型目录路径')
    parser.add_argument('--output', type=str, required=True, help='输出预测结果文件路径')
    parser.add_argument('--window_size', type=int, default=16, help='时间窗口大小')
    parser.add_argument('--lags', type=int, default=4, help='滞后特征数')
    parser.add_argument('--models', type=str, nargs='+', help='要使用的模型类型列表')
    parser.add_argument('--weights', type=float, nargs='+', help='各模型的权重')
    parser.add_argument('--months', type=int, help='只使用最近几个月的数据')

    args = parser.parse_args()

    # 解析权重参数
    weights_dict = None
    if args.weights and args.models and len(args.weights) == len(args.models):
        weights_dict = dict(zip(args.models, args.weights))

    predict(
        args.input,
        args.models_dir,
        args.output,
        args.window_size,
        args.lags,
        args.models,
        weights_dict,
        args.months
    )
