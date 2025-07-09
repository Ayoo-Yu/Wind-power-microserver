# param_optimizer.py
import os
import logging
import sys
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.metrics import mean_squared_error

# 导入项目中的其他模块
from config import (
    LAGS, WINDOW_SIZE, TRAIN_RATIO, MODEL_FOLDER, DATASET_FOLDER, Today,
    PARAM_OPT_ITERATIONS, PARAM_OPT_MIN_IMPROVEMENT, PARAM_OPT_LOG_DIR
)
from data_processor_middle import load_data, preprocess_data, split_data, feature_engineering, scale_data, create_time_window
from models_middle import get_lightgbm_params, add_new_param_version, save_param_versions_to_file, get_latest_param_version
from RandomizedSearchCV import find_best_params
from utils_middle import evaluate_with_time_weights, calculate_rmse, calculate_k
import lightgbm as lgb

# 设置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 确保日志目录存在
os.makedirs(PARAM_OPT_LOG_DIR, exist_ok=True)

# 创建日志文件
log_file = os.path.join(PARAM_OPT_LOG_DIR, f"{Today}.log")

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
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 定义周标志文件路径
def get_weekly_flag_file():
    """获取本周的标志文件路径"""
    # 获取当前日期
    today = datetime.now()
    # 计算本周的周一日期（作为标识符）
    monday = today - timedelta(days=today.weekday())
    monday_str = monday.strftime('%Y%m%d')
    # 返回标志文件路径
    return os.path.join(PARAM_OPT_LOG_DIR, f"{monday_str}_param_opt_done.flag")

def is_weekly_optimization_done():
    """检查本周是否已经完成参数优化"""
    flag_file = get_weekly_flag_file()
    if os.path.exists(flag_file):
        logger.info(f"检测到本周参数优化已经执行过 (标志文件: {flag_file})")
        return True
    return False

def mark_weekly_optimization_done():
    """标记本周参数优化已完成"""
    flag_file = get_weekly_flag_file()
    with open(flag_file, 'w') as f:
        f.write(f'Parameter optimization done for week of {datetime.now().strftime("%Y-%m-%d")}\n')
    logger.info(f"参数优化完成，已创建标志文件: {flag_file}")

def print_section(title):
    """打印带分隔符的标题"""
    separator = "=" * 80
    print(f"\n{separator}")
    print(f">>> {title} <<<")
    print(f"{separator}\n")
    logger.info(f"\n{separator}")
    logger.info(f">>> {title} <<<")
    logger.info(f"{separator}\n")

def get_latest_data_file():
    """获取最新的数据文件"""
    files = [f for f in os.listdir(DATASET_FOLDER) if f.endswith('.csv')]
    if not files:
        logger.error("没有找到CSV数据文件")
        return None
    
    # 按文件名排序（假设文件名是日期格式）
    files.sort(reverse=True)
    latest_file = os.path.join(DATASET_FOLDER, files[0])
    logger.info(f"找到最新的数据文件: {latest_file}")
    return latest_file

