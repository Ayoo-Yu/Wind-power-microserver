from .data_processor import load_data, preprocess_data, split_data, feature_engineering, scale_data, create_time_window
from .models import get_lightgbm_params
from .train import train_and_evaluate, save_predictions
from .utils import visualize_results
import sys
sys.path.append('./config')
from .config import WINDOW_SIZE, LAGS
import os
from datetime import datetime
from flask import current_app
def train_run(DATA_FILE_PATH, MODEL, TRAIN_RATIO=0.9, CUSTOM_PARAMS=None):
    # 配置
    file_path = DATA_FILE_PATH
    model_name = MODEL
    window_size = WINDOW_SIZE
    lags = LAGS
    train_ratio = TRAIN_RATIO
    custom_params = CUSTOM_PARAMS
    
    # 动态生成输出目录，带时间戳
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join('results', current_time)
    os.makedirs(output_dir, exist_ok=True)  # 确保创建目录
    current_app.logger.info(f"输出结果将保存到: {output_dir}")
    current_app.logger.info(f"训练集占比设置为: {train_ratio}")
    
    if model_name == 'CUSTOM' and custom_params:
        current_app.logger.info(f"使用自定义模型参数: {custom_params}")
    
    # 数据加载与预处理
    data = load_data(file_path)
    current_app.logger.info(f"数据加载完成!")
    X, y = preprocess_data(data)
    current_app.logger.info(f"数据预处理完成!")
    X_train, X_val, y_train, y_val = split_data(X, y, train_ratio=train_ratio)
    current_app.logger.info(f"数据集分割完成! 训练集大小: {len(X_train)}, 验证集大小: {len(X_val)}")
    X_train_fe, X_val_fe = feature_engineering(X_train, X_val, lags)
    current_app.logger.info("特征工程完成!")
    # 数据标准化
    X_train_scaled, X_val_scaled, scaler = scale_data(X_train_fe, X_val_fe)
    current_app.logger.info("数据标准化完成!")
    # 创建时间窗口
    X_train_windows, y_train_windows = create_time_window(X_train_scaled, y_train.values, window_size)
    X_val_windows, y_val_windows = create_time_window(X_val_scaled, y_val.values, window_size)
    current_app.logger.info("时间窗口创建完成!")
    
    # 获取模型参数
    if model_name == 'CUSTOM' and custom_params:
        params = custom_params
        params['name'] = 'CUSTOM'
    else:
        params = get_lightgbm_params(model=model_name)
    
    current_app.logger.info("模型参数获取完成!")
    current_app.logger.info(params)
    
    # 训练与评估
    results_dict,model_filepath,scaler_filepath = train_and_evaluate(X_train_windows, y_train_windows, X_val_windows, y_val_windows, params, scaler)
    current_app.logger.info("模型训练与评估完成!")
    # 保存预测结果
    forecast_df = save_predictions(results_dict, y_val_windows, output_base_dir=output_dir)
    current_app.logger.info("预测结果保存完成!")
    # 可视化结果
    visualize_results(results_dict, y_val_windows, output_path=os.path.join(output_dir, 'power_predictions_comparison.png'))
    current_app.logger.info("可视化结果完成!")
    return forecast_df,model_filepath,scaler_filepath
