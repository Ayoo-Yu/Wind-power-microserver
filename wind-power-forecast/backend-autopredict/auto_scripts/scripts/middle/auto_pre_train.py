# merged_auto_script.py
import os
import time
import logging
import sys
from threading import Thread, Lock, Event
import joblib
import pandas as pd
from datetime import datetime, timedelta
import argparse

# --- Dynamically Add Project Root to sys.path ---
# Calculate the path to the project root (/app) based on this file's location
# This file is at /app/auto_scripts/scripts/middle/auto_pre_train.py
# We need to go up 3 levels to reach /app
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..')) # Correct: Go up 3 levels
    if project_root not in sys.path:
        sys.path.insert(0, project_root) # Insert at the beginning
        logging.info(f"(auto_pre_train) 将项目根目录添加到 sys.path: {project_root}")
    # --- Debug Logging Start ---
    print(f"DEBUG: Calculated project_root: {project_root}")
    print(f"DEBUG: Current sys.path: {sys.path}")
    logging.info(f"DEBUG: Calculated project_root: {project_root}")
    logging.info(f"DEBUG: Current sys.path: {sys.path}")
    # --- Debug Logging End ---
except Exception as path_e:
    logging.error(f"(auto_pre_train) 动态计算项目根目录时出错: {path_e}", exc_info=True)
# --- End Path Modification ---

# 导入预测和训练所需的模块
from predict_middle import predict
from data_processor_middle import (
    load_data,
    preprocess_data,
    split_data,
    feature_engineering,
    scale_data,
    create_time_window,
    filter_data_by_date,
    update_training_csv_from_db
)
from models_middle import get_lightgbm_params, get_unified_params
from train_middle import train_and_evaluate, train_multiple_datasets, calculate_model_weights, save_predictions
from utils_middle import visualize_results
from config_middle import WINDOW_SIZE, TRAIN_RATIO, LAGS, OUTPUT_DIR_TRAIN, Today, PREC_SV_FOLDER, DATASET_FOLDER, MODEL_FOLDER, OUTPUT_DIR_PRE, AUTO_PRE_TRAIN_LOG_DIR

# 创建一个锁用于同步模型文件的访问
model_lock = Lock()
# 创建一个事件用于指示模型是否可用
model_available = Event()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# 确保日志目录存在
log_dir = AUTO_PRE_TRAIN_LOG_DIR
os.makedirs(log_dir, exist_ok=True)
# 创建日志文件
log_file = os.path.join(log_dir, f"{Today}.log")
# 创建 FileHandler
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# 定义日志格式
formatter = logging.Formatter("%(asctime)s - %(message)s")
file_handler.setFormatter(formatter)

# 将处理器添加到日志记录器
logger.addHandler(file_handler)

# 添加控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 处理Windows控制台输出编码
if sys.platform == 'win32':
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    # 确保stderr也使用utf-8编码
    sys.stderr.reconfigure(encoding='utf-8')

def get_train_flag_file(date_str):
    """获取训练完成标志文件的路径"""
    return os.path.join(log_dir, f"{date_str}_train_done.flag")

def is_train_done(date_str):
    """检查指定日期的训练是否已完成"""
    flag_file = get_train_flag_file(date_str)
    if os.path.exists(flag_file):
        logging.info(f"检测到{date_str}的训练已经执行过 (标志文件: {flag_file})")
        return True
    return False