def optimize_params():
    """执行参数优化流程"""
    print_section("开始参数优化")
    logger.info("开始LightGBM参数优化流程")
    
    # 检查本周是否已经执行过参数优化
    if is_weekly_optimization_done():
        print_section("参数优化已执行")
        logger.info("本周已经执行过参数优化，跳过此次运行")
        print("本周已经执行过参数优化，跳过此次运行")
        return True
    
    # 获取最新的数据文件
    data_file = get_latest_data_file()
    if not data_file:
        logger.error("无法继续参数优化，未找到数据文件")
        return False
    
    # 读取数据
    logger.info(f"加载数据: {data_file}")
    data = load_data(data_file)
    logger.info(f"数据加载完成，共 {len(data)} 条记录")
    
    # 预处理数据
    X, y = preprocess_data(data)
    X_train, X_val, y_train, y_val = split_data(X, y, TRAIN_RATIO)
    logger.info(f"数据集划分完成，训练集: {X_train.shape}, 验证集: {X_val.shape}")
    
    # 提取时间戳用于加权评分
    timestamps = None
    if 'Timestamp' in data.columns:
        # 保存验证集对应的时间戳
        split_index = int(len(data) * TRAIN_RATIO)
        val_timestamps = data['Timestamp'].iloc[split_index:].reset_index(drop=True)
        timestamps = val_timestamps
    
    # 特征工程
    X_train_fe, X_val_fe = feature_engineering(X_train, X_val, LAGS)
    logger.info(f"特征工程完成，训练特征: {X_train_fe.shape}, 验证特征: {X_val_fe.shape}")
    
    # 标准化
    X_train_scaled, X_val_scaled, scaler = scale_data(X_train_fe, X_val_fe)
    logger.info(f"数据标准化完成")
    
    # 创建时间窗口
    X_train_windows, y_train_windows = create_time_window(X_train_scaled, y_train.values, WINDOW_SIZE)
    X_val_windows, y_val_windows = create_time_window(X_val_scaled, y_val.values, WINDOW_SIZE)
    logger.info(f"时间窗口创建完成，训练窗口: {X_train_windows.shape}, 验证窗口: {X_val_windows.shape}")
    
    # 调整时间戳长度以匹配窗口化后的数据
    if timestamps is not None and len(timestamps) > len(y_val_windows):
        timestamps = timestamps[len(timestamps) - len(y_val_windows):].reset_index(drop=True)
        logger.info(f"调整时间戳长度与验证集窗口匹配: {len(timestamps)}")
    
    # 获取当前参数版本
    current_version = get_latest_param_version()
    current_params = get_lightgbm_params()
    logger.info(f"当前参数版本: {current_version}")
    
    # 对每种算法类型进行优化
    algo_types = ['GBDT', 'DART', 'GOSS']
    boosting_types = ['gbdt', 'dart', 'goss']  # 与algo_types对应的boosting类型
    optimized_params = {}
    current_scores = {}
    new_scores = {}
    
    for i, (algo_type, boosting_type) in enumerate(zip(algo_types, boosting_types)):
        print_section(f"优化 {algo_type} 算法参数")
        logger.info(f"开始优化 {algo_type} 算法参数")
        
        # 准备数据
        X_train_flat = X_train_windows.reshape(X_train_windows.shape[0], -1)
        
        # 使用当前参数训练模型获取基准分数
        current_model_params = current_params[i].copy()
        logger.info(f"使用当前参数训练 {algo_type} 模型作为基准")
        
        # 训练当前参数的模型
        model = lgb.LGBMRegressor(**current_model_params)
        model.fit(X_train_flat, y_train_windows)
        
        # 在验证集上评估
        X_val_flat = X_val_windows.reshape(X_val_windows.shape[0], -1)
        y_pred = model.predict(X_val_flat)
        
        # 计算评分
        try:
            score, rmse, k = evaluate_with_time_weights(y_val_windows, y_pred, timestamps)
            current_scores[algo_type] = {"score": score, "rmse": rmse, "k": k}
            logger.info(f"当前 {algo_type} 参数基准分数: score={score:.4f}, rmse={rmse:.4f}, k={k:.4f}")
        except Exception as e:
            logger.error(f"计算当前参数评分出错: {str(e)}")
            # 使用简单的RMSE和K值评分作为基准
            rmse = calculate_rmse(y_val_windows, y_pred)
            k = calculate_k(y_val_windows, y_pred)
            
            # 归一化RMSE (使其在0到1之间，越小越好)
            # 这里假设RMSE最大不超过装机容量
            norm_rmse = min(1.0, rmse / 453.5)
            norm_weighted_rmse = 1 - norm_rmse  # 转换为越大越好
            
            # 综合评分 (加权平均)
            rmse_weight = 0.5
            k_weight = 0.5
            score = norm_weighted_rmse * rmse_weight + k * k_weight
            
            current_scores[algo_type] = {"score": score, "rmse": rmse, "k": k}
            logger.info(f"使用简单评分 - 当前 {algo_type} 参数基准分数: score={score:.4f}, rmse={rmse:.4f}, k={k:.4f}")
        
        # 使用随机搜索优化参数
        try:
            logger.info(f"开始 {algo_type} 的参数随机搜索")
            # 使用更新后的find_best_params函数，传入boosting_type和时间戳
            best_params = find_best_params(
                X_train_flat, 
                y_train_windows, 
                n_iter=PARAM_OPT_ITERATIONS,
                timestamps=timestamps if len(y_train_windows) == len(timestamps) else None,
                boosting_type=boosting_type
            )
            
            logger.info(f"找到 {algo_type} 的最佳参数: {best_params}")
            optimized_params[algo_type] = best_params
            
            # 使用最佳参数训练新模型
            model = lgb.LGBMRegressor(**best_params)
            model.fit(X_train_flat, y_train_windows)
            
            # 评估新模型
            y_pred = model.predict(X_val_flat)
            
            # 计算新模型的分数
            try:
                score, rmse, k = evaluate_with_time_weights(y_val_windows, y_pred, timestamps)
                new_scores[algo_type] = {"score": score, "rmse": rmse, "k": k}
                logger.info(f"新 {algo_type} 参数评分: score={score:.4f}, rmse={rmse:.4f}, k={k:.4f}")
            except Exception as e:
                logger.error(f"计算新参数评分出错: {str(e)}")
                # 使用简单的RMSE和K值评分
                rmse = calculate_rmse(y_val_windows, y_pred)
                k = calculate_k(y_val_windows, y_pred)
                
                # 归一化RMSE (使其在0到1之间，越小越好)
                norm_rmse = min(1.0, rmse / 453.5)
                norm_weighted_rmse = 1 - norm_rmse  # 转换为越大越好
                
                # 综合评分 (加权平均)
                rmse_weight = 0.5
                k_weight = 0.5
                score = norm_weighted_rmse * rmse_weight + k * k_weight
                
                new_scores[algo_type] = {"score": score, "rmse": rmse, "k": k}
                logger.info(f"使用简单评分 - 新 {algo_type} 参数评分: score={score:.4f}, rmse={rmse:.4f}, k={k:.4f}")
        
        except Exception as e:
            logger.error(f"{algo_type} 参数优化失败: {str(e)}")
            # 使用当前参数作为最佳参数
            optimized_params[algo_type] = current_params[i]
            new_scores[algo_type] = current_scores[algo_type]
    
    # 检查是否所有算法都有足够的改进
    all_improved = True
    significant_improvement = True
    
    for algo_type in algo_types:
        if algo_type in new_scores and algo_type in current_scores:
            # 检查是否有改进
            improved = new_scores[algo_type]["score"] > current_scores[algo_type]["score"]
            
            # 计算改进百分比
            old_score = current_scores[algo_type]["score"]
            new_score = new_scores[algo_type]["score"]
            improvement_pct = ((new_score - old_score) / old_score) * 100 if old_score > 0 else 0
            
            # 检查改进是否足够显著
            significant = improvement_pct >= (PARAM_OPT_MIN_IMPROVEMENT * 100)
            
            logger.info(f"{algo_type} 参数改进: {improved} (新分数: {new_score:.4f}, 旧分数: {old_score:.4f}, 改进: {improvement_pct:.2f}%)")
            logger.info(f"{algo_type} 改进是否显著: {significant} (最小阈值: {PARAM_OPT_MIN_IMPROVEMENT * 100}%)")
            
            all_improved = all_improved and improved
            significant_improvement = significant_improvement and significant
    
    # 创建新的版本号（使用当前日期）
    new_version = datetime.now().strftime('%Y%m%d')
    
    # 如果所有算法都有显著改进，更新参数文件
    if all_improved and significant_improvement:
        print_section("更新所有算法参数")
        logger.info("所有算法参数均有显著改进，更新参数文件")
        
        # 添加新参数版本
        success = add_new_param_version(
            new_version,
            optimized_params['GBDT'],
            optimized_params['DART'],
            optimized_params['GOSS']
        )
        
        if success:
            # 保存到文件
            if save_param_versions_to_file():
                logger.info(f"成功更新参数文件，新版本: {new_version}")
                
                # 记录改进百分比
                improvement_log = {}
                for algo_type in algo_types:
                    old_score = current_scores[algo_type]["score"]
                    new_score = new_scores[algo_type]["score"]
                    improvement = ((new_score - old_score) / old_score) * 100 if old_score > 0 else 0
                    improvement_log[algo_type] = {
                        "old_score": old_score,
                        "new_score": new_score,
                        "improvement": f"{improvement:.2f}%"
                    }
                
                logger.info(f"参数优化改进情况: {improvement_log}")
                
                # 标记本周参数优化已完成
                mark_weekly_optimization_done()
                return True
            else:
                logger.error("保存参数文件失败")
        else:
            logger.error(f"添加新参数版本失败")
    else:
        # 分别检查每种算法是否有显著改进，单独更新有显著改进的算法参数
        print_section("更新部分算法参数")
        logger.info("不是所有算法都有显著改进，分别检查更新")
        
        # 准备要更新的参数
        gbdt_params = current_params[0]
        dart_params = current_params[1]
        goss_params = current_params[2]
        
        # 记录更新情况
        update_log = {}
        has_updates = False
        
        # 检查每种算法
        for i, algo_type in enumerate(algo_types):
            if algo_type in new_scores and algo_type in current_scores:
                # 检查是否有显著改进
                old_score = current_scores[algo_type]["score"]
                new_score = new_scores[algo_type]["score"]
                improved = new_score > old_score
                improvement_pct = ((new_score - old_score) / old_score) * 100 if old_score > 0 else 0
                significant = improvement_pct >= (PARAM_OPT_MIN_IMPROVEMENT * 100)
                
                if improved and significant:
                    logger.info(f"{algo_type} 参数有显著改进，将更新其参数")
                    # 更新对应算法的参数
                    if algo_type == 'GBDT':
                        gbdt_params = optimized_params['GBDT']
                    elif algo_type == 'DART':
                        dart_params = optimized_params['DART']
                    elif algo_type == 'GOSS':
                        goss_params = optimized_params['GOSS']
                    
                    has_updates = True
                    update_log[algo_type] = {
                        "old_score": old_score,
                        "new_score": new_score,
                        "improvement": f"{improvement_pct:.2f}%",
                        "updated": True
                    }
                else:
                    logger.info(f"{algo_type} 参数没有显著改进，保持当前参数不变")
                    update_log[algo_type] = {
                        "old_score": old_score,
                        "new_score": new_score,
                        "improvement": f"{improvement_pct:.2f}%",
                        "updated": False
                    }
        
        # 如果有任何更新，保存新参数
        if has_updates:
            # 添加新参数版本
            success = add_new_param_version(
                new_version,
                gbdt_params,
                dart_params,
                goss_params
            )
            
            if success:
                # 保存到文件
                if save_param_versions_to_file():
                    logger.info(f"成功更新部分算法参数，新版本: {new_version}")
                    logger.info(f"参数更新情况: {update_log}")
                    
                    # 标记本周参数优化已完成
                    mark_weekly_optimization_done()
                    return True
                else:
                    logger.error("保存参数文件失败")
            else:
                logger.error(f"添加新参数版本失败")
        else:
            logger.info("没有任何算法参数达到显著改进标准，保持当前参数不变")
    
    # 无论是否更新了参数，都标记本周参数优化已完成
    mark_weekly_optimization_done()
    return False

if __name__ == "__main__":
    try:
        optimize_params()
    except Exception as e:
        logger.error(f"参数优化过程中发生错误: {str(e)}") 