# config_supershort.py
import os
from datetime import datetime

Today = datetime.now().strftime('%Y%m%d')
WINDOW_SIZE = 16
TRAIN_RATIO = 0.9
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录 (/app/auto_scripts/scripts/supershort)

# 移除 BASE_DIR 计算
# BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..', '..'))
# print(f"BASE_DIR: {BASE_DIR}")

# 使用基于 CURRENT_DIR 的相对路径，与 docker-compose.yaml 中的容器内路径对齐
DATASET_FOLDER = os.path.join(CURRENT_DIR, 'datasets')
PREC_SV_FOLDER = os.path.join(CURRENT_DIR, 'prediction_inputs')
MODEL_FOLDER = os.path.join(CURRENT_DIR, 'saved_models')
OUTPUT_DIR_PRE = os.path.join(CURRENT_DIR, 'prediction_results')
# 将训练预测输出也放在相对路径下
OUTPUT_DIR_TRAIN = os.path.join(CURRENT_DIR, 'train_predictions') 

# 日志目录结构，与全局config.py保持一致
LOGS_BASE_DIR = os.path.join(CURRENT_DIR, 'logs')
AUTO_TRAIN_LOG_DIR = os.path.join(LOGS_BASE_DIR, 'auto_train')  # 训练日志目录
AUTO_PREDICT_LOG_DIR = os.path.join(LOGS_BASE_DIR, 'auto_predict')  # 预测日志目录

# 更新打印语句以反映新路径
print(f"DATASET_FOLDER (数据集): {DATASET_FOLDER}")
print(f"PREC_SV_FOLDER (预测输入): {PREC_SV_FOLDER}")
print(f"MODEL_FOLDER (模型): {MODEL_FOLDER}")
print(f"OUTPUT_DIR_PRE (预测输出): {OUTPUT_DIR_PRE}")
print(f"AUTO_TRAIN_LOG_DIR (训练日志): {AUTO_TRAIN_LOG_DIR}")
print(f"AUTO_PREDICT_LOG_DIR (预测日志): {AUTO_PREDICT_LOG_DIR}")

LAGS = 4

# 确保输出目录存在 (这些路径现在都是相对于 CURRENT_DIR)
os.makedirs(OUTPUT_DIR_PRE, exist_ok=True)
os.makedirs(OUTPUT_DIR_TRAIN, exist_ok=True)
os.makedirs(PREC_SV_FOLDER, exist_ok=True)
os.makedirs(DATASET_FOLDER, exist_ok=True)
os.makedirs(MODEL_FOLDER, exist_ok=True)
os.makedirs(AUTO_TRAIN_LOG_DIR, exist_ok=True)
os.makedirs(AUTO_PREDICT_LOG_DIR, exist_ok=True)