def mark_train_done(date_str):
    """标记训练已完成"""
    flag_file = get_train_flag_file(date_str)
    with open(flag_file, 'w') as f:
        f.write(f'Training done for {date_str} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    logging.info(f"训练完成，已创建标志文件: {flag_file}")

def get_predict_flag_file(date_str):
    """获取预测完成标志文件的路径"""
    return os.path.join(log_dir, f"{date_str}_predict_done.flag")

def is_predict_done(date_str):
    """检查指定日期的预测是否已完成"""
    flag_file = get_predict_flag_file(date_str)
    if os.path.exists(flag_file):
        logging.info(f"检测到{date_str}的预测已经执行过 (标志文件: {flag_file})")
        return True
    return False

def mark_predict_done(date_str):
    """标记预测已完成"""
    flag_file = get_predict_flag_file(date_str)
    with open(flag_file, 'w') as f:
        f.write(f'Prediction done for {date_str} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    logging.info(f"预测完成，已创建标志文件: {flag_file}")

def print_section(title):
    """打印带分隔符的标题"""
    separator = "=" * 80
    print(f"\n{separator}")
    print(f">>> {title} <<<")
    print(f"{separator}\n")
    logging.info(f"\n{separator}")
    logging.info(f">>> {title} <<<")
    logging.info(f"{separator}\n")

def is_model_available(model_folder_today):
    """检查最佳模型是否可用"""
    print(f"检查模型目录: {model_folder_today}")
    logging.info(f"检查模型目录: {model_folder_today}")
    best_models_dir = os.path.join(model_folder_today, 'best_models')
    
    if os.path.exists(best_models_dir):
        print(f"发现best_models目录: {best_models_dir}")
        logging.info(f"发现best_models目录: {best_models_dir}")
        # 检查是否至少有一个算法类型的模型可用
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
    
    # 检查传统模型文件
    model_file = os.path.join(model_folder_today, 'model.joblib')
    exists = os.path.exists(model_file)
    if exists:
        print(f"✅ 发现传统模型文件: {model_file}")
        logging.info(f"发现传统模型文件: {model_file}")
    else:
        print(f"❌ 未找到任何可用模型文件")
        logging.info(f"未找到任何可用模型文件")
    return exists

def train_model(data_file_path, model_folder_today):
    """执行模型训练和评估 (使用 CSV 文件路径)"""
    print_section("开始模型训练")
    # 配置
    window_size = WINDOW_SIZE
    lags = LAGS
    train_ratio = TRAIN_RATIO
    output_dir = OUTPUT_DIR_TRAIN
    print(f"配置信息:")
    print(f"  - 窗口大小: {window_size}")
    print(f"  - 滞后特征数: {lags}")
    print(f"  - 训练集比例: {train_ratio}")
    print(f"  - 输出目录: {output_dir}")
    print(f"  - 模型存储路径: {model_folder_today}")
    logging.info(f"配置信息:")
    logging.info(f"  - 窗口大小: {window_size}")
    logging.info(f"  - 滞后特征数: {lags}")
    logging.info(f"  - 训练集比例: {train_ratio}")
    logging.info(f"  - 输出目录: {output_dir}")
    logging.info(f"  - 模型存储路径: {model_folder_today}")
    logging.info(f"输出结果将保存到: {output_dir}")
    
    # 数据加载 (从 CSV 文件加载)
    print_section("数据加载与预处理")
    print(f"加载数据文件: {data_file_path}")
    logging.info(f"加载数据文件: {data_file_path}")
    logging.info("开始加载和预处理数据...")
    # Call original load_data with file path
    data = load_data(data_file_path) 

    # 检查加载的数据是否为空
    if data.empty:
        print(f"❌ 从 CSV 文件加载的数据为空或加载失败，无法继续训练: {data_file_path}")
        logging.error(f"❌ 从 CSV 文件加载的数据为空或加载失败，无法继续训练: {data_file_path}")
        return # Exit training if no data

    print(f"数据加载完成，共 {len(data)} 条记录")
    print(f"数据前5行预览: \n{data.head()}")
    logging.info(f"数据加载完成，共 {len(data)} 条记录")
    logging.info(f"数据前5行预览: \n{data.head()}")
    
    # 使用不同时长的历史数据训练多个模型
    months_list = [None]  # None表示使用全部数据
    
    # 根据数据集的实际时间跨度优化months_list
    if 'Timestamp' in data.columns:
        # 确保Timestamp列是datetime类型
        if not pd.api.types.is_datetime64_any_dtype(data['Timestamp']):
            data['Timestamp'] = pd.to_datetime(data['Timestamp'])
        
        # 计算数据集的实际时间跨度（月数）
        earliest_date = data['Timestamp'].min()
        latest_date = data['Timestamp'].max()
        date_range_months = (latest_date.year - earliest_date.year) * 12 + latest_date.month - earliest_date.month
        
        print(f"数据集时间范围: {earliest_date.strftime('%Y-%m-%d')} 至 {latest_date.strftime('%Y-%m-%d')}, 共 {date_range_months} 个月")
        logging.info(f"数据集时间范围: {earliest_date.strftime('%Y-%m-%d')} 至 {latest_date.strftime('%Y-%m-%d')}, 共 {date_range_months} 个月")
        
        # 修剪months_list，去除超过实际月数的选项
        optimized_months = [m for m in months_list if m is None or m <= date_range_months]
        
        if len(optimized_months) < len(months_list):
            print(f"根据数据集实际时间范围({date_range_months}个月)，优化months_list: {months_list} -> {optimized_months}")
            logging.info(f"根据数据集实际时间范围({date_range_months}个月)，优化months_list: {months_list} -> {optimized_months}")
            months_list = optimized_months
    
    print(f"将使用以下时间段训练模型: {months_list}")
    logging.info(f"将使用以下时间段训练模型: {months_list}")
    
    try:
        print_section("开始多数据集训练")
        print(f"将使用多种时间跨度的数据训练模型...")
        logging.info(f"将使用多种时间跨度的数据训练模型...")
        # 运行多数据集训练，为每种算法选择最佳模型
        training_output = train_multiple_datasets(data, months_list, train_ratio, lags, window_size, model_folder_today)
        # 从返回的字典中获取models和results
        best_models_info = training_output['models']
        all_training_results = training_output['results']
        print(f"多数据集训练完成! 已为每种算法选择最佳模型")
        logging.info(f"多数据集训练完成! 已为每种算法选择最佳模型")
        for algo_type, model_info in best_models_info.items():
            if model_info['model'] is not None:
                months_desc = f"{model_info['months']}个月" if model_info['months'] else "全部数据"
                print(f"  - 最佳{algo_type}模型: 使用{months_desc}数据, 评分={model_info['score']:.4f}")
                logging.info(f"  - 最佳{algo_type}模型: 使用{months_desc}数据, 评分={model_info['score']:.4f}")
        
        # 新增：选择全局最优模型
        print_section("选择全局最优模型")
        logging.info("选择全局最优模型")
        best_overall_score = float('-inf')
        best_overall_type = None
        best_overall_info = None

        for algo_type, model_info in best_models_info.items():
            # 确保模型信息有效且包含评分
            if model_info and model_info.get('model') is not None and 'score' in model_info:
                current_score = model_info['score']
                # score 越高越好
                if current_score > best_overall_score:
                    best_overall_score = current_score
                    best_overall_type = algo_type
                    best_overall_info = model_info

        if best_overall_type:
            print(f"✅ 全局最优模型类型为: {best_overall_type}，评分为: {best_overall_score:.4f}")
            logging.info(f"✅ 全局最优模型类型为: {best_overall_type}，评分为: {best_overall_score:.4f}")

            # 将最优模型类型写入标记文件，方便预测脚本读取
            marker_file_path = os.path.join(model_folder_today, 'best_model_type.txt')
            try:
                with open(marker_file_path, 'w') as f:
                    f.write(best_overall_type)
                print(f"✅ 全局最优模型类型已写入标记文件: {marker_file_path}")
                logging.info(f"✅ 全局最优模型类型已写入标记文件: {marker_file_path}")
            except IOError as e:
                print(f"❌ 写入最优模型标记文件失败: {e}")
                logging.error(f"❌ 写入最优模型标记文件失败: {e}")
        else:
            print(f"❌ 未能确定全局最优模型。")
            logging.error(f"❌ 未能确定全局最优模型。")
        
        # 移除模型权重计算步骤
        print_section("跳过模型权重计算")
        logging.info("根据需求跳过模型权重计算步骤，将仅使用单个最佳模型进行预测。")
    
    except Exception as e:
        print_section("多数据集训练失败")
        logging.error("多数据集训练失败")
        print(f"❌ 错误信息: {str(e)}")
        logging.error(f"❌ 错误信息: {str(e)}")
        print(f"回退到传统的单一模型训练方法...")
        logging.info(f"回退到传统的单一模型训练方法...")
        
        # 如果多数据集训练失败，回退到传统方法
        print_section("开始传统单一模型训练")
        logging.info("开始传统单一模型训练")
        print(f"使用全部数据进行预处理...")
        logging.info(f"使用全部数据进行预处理...")
        X, y = preprocess_data(data)
        X_train, X_val, y_train, y_val = split_data(X, y, train_ratio)
        print(f"数据集划分完成，训练集: {X_train.shape}, 验证集: {X_val.shape}")
        logging.info(f"数据集划分完成，训练集: {X_train.shape}, 验证集: {X_val.shape}")
        
        print(f"执行特征工程...")
        logging.info(f"执行特征工程...")
        X_train_fe, X_val_fe = feature_engineering(X_train, X_val, lags)
        print(f"特征工程后的数据集大小 - 训练: {X_train_fe.shape}, 验证: {X_val_fe.shape}")
        logging.info(f"特征工程后的数据集大小 - 训练: {X_train_fe.shape}, 验证: {X_val_fe.shape}")
        
        # 数据标准化
        print(f"执行数据标准化...")
        logging.info(f"执行数据标准化...")
        X_train_scaled, X_val_scaled, scaler = scale_data(X_train_fe, X_val_fe)
        print(f"数据标准化完成")
        logging.info(f"数据标准化完成")
        
        # 创建时间窗口
        print(f"创建时间窗口，窗口大小: {window_size}...")
        logging.info(f"创建时间窗口，窗口大小: {window_size}...")
        X_train_windows, y_train_windows = create_time_window(X_train_scaled, y_train.values, window_size)
        X_val_windows, y_val_windows = create_time_window(X_val_scaled, y_val.values, window_size)
        print(f"时间窗口创建完成，窗口数量 - 训练: {len(X_train_windows)}, 验证: {len(X_val_windows)}")
        logging.info(f"时间窗口创建完成，窗口数量 - 训练: {len(X_train_windows)}, 验证: {len(X_val_windows)}")
        
        # 获取模型参数
        print(f"获取模型参数...")
        logging.info(f"获取模型参数...")
        params_list = get_lightgbm_params()
        print(f"模型参数获取完成，共 {len(params_list)} 种参数配置")
        logging.info(f"模型参数获取完成，共 {len(params_list)} 种参数配置")
        
        # 训练与评估
        print_section("开始模型训练与评估")
        logging.info("开始模型训练与评估")
        print(f"训练3种不同的LightGBM模型: GBDT, DART, GOSS")
        logging.info(f"训练3种不同的LightGBM模型: GBDT, DART, GOSS")
        
        # 生成扁平化特征名（用于兼容特征选择机制）
        original_feature_names = X_train.columns.tolist() if hasattr(X_train, 'columns') else [f'feature_{i}' for i in range(X_train.shape[1])]
        flat_feature_names = []
        # 按照时间步（外循环）和特征（内循环）的顺序生成特征名
        # 这必须与create_flattened_windows_with_indices函数中window.reshape(1, -1)的扁平化顺序一致
        for i in range(window_size):
            time_lag_label = window_size - 1 - i  # 从window_size-1到0
            for name in original_feature_names:
                flat_feature_names.append(f"{name}_t-{time_lag_label}")
        
        results_dict = train_and_evaluate(
            X_train_windows, y_train_windows,
            X_val_windows, y_val_windows,
            params_list, scaler, model_folder_today,
            None, flat_feature_names,  # 添加feature_names参数
            save_importance=True  # 此处总是保存特征重要性（因为是使用全部数据的传统训练）
        )
        print(f"模型训练与评估完成!")
        logging.info(f"模型训练与评估完成!")
        for model_name, result in results_dict.items():
            print(f"  - {model_name}: RMSE={result['rmse']:.4f}, K={result['k']:.4f}")
            logging.info(f"  - {model_name}: RMSE={result['rmse']:.4f}, K={result['k']:.4f}")
        
        # 保存预测结果
        print(f"保存预测结果到 {output_dir}...")
        logging.info(f"保存预测结果到 {output_dir}...")
        save_predictions(results_dict, y_val_windows, output_base_dir=output_dir)
        print(f"预测结果保存完成")
        logging.info(f"预测结果保存完成")
        
        # 可视化结果
        print(f"创建可视化结果...")
        logging.info(f"创建可视化结果...")
        visualize_results(results_dict, y_val_windows, output_dir)
        print(f"可视化结果创建完成")
        logging.info(f"可视化结果创建完成")

def monitor_training(today_date):
    """监视训练过程，并在训练前更新 CSV 文件"""
    print_section("启动训练监视线程")
    logging.info("启动训练监视线程")
    # Define CSV file path (Use a constant name)
    # csv_file = os.path.join(DATASET_FOLDER, f'{today_date}.csv') # Old way
    csv_file = os.path.join(DATASET_FOLDER, 'training_data_middle.csv') # New constant name
    model_folder_today = os.path.join(MODEL_FOLDER, today_date)
    
    # 确保模型文件夹存在
    os.makedirs(model_folder_today, exist_ok=True)
    # 确保数据集文件夹存在 (如果 update 函数不创建的话)
    os.makedirs(DATASET_FOLDER, exist_ok=True)

    print(f"训练 CSV 文件路径: {csv_file}") # Log CSV file path
    print(f"模型存储目录: {model_folder_today}")
    print(f"训练完成标志文件: {get_train_flag_file(today_date)}")
    logging.info(f"训练 CSV 文件路径: {csv_file}")
    logging.info(f"模型存储目录: {model_folder_today}")
    logging.info(f"训练完成标志文件: {get_train_flag_file(today_date)}")
    logging.info(f"开始监视训练任务 (基于标志文件和 CSV 更新)...")

    while True:
        if is_train_done(today_date):
            print(f"⚠️ 检测到今天的训练已经执行过，跳过...")
            logging.info(f"⚠️ 检测到今天的训练已经执行过，跳过...")
            if is_model_available(model_folder_today):
                model_available.set()
                print(f"✅ (跳过训练后) 模型已设置为可用状态")
                logging.info(f"✅ (跳过训练后) 模型已设置为可用状态")
            break # Exit the loop if training is done

        # --- 更新 CSV 文件 --- 
        print(f"ℹ️ 尝试更新训练 CSV 文件: {csv_file}")
        logging.info(f"ℹ️ 尝试更新训练 CSV 文件: {csv_file}")
        update_successful = update_training_csv_from_db(csv_file)
        
        if not update_successful:
            print(f"❌ 更新训练 CSV 文件失败，本次将跳过训练。请检查日志获取详细信息。")
            logging.error(f"❌ 更新训练 CSV 文件失败，本次将跳过训练。")
            # Decide whether to break or sleep and retry later
            # For now, let's just break the loop for this run
            break 
        else:
            print(f"✅ CSV 文件更新检查完成。")
            logging.info(f"✅ CSV 文件更新检查完成。")

        # --- 执行训练 --- 
        # Check again if training is done in case it finished while updating CSV
        if is_train_done(today_date):
            logging.info("在 CSV 更新后检测到训练已完成，跳过执行训练。")
            break

        print(f"ℹ️ 今天 ({today_date}) 的训练尚未完成，开始执行训练 (使用 {csv_file})...")
        logging.info(f"ℹ️ 今天 ({today_date}) 的训练尚未完成，开始执行训练 (使用 {csv_file})...")
        with model_lock:
            # Call train_model with the CSV file path
            train_model(csv_file, model_folder_today)
        
        # 标记训练已完成
        mark_train_done(today_date)
        print(f"✅ 训练完成，已创建标志文件")
        logging.info(f"✅ 训练完成，已创建标志文件")
        
        # 验证模型是否可用
        if is_model_available(model_folder_today):
            model_available.set()
            print(f"✅ 模型已成功保存到 {model_folder_today}，模型可用。")
            logging.info(f"✅ 模型已成功保存到 {model_folder_today}，模型可用。")
        else:
            print(f"❌ 模型文件未找到在 {model_folder_today}，模型不可用。")
            logging.info(f"❌ 模型文件未找到在 {model_folder_today}，模型不可用。")
        break # Exit loop after attempting training

def monitor_prediction(today_date):
    """
    监控预测过程，确保预测任务完成
    **修改：现在查找并使用明天的预测输入文件**
    
    参数:
    today_date: 当前日期，格式为YYYYMMDD
    """
    print(f"开始监控预测过程，日期: {today_date} (将预测 {today_date} 的下一天)")
    logging.info(f"开始监控预测过程，日期: {today_date} (将预测 {today_date} 的下一天)")
    
    # 检查今天的预测 *运行* 是否已完成 (使用今天的标志)
    if is_predict_done(today_date):
        print(f"今天 ({today_date}) 的预测任务已运行完成，无需再次执行")
        logging.info(f"今天 ({today_date}) 的预测任务已运行完成，无需再次执行")
        return
    
    # 计算明天的日期字符串
    try:
        today_dt = datetime.strptime(today_date, '%Y%m%d')
        tomorrow_dt = today_dt + timedelta(days=1)
        tomorrow_date_str = tomorrow_dt.strftime('%Y%m%d')
        print(f"将查找明天的预测输入文件，日期: {tomorrow_date_str}")
        logging.info(f"将查找明天的预测输入文件，日期: {tomorrow_date_str}")
    except ValueError:
        logging.error(f"无法解析日期: {today_date}，无法确定明天的输入文件名。")
        return

    # 等待模型可用 (使用今天的模型)
    model_folder_today = os.path.join(MODEL_FOLDER, today_date)
    max_wait_time = 7200  # 最大等待时间，单位秒
    wait_interval = 60  # 检查间隔，单位秒
    start_time = time.time()
    
    print(f"等待今天的模型目录可用: {model_folder_today}")
    logging.info(f"等待今天的模型目录可用: {model_folder_today}")
    
    while True:
        # 检查是否超时
        if time.time() - start_time > max_wait_time:
            print(f"等待模型超时，预测任务终止")
            logging.error(f"等待模型超时，预测任务终止")
            return
        
        # 再次检查今天的预测 *运行* 是否已完成
        if is_predict_done(today_date):
            print(f"在等待期间，今天 ({today_date}) 的预测任务已完成，退出等待")
            logging.info(f"在等待期间，今天 ({today_date}) 的预测任务已完成，退出等待")
            return
        
        # 检查模型目录是否存在
        if not os.path.exists(model_folder_today):
            print(f"今天的模型目录不存在，等待 {wait_interval} 秒后重试...")
            logging.info(f"今天的模型目录不存在，等待 {wait_interval} 秒后重试...")
            time.sleep(wait_interval)
            continue
        
        # 使用is_model_available检查是否有模型文件（包括best_models子目录）
        if not is_model_available(model_folder_today):
            print(f"今天的模型目录中没有可用的模型文件，等待 {wait_interval} 秒后重试...")
            logging.info(f"今天的模型目录中没有可用的模型文件，等待 {wait_interval} 秒后重试...")
            time.sleep(wait_interval)
            continue
        
        # 检查是否有 *明天* 的预测输入文件
        csv_file = os.path.join(PREC_SV_FOLDER, f"predict_input_{tomorrow_date_str}.csv")
        if not os.path.exists(csv_file):
            print(f"明天的预测输入文件 ({tomorrow_date_str}) 不存在，等待 {wait_interval} 秒后重试: {csv_file}")
            logging.info(f"明天的预测输入文件 ({tomorrow_date_str}) 不存在，等待 {wait_interval} 秒后重试: {csv_file}")
            time.sleep(wait_interval)
            continue
        
        # 执行预测
        print(f"✅ 发现明天的预测文件：{csv_file}，使用今天的模型执行预测...")
        logging.info(f"✅ 发现明天的预测文件：{csv_file}，使用今天的模型执行预测...")
        
        # --- 新增：检查生产模型和类型文件 ---
        production_model_path = os.path.join(model_folder_today, 'best_models', 'production_model.joblib')
        best_model_type_path = os.path.join(model_folder_today, 'best_model_type.txt')
        
        prod_model_exists = os.path.exists(production_model_path)
        type_file_content = None
        if os.path.exists(best_model_type_path):
            try:
                with open(best_model_type_path, 'r') as f:
                    type_file_content = f.read().strip()
            except Exception as e:
                logging.error(f"读取 best_model_type.txt 文件失败: {e}")

        if prod_model_exists and type_file_content == "production_model":
            print("✅ 检测到生产模型 (production_model.joblib) 存在，且类型文件正确标记。预测将优先使用生产模型。")
            logging.info("✅ 检测到生产模型 (production_model.joblib) 存在，且类型文件正确标记。预测将优先使用生产模型。")
        elif prod_model_exists and type_file_content != "production_model":
            print(f"⚠️ 检测到生产模型存在，但类型文件标记为 '{type_file_content}'。预测行为将取决于 predict 函数的内部逻辑。")
            logging.warning(f"⚠️ 检测到生产模型存在，但类型文件标记为 '{type_file_content}'。预测行为将取决于 predict 函数的内部逻辑。")
        elif not prod_model_exists and type_file_content == "production_model":
            print(f"⚠️ 类型文件标记为 'production_model'，但生产模型文件缺失！预测行为将取决于 predict 函数的内部逻辑（可能失败或回退）。")
            logging.warning(f"⚠️ 类型文件标记为 'production_model'，但生产模型文件缺失！预测行为将取决于 predict 函数的内部逻辑（可能失败或回退）。")
        else: # not prod_model_exists and type_file_content != "production_model"
            print(f"ℹ️ 未检测到生产模型，或类型文件标记为 '{type_file_content}'。预测将尝试使用评估阶段的最佳模型。")
            logging.info(f"ℹ️ 未检测到生产模型，或类型文件标记为 '{type_file_content}'。预测将尝试使用评估阶段的最佳模型。")
        # --- 检查结束 ---

        # 创建输出目录 (使用今天的日期)
        output_dir = os.path.join(OUTPUT_DIR_PRE, today_date)
        os.makedirs(output_dir, exist_ok=True)
        # 输出文件名仍然使用今天的日期，表示是今天运行的预测
        output_file = os.path.join(output_dir, f"predict_output_{today_date}.csv") 
        
        print(f"输出文件将保存到: {output_file}")
        logging.info(f"输出文件将保存到: {output_file}")
        
        # 调用predict函数 (输入是明天的文件，模型是今天的)
        predict_success = False  # 用于标记预测是否真的执行了
        try:
            # 调用predict函数
            combined_pred, pred_timestamps = predict(
                input_file=csv_file,             # 使用明天的输入文件
                models_dir=model_folder_today, # 使用今天的模型目录
                output_file=output_file,         # 输出文件基于今天日期
                window_size=WINDOW_SIZE,
                lags=LAGS
            )
            
            # 检查返回值，只有成功预测才标记完成
            if combined_pred is not None and pred_timestamps is not None:
                predict_success = True
                print(f"✅ 预测成功完成，结果已保存到 {output_file}")
                logging.info(f"✅ 预测成功完成，结果已保存到 {output_file}")
            else:
                print(f"❌ predict 函数未成功返回结果，跳过标记完成")
                logging.error(f"❌ predict 函数未成功返回结果，跳过标记完成")
        
        except Exception as e:
            print(f"❌ 调用 predict 函数时发生意外错误: {e}")
            logging.error(f"❌ 调用 predict 函数时发生意外错误: {e}")
            import traceback
            traceback.print_exc()
            logging.error(traceback.format_exc())
        
        # 只有在predict函数成功执行后才标记 *今天* 的预测任务完成
        if predict_success:
            mark_predict_done(today_date) # 使用今天的日期标记
            print(f"✅ 今天 ({today_date}) 的预测执行完成")
            logging.info(f"✅ 今天 ({today_date}) 的预测执行完成")
        else:
            print(f"❌ 预测未成功执行或失败，不标记完成")
            logging.error(f"❌ 预测未成功执行或失败，不标记完成")
        
        break  # 无论成功与否，发现文件后都退出循环
    
    print(f"预测监控结束 ({today_date})")
    logging.info(f"预测监控结束 ({today_date})")

def main():
    """主函数，启动训练和预测的监视线程"""
    parser = argparse.ArgumentParser(description="Auto Pre-Train script for short/middle term models.")
    parser.add_argument("--mode", type=str, choices=['train', 'predict', 'all'], default='all',
                        help="Run mode: 'train' for training only, 'predict' for prediction only, 'all' for both.")
    args = parser.parse_args()

    print_section(f"自动训练预测系统启动 - 模式: {args.mode.upper()} (中期)")
    logging.info(f"自动训练预测系统启动 - 模式: {args.mode.upper()} (中期)")
    today_date = Today # Today is defined in config_middle
    print(f"今天的日期是: {today_date}")
    logging.info(f"今天的日期是: {today_date}")

    train_thread = None
    predict_thread = None

    if args.mode == 'train' or args.mode == 'all':
        print(f"创建训练监视线程 (中期)...")
        logging.info(f"创建训练监视线程 (中期)...")
        train_thread = Thread(target=monitor_training, args=(today_date,), name="TrainThread-Middle")
        print(f"启动训练线程 (中期)...")
        logging.info(f"启动训练线程 (中期)...")
        train_thread.start()
        if args.mode == 'train': 
            print(f"等待训练线程完成 (中期)...")
            logging.info(f"等待训练线程完成 (中期)...")
            train_thread.join()
            print_section("训练模式完成 (中期)")
            logging.info("训练模式完成 (中期)")
            return 

    if args.mode == 'predict' or args.mode == 'all':
        if args.mode == 'all' and train_thread is not None and train_thread.is_alive():
            print(f"模式 'all': 等待训练线程完成 (中期) 才能安全开始预测...")
            logging.info(f"模式 'all': 等待训练线程完成 (中期) 才能安全开始预测...")
            train_thread.join()

        print(f"创建预测监视线程 (中期)...")
        logging.info(f"创建预测监视线程 (中期)...")
        predict_thread = Thread(target=monitor_prediction, args=(today_date,), name="PredictThread-Middle")
        print(f"启动预测线程 (中期)...")
        logging.info(f"启动预测线程 (中期)...")
        predict_thread.start()
        if args.mode == 'predict': 
            print(f"等待预测线程完成 (中期)...")
            logging.info(f"等待预测线程完成 (中期)...")
            predict_thread.join()
            print_section("预测模式完成 (中期)")
            logging.info("预测模式完成 (中期)")
            return 

    if args.mode == 'all':
        if train_thread is not None and train_thread.is_alive():
            train_thread.join()
        if predict_thread is not None and predict_thread.is_alive():
            print(f"模式 'all': 等待预测线程完成 (中期)...")
            logging.info(f"模式 'all': 等待预测线程完成 (中期)...")
            predict_thread.join()

    print_section("系统任务完成 (中期 - 基于模式)")
    logging.info("系统任务完成 (中期 - 基于模式)")


if __name__ == '__main__':
    main()
