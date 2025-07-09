# config.py
import os

WINDOW_SIZE = 16
TRAIN_RATIO = 0.9
OUTPUT_DIR = 'results/'
LAGS = 4
# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
