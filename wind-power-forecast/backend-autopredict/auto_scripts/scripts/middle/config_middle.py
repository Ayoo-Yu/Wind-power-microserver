# config_middle.py
import os
from datetime import datetime

Today = datetime.now().strftime('%Y%m%d')
WINDOW_SIZE = 16
TRAIN_RATIO = 0.9
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录 (/app/auto_scripts/scripts/middle)

# 移除 BASE_DIR 计算
# # 回溯到wind-power-forecast目录 (从middle到scripts到auto_scripts到backend到根目录)
# BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..', '..'))
# print(f"BASE_DIR: {BASE_DIR}")

# 使用基于 CURRENT_DIR 的相对路径，与 docker-compose.yaml 中的容器内路径对齐
DATASET_FOLDER = os.path.join(CURRENT_DIR, 'datasets')
PREC_SV_FOLDER = os.path.join(CURRENT_DIR, 'predict_inputs')
MODEL_FOLDER = os.path.join(CURRENT_DIR, 'models')
OUTPUT_DIR_PRE = os.path.join(CURRENT_DIR, 'predict_outputs')
FEATURE_IMPORTANCE_DIR = os.path.join(CURRENT_DIR, 'feature_importance') # 直接在 middle 目录下
# 将训练预测输出也放在相对路径下
OUTPUT_DIR_TRAIN = os.path.join(CURRENT_DIR, 'train_predictions') 

# 更新打印语句以反映新路径
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
PARAM_OPT_LOG_DIR = os.path.join(CURRENT_DIR, 'logs', 'param_optimizer')  # 参数优化日志目录
AUTO_PRE_TRAIN_LOG_DIR = os.path.join(CURRENT_DIR, 'logs', 'auto_pre_train')  # 预训练日志目录

# 确保输出目录存在 (这些路径现在都是相对于 CURRENT_DIR)
os.makedirs(OUTPUT_DIR_PRE, exist_ok=True)
os.makedirs(OUTPUT_DIR_TRAIN, exist_ok=True)
os.makedirs(PREC_SV_FOLDER, exist_ok=True)
os.makedirs(DATASET_FOLDER, exist_ok=True)
os.makedirs(MODEL_FOLDER, exist_ok=True)
os.makedirs(FEATURE_IMPORTANCE_DIR, exist_ok=True)
os.makedirs(AUTO_PRE_TRAIN_LOG_DIR, exist_ok=True)
