# config_middle.py
import os
from datetime import datetime

Today = datetime.now().strftime('%Y%m%d')
WINDOW_SIZE = 16
TRAIN_RATIO = 0.9
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录 (/app/auto_scripts/scripts/middle)

DEFAULT_WIND_FARM_CODE = os.environ.get('DEFAULT_WIND_FARM_CODE', 'default-farm')


def _normalize_wind_farm_code(value: str) -> str:
    value = (value or '').strip()
    return value or DEFAULT_WIND_FARM_CODE


WIND_FARM_CODE = _normalize_wind_farm_code(os.environ.get('WIND_FARM_CODE'))
IS_DEFAULT_CODE = WIND_FARM_CODE == DEFAULT_WIND_FARM_CODE


def _scoped_dir(*parts: str) -> str:
    base_path = os.path.join(CURRENT_DIR, *parts)
    if IS_DEFAULT_CODE:
        return base_path
    return os.path.join(base_path, WIND_FARM_CODE)


# 使用基于 CURRENT_DIR 的相对路径，与 docker-compose.yaml 中的容器内路径对齐
DATASET_FOLDER = _scoped_dir('datasets')
PREC_SV_FOLDER = _scoped_dir('predict_inputs')
MODEL_FOLDER = _scoped_dir('models')
OUTPUT_DIR_PRE = _scoped_dir('predict_outputs')
FEATURE_IMPORTANCE_DIR = _scoped_dir('feature_importance')
OUTPUT_DIR_TRAIN = _scoped_dir('train_predictions')

# 更新打印语句以反映新路径
print(f"WIND_FARM_CODE: {WIND_FARM_CODE}")
print(f"DATASET_FOLDER (数据集): {DATASET_FOLDER}")
print(f"PREC_SV_FOLDER (预测输入): {PREC_SV_FOLDER}")
print(f"MODEL_FOLDER (模型): {MODEL_FOLDER}")
print(f"OUTPUT_DIR_PRE (预测输出): {OUTPUT_DIR_PRE}")
print(f"FEATURE_IMPORTANCE_DIR (特征重要性): {FEATURE_IMPORTANCE_DIR}")
print(f"OUTPUT_DIR_TRAIN (训练预测输出): {OUTPUT_DIR_TRAIN}")

LAGS = 4

# 参数优化配置 (日志路径已相对于 CURRENT_DIR)
PARAM_OPT_ITERATIONS = 10  # 随机搜索迭代次数
PARAM_OPT_WEEKLY = True    # 是否启用每周参数优化
PARAM_OPT_MIN_IMPROVEMENT = 0.05  # 最小改进阈值（2%）
PARAM_OPT_LOG_DIR = _scoped_dir('logs', 'param_optimizer')  # 参数优化日志目录
AUTO_PRE_TRAIN_LOG_DIR = _scoped_dir('logs', 'auto_pre_train')  # 预训练日志目录

# 确保输出目录存在 (这些路径现在都是相对于 CURRENT_DIR)
for directory in [
    OUTPUT_DIR_PRE,
    OUTPUT_DIR_TRAIN,
    PREC_SV_FOLDER,
    DATASET_FOLDER,
    MODEL_FOLDER,
    FEATURE_IMPORTANCE_DIR,
    PARAM_OPT_LOG_DIR,
    AUTO_PRE_TRAIN_LOG_DIR,
]:
    os.makedirs(directory, exist_ok=True)
