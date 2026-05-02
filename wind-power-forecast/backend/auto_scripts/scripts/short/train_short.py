# train_short.py
from sklearn.metrics import mean_squared_error
import lightgbm as lgb
import pandas as pd
import numpy as np
import os
import logging
import sys
import joblib  # 用于保存模型和 scaler
import gc  # 添加垃圾回收模块
import pickle  # 用于保存特征重要性
from config_short import Today, FEATURE_IMPORTANCE_DIR
from utils_short import (
    calculate_daily_averaged_k,
    evaluate_with_time_weights,
    normalize_rmse_score,
)
from data_processor_short import (
    preprocess_data, filter_data_by_date, feature_engineering,
    scale_data, create_time_window_pre,
    create_flattened_windows_with_indices
)
from models_short import get_unified_params
import psutil

# 获取logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 添加控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 处理Windows控制台输出编码
if sys.platform == 'win32':
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    # 确保stderr也使用utf-8编码
    sys.stderr.reconfigure(encoding='utf-8')

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
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    print(f"当前内存占用: {memory_mb:.2f} MB")
    logger.info(f"当前内存占用: {memory_mb:.2f} MB")
    return memory_mb

def train_and_evaluate(X_train, y_train, X_val, y_val, params_list, scaler, model_folder_today, val_timestamps=None, feature_names=None, save_importance=True):
    print_separator("开始模型训练与评估")
    results_dict = {}
    save_path = model_folder_today
    
    # 创建目录结构
    os.makedirs(save_path, exist_ok=True)
    print(f"模型和 scaler 将被保存到目录: {save_path}")
    logger.info(f"模型和 scaler 将被保存到目录: {save_path}")
    
    # 初始化变量以跟踪最佳模型
    best_mse = float('inf')
    best_model = None
    best_model_name = ""
    
    # 确保X_train和X_val已经是扁平化的2D数组
    if len(X_train.shape) > 2:
        print(f"将3D训练数据扁平化: {X_train.shape}")
        logger.info(f"将3D训练数据扁平化: {X_train.shape}")
        X_train = X_train.reshape(X_train.shape[0], -1)
    
    if len(X_val.shape) > 2:
        print(f"将3D验证数据扁平化: {X_val.shape}")
        logger.info(f"将3D验证数据扁平化: {X_val.shape}")
        X_val = X_val.reshape(X_val.shape[0], -1)
    
    # 确保数据类型是float32以减少内存占用
    if X_train.dtype != np.float32:
        print(f"将训练数据转换为float32类型")
        logger.info(f"将训练数据转换为float32类型")
        X_train = X_train.astype(np.float32)
    
    if X_val.dtype != np.float32:
        print(f"将验证数据转换为float32类型")
        logger.info(f"将验证数据转换为float32类型")
        X_val = X_val.astype(np.float32)
    
    if y_train.dtype != np.float32:
        y_train = y_train.astype(np.float32)
    
    if y_val.dtype != np.float32:
        y_val = y_val.astype(np.float32)
    
    for params in params_list:
        print_separator(f"训练 {params['name']} 模型")
        # 初始化模型
        print(f"模型参数: {params}")
        logger.info(f"模型参数: {params}")
        model = lgb.LGBMRegressor(**params)
        
        # 训练模型
        print(f"开始训练 {params['name']} 模型...")
        logger.info(f"开始训练 {params['name']} 模型...")
        
        # DART模式不支持早停，其他模式使用早停
        if params.get('boosting_type') == 'dart':
            model.fit(X_train, y_train, 
                    eval_set=[(X_val, y_val)],
                    eval_metric='rmse')
        else:
            model.fit(X_train, y_train, 
                    eval_set=[(X_val, y_val)],
                    eval_metric='rmse',
                    callbacks=[lgb.early_stopping(10)])
        
        print(f"{params['name']} 模型训练完成")
        logger.info(f"{params['name']} 模型训练完成")
        
        # 预测验证集
        print(f"使用 {params['name']} 模型预测验证集...")
        logger.info(f"使用 {params['name']} 模型预测验证集...")
        y_pred = model.predict(X_val)
        
        # 计算 MSE
        mse = mean_squared_error(y_val, y_pred)
        rmse = np.sqrt(mse)
        k = calculate_daily_averaged_k(y_val, y_pred)
        
        # 计算带时间权重的评分（如果提供了时间戳）
        weighted_score = None
        if val_timestamps is not None:
            # 确保时间戳与预测值长度一致
            if len(val_timestamps) != len(y_val):
                print(f"⚠️ 时间戳长度 ({len(val_timestamps)}) 与预测值长度 ({len(y_val)}) 不匹配，调整时间戳...")
                logger.info(f"⚠️ 时间戳长度 ({len(val_timestamps)}) 与预测值长度 ({len(y_val)}) 不匹配，调整时间戳...")
                
                if len(val_timestamps) > len(y_val):
                    val_timestamps = val_timestamps[-len(y_val):]
                    print(f"时间戳已截断至匹配验证集长度: {len(val_timestamps)}")
                    logger.info(f"时间戳已截断至匹配验证集长度: {len(val_timestamps)}")
                else:
                    print(f"时间戳长度不足，将使用非时间加权评分")
                    logger.info(f"时间戳长度不足，将使用非时间加权评分")
                    val_timestamps = None
            
            if val_timestamps is not None:
                print(f"使用时间加权方式计算模型评分...")
                logger.info(f"使用时间加权方式计算模型评分...")
                try:
                    weighted_score, _, _, weighted_rmse, weighted_k = evaluate_with_time_weights(y_val, y_pred, val_timestamps)
                except Exception as e:
                    print(f"⚠️ 时间加权评分计算失败: {str(e)}，将使用简单加权评分")
                    logger.info(f"⚠️ 时间加权评分计算失败: {str(e)}，将使用简单加权评分")
                    weighted_score = None
                    weighted_rmse = None
                    weighted_k = None
        
        if weighted_score is None:
            # 没有时间戳或计算失败时使用简单评分：(1-归一化RMSE)*0.5 + k*0.5
            print(f"使用简单加权方式计算模型评分...")
            logger.info(f"使用简单加权方式计算模型评分...")
            norm_rmse = normalize_rmse_score(rmse)
            weighted_score = (1 - norm_rmse) * 0.5 + k * 0.5
            weighted_rmse = rmse  # 使用标准RMSE作为加权RMSE
            weighted_k = k       # 使用标准K作为加权K
        
        # 存储结果
        results_dict[params['name']] = {
            'model': model,
            'y_pred': y_pred,
            'mse': mse,
            'rmse': rmse,
            'k': k,
            'weighted_score': weighted_score,
            'weighted_rmse': weighted_rmse,
            'weighted_k': weighted_k
        }
        print(f"{params['name']} 评估结果 - RMSE: {rmse:.4f}, K: {k:.4f}, 加权评分: {weighted_score:.4f}")
        print(f"  时间加权结果 - 加权RMSE: {weighted_rmse:.4f}, 加权K: {weighted_k:.4f}")
        logger.info(f"{params['name']} 评估结果 - RMSE: {rmse:.4f}, K: {k:.4f}, 加权评分: {weighted_score:.4f}")
        logger.info(f"  时间加权结果 - 加权RMSE: {weighted_rmse:.4f}, 加权K: {weighted_k:.4f}")
        
        # 保存特征重要性（如果有特征名列表且save_importance为True）
        if save_importance and feature_names is not None:
            # 确保特征名列表长度与模型特征数量一致
            if len(feature_names) == X_train.shape[1]:
                # feature_importances = model.feature_importances_
                # feature_importances = model.feature_importances_(importance_type='gain') 
                # 直接访问 feature_importances_ 属性
                feature_importances = model.feature_importances_
                
                # 使用固定的特征重要性目录
                importance_file = os.path.join(FEATURE_IMPORTANCE_DIR, f'{params["name"]}_feature_importance.pkl')
                
                feature_importance_dict = {
                    'features': feature_names,
                    'importances': feature_importances,
                    'date': Today
                }
                
                # 保存特征重要性
                with open(importance_file, 'wb') as f:
                    pickle.dump(feature_importance_dict, f)
                
                print(f"✅ {params['name']} 模型的特征重要性已保存到 {importance_file}")
                logger.info(f"✅ {params['name']} 模型的特征重要性已保存到 {importance_file}")
            else:
                print(f"⚠️ 特征名列表长度 ({len(feature_names)}) 与模型特征数量 ({X_train.shape[1]}) 不匹配，无法保存特征重要性")
                logger.warning(f"⚠️ 特征名列表长度 ({len(feature_names)}) 与模型特征数量 ({X_train.shape[1]}) 不匹配，无法保存特征重要性")
        
        # 检查是否为当前最佳模型（基于加权评分）
        if weighted_score is not None and (best_model is None or weighted_score > results_dict[best_model_name]['weighted_score']):
            best_model = model
            best_model_name = params['name']
            print(f"✅ {params['name']} 成为当前最佳模型 (基于加权评分)")
            logger.info(f"✅ {params['name']} 成为当前最佳模型 (基于加权评分)")
        # 如果没有加权评分，则使用MSE
        elif weighted_score is None and mse < best_mse:
            best_mse = mse
            best_model = model
            best_model_name = params['name']
            print(f"✅ {params['name']} 成为当前最佳模型 (基于MSE)")
            logger.info(f"✅ {params['name']} 成为当前最佳模型 (基于MSE)")
        
        # 保存当前模型
        model_filename = f"{params['name']}.joblib"
        model_filepath = os.path.join(save_path, model_filename)
        joblib.dump(model, model_filepath)
        print(f"{params['name']} 模型已保存到 {model_filepath}")
        logger.info(f"{params['name']} 模型已保存到 {model_filepath}")
        
        # 清理一下内存
        gc.collect()
    
    # 保存 scaler
    scaler_filename = 'scaler.joblib'
    scaler_filepath = os.path.join(save_path, scaler_filename)
    joblib.dump(scaler, scaler_filepath)
    print(f"Scaler 已保存到 {scaler_filepath}")
    logger.info(f"Scaler 已保存到 {scaler_filepath}")
    
    # 如果找到最佳模型，则额外保存为 'model.joblib'
    if best_model is not None:
        best_model_filepath = os.path.join(save_path, 'model.joblib')
        joblib.dump(best_model, best_model_filepath)
        print(f"最佳模型 '{best_model_name}' 已额外保存到 {best_model_filepath}")
        logger.info(f"最佳模型 '{best_model_name}' 已额外保存到 {best_model_filepath}")
    else:
        print("未找到最佳模型。")
        logger.info("未找到最佳模型。")
    
    return results_dict

def split_data(X, y, train_ratio):
    """
    按顺序拆分训练集和验证集
    """
    split_index = int(len(X) * train_ratio)
    X_train, X_val = X[:split_index].copy(), X[split_index:].copy()
    y_train, y_val = y[:split_index].copy(), y[split_index:].copy()
    return X_train, X_val, y_train, y_val

def train_multiple_datasets(data, months_list, train_ratio, lags, window_size, model_folder_today):
    """
    使用不同时间段的数据训练多个模型，并选择最佳模型
    
    参数:
    data: 原始数据
    months_list: 要使用的月份列表 [1, 3, 6, 9, 12, None]
    train_ratio: 训练集比例
    lags: 滞后特征数量
    window_size: 窗口大小
    model_folder_today: 模型保存路径
    
    返回:
    最佳模型信息的字典
    """
    # 记录初始内存
    initial_memory = print_memory_usage()
    
    print_separator("使用多个数据集训练模型")
    # 创建存储最佳模型的目录
    best_models_dir = os.path.join(model_folder_today, 'best_models')
    os.makedirs(best_models_dir, exist_ok=True)
    print(f"最佳模型将保存到: {best_models_dir}")
    logger.info(f"最佳模型将保存到: {best_models_dir}")
    
    # 获取统一参数
    all_params = get_unified_params()
    print(f"获取统一参数成功，包含 {len(all_params)} 种模型类型")
    logger.info(f"获取统一参数成功，包含 {len(all_params)} 种模型类型")
    
    # 为每种算法类型存储最佳模型
    best_models = {
        'GBDT': {'model': None, 'score': -float('inf'), 'months': None, 'scaler': None},
        'DART': {'model': None, 'score': -float('inf'), 'months': None, 'scaler': None},
        'GOSS': {'model': None, 'score': -float('inf'), 'months': None, 'scaler': None},
    }
    
    # 存储所有训练结果
    all_results = {}
    
    # 新增：存储全量数据的处理结果，用于后续重训练
    full_data_processed = {
        'X_train_flat': None,
        'X_val_flat': None,
        'y_train_windows': None,
        'y_val_windows': None,
        'flat_feature_names': None,
        'val_timestamps': None,
        'scaler': None
    }
    
    # 新增：标记需要重训练的算法类型
    needs_retraining = {'GBDT': False, 'DART': False, 'GOSS': False}
    
    # 1. 对每个时间段分别训练
    for months in months_list:
        print_separator(f"训练数据集: {months}个月" if months else "训练数据集: 全部数据")
        months_desc = f"{months}个月" if months else "全部数据"
        print(f"使用{months_desc}的数据进行训练...")
        logger.info(f"使用{months_desc}的数据进行训练...")
        
        # 过滤数据
        print(f"过滤数据为最近{months_desc}..." if months else "使用全部数据...")
        logger.info(f"过滤数据为最近{months_desc}..." if months else "使用全部数据...")
        filtered_data = filter_data_by_date(data, months)
        print(f"过滤后的数据量: {len(filtered_data)}")
        logger.info(f"过滤后的数据量: {len(filtered_data)}")
        
        try:
            # 打印数据过滤后内存
            print_memory_usage()
        except:
            pass
        
        # 预处理数据
        print(f"对{months_desc}数据进行预处理...")
        logger.info(f"对{months_desc}数据进行预处理...")
        X, y = preprocess_data(filtered_data)
        print(f"预处理后的特征维度: {X.shape}, 目标变量维度: {y.shape}")
        logger.info(f"预处理后的特征维度: {X.shape}, 目标变量维度: {y.shape}")
        
        X_train, X_val, y_train, y_val = split_data(X, y, train_ratio)
        print(f"数据集划分完成，训练集: {X_train.shape}, 验证集: {X_val.shape}")
        logger.info(f"数据集划分完成，训练集: {X_train.shape}, 验证集: {X_val.shape}")
        
        # 提取验证集的时间戳，用于时间加权评估
        val_timestamps = None
        if 'Timestamp' in filtered_data.columns:
            val_timestamps = filtered_data['Timestamp'].iloc[int(len(filtered_data) * train_ratio):].values
            print(f"提取了 {len(val_timestamps)} 个验证集时间戳，用于时间加权评估")
            logger.info(f"提取了 {len(val_timestamps)} 个验证集时间戳，用于时间加权评估")
        else:
            print("无法获取时间戳，将使用简单加权评估")
            logger.info("无法获取时间戳，将使用简单加权评估")
        
        try:
            # 打印预处理后内存
            print_memory_usage()
        except:
            pass
        
        # 特征工程
        print(f"执行特征工程，滞后特征数: {lags}...")
        logger.info(f"执行特征工程，滞后特征数: {lags}...")
        
        # 改为分别对训练集和验证集进行特征工程
        X_train_fe, nan_indices_train = feature_engineering(X_train, lags)
        X_val_fe, nan_indices_val = feature_engineering(X_val, lags)
        
        print(f"特征工程后，训练集: {X_train_fe.shape}, 验证集: {X_val_fe.shape}")
        logger.info(f"特征工程后，训练集: {X_train_fe.shape}, 验证集: {X_val_fe.shape}")
        
        # 从y中同时删除NaN对应的行，保持X和y对齐
        y_train = y_train.drop(index=nan_indices_train)
        y_val = y_val.drop(index=nan_indices_val)
        
        # 同样删除X中NaN行
        X_train = X_train_fe.drop(index=nan_indices_train)
        X_val = X_val_fe.drop(index=nan_indices_val)
        
        print(f"移除NaN后，训练集: {X_train.shape}, 训练集目标变量: {len(y_train)}")
        print(f"移除NaN后，验证集: {X_val.shape}, 验证集目标变量: {len(y_val)}")
        logger.info(f"移除NaN后，训练集: {X_train.shape}, 训练集目标变量: {len(y_train)}")
        logger.info(f"移除NaN后，验证集: {X_val.shape}, 验证集目标变量: {len(y_val)}")
        
        # 如果有时间戳，也需要相应调整
        if val_timestamps is not None and len(nan_indices_val) > 0:
            # 获取保留的索引
            kept_indices = np.setdiff1d(np.arange(len(X_val) + len(nan_indices_val)), nan_indices_val)
            val_timestamps = val_timestamps[kept_indices]
            print(f"调整后的时间戳数量: {len(val_timestamps)}")
            logger.info(f"调整后的时间戳数量: {len(val_timestamps)}")
        
        try:
            # 打印特征工程后内存
            print_memory_usage()
        except:
            pass
        
        # 标准化
        print("标准化数据...")
        logger.info("标准化数据...")
        X_train_scaled, X_val_scaled, scaler = scale_data(X_train, X_val)
        print(f"标准化后，训练集: {X_train_scaled.shape}, 验证集: {X_val_scaled.shape}")
        logger.info(f"标准化后，训练集: {X_train_scaled.shape}, 验证集: {X_val_scaled.shape}")
        
        try:
            # 打印标准化后内存
            print_memory_usage()
        except:
            pass
        
        # 创建时间窗口 - 使用新的扁平化窗口创建函数
        print(f"创建时间窗口，窗口大小: {window_size}...")
        logger.info(f"创建时间窗口，窗口大小: {window_size}...")
        
        # 使用优化的扁平化窗口创建函数
        X_train_flat, y_train_windows, _ = create_flattened_windows_with_indices(
            X_train_scaled, y_train, window_size
        )
        X_val_flat, y_val_windows, val_target_indices = create_flattened_windows_with_indices(
            X_val_scaled, y_val, window_size
        )
        
        print(f"窗口创建后，训练集: {X_train_flat.shape}, 训练集目标: {y_train_windows.shape}")
        print(f"窗口创建后，验证集: {X_val_flat.shape}, 验证集目标: {y_val_windows.shape}")
        logger.info(f"窗口创建后，训练集: {X_train_flat.shape}, 训练集目标: {y_train_windows.shape}")
        logger.info(f"窗口创建后，验证集: {X_val_flat.shape}, 验证集目标: {y_val_windows.shape}")
        
        # 生成扁平化特征名列表（用于特征重要性保存）
        original_feature_names = X_train.columns.tolist()
        flat_feature_names = generate_flat_feature_names(original_feature_names, window_size)
        
        # 如果是全量数据，保存处理结果用于后续重训练
        if months is None:
            full_data_processed['X_train_flat'] = X_train_flat
            full_data_processed['X_val_flat'] = X_val_flat
            full_data_processed['y_train_windows'] = y_train_windows
            full_data_processed['y_val_windows'] = y_val_windows
            full_data_processed['flat_feature_names'] = flat_feature_names
            full_data_processed['val_timestamps'] = val_timestamps
            full_data_processed['scaler'] = scaler
            print(f"✅ 保存全量数据处理结果，用于后续可能的重训练")
            logger.info(f"✅ 保存全量数据处理结果，用于后续可能的重训练")
        
        # 清理不再需要的数据以释放内存
        del X_train_scaled, X_val_scaled
        gc.collect()
        
        try:
            # 打印窗口创建后内存
            print_memory_usage()
        except:
            pass
        
        # 调整验证集时间戳以匹配窗口化后的数据
        if val_timestamps is not None:
            # 检查是否有索引信息
            if val_target_indices is not None:
                # 使用索引获取相应的时间戳
                # 注意：可能需要额外逻辑来确保正确匹配，因为val_target_indices存储的是y_val的原始索引
                # 而val_timestamps可能是从filtered_data中获取的
                # 需要确保它们之间的对应关系
                if len(val_target_indices) == len(y_val_windows):
                    try:
                        # 尝试调整时间戳
                        trimmed_timestamps = []
                        print(f"DEBUG: val_target_indices sample: {val_target_indices[:5] if len(val_target_indices) > 5 else val_target_indices}")
                        logger.info(f"DEBUG: val_target_indices sample: {val_target_indices[:5] if len(val_target_indices) > 5 else val_target_indices}")
                        for idx in val_target_indices:
                            # 假设idx是filtered_data中的【标签】索引
                            if idx in filtered_data.index:  # 检查【标签】是否存在于索引中
                                trimmed_timestamps.append(filtered_data['Timestamp'].loc[idx])  # 使用.loc访问
                            else:
                                # 这个标签索引不在filtered_data中（可能因为过滤或其他原因丢失）
                                print(f"警告: 索引标签 {idx} 不在 filtered_data (长度 {len(filtered_data)}) 的索引中")
                                logger.warning(f"警告: 索引标签 {idx} 不在 filtered_data (长度 {len(filtered_data)}) 的索引中")
                        
                        if len(trimmed_timestamps) == len(y_val_windows):
                            val_timestamps = pd.to_datetime(trimmed_timestamps)
                            print(f"成功调整时间戳数量: {len(val_timestamps)}")
                            logger.info(f"成功调整时间戳数量: {len(val_timestamps)}")
                        else:
                            print(f"警告: 调整后的时间戳数量({len(trimmed_timestamps)})与验证集窗口数量({len(y_val_windows)})不匹配, 将不使用时间戳")
                            logger.warning(f"警告: 调整后的时间戳数量({len(trimmed_timestamps)})与验证集窗口数量({len(y_val_windows)})不匹配, 将不使用时间戳")
                            val_timestamps = None  # 放弃使用时间戳
                    except Exception as e:
                        print(f"调整时间戳时发生错误: {str(e)}")
                        logger.error(f"调整时间戳时发生错误: {str(e)}")
                        val_timestamps = None  # 出错则放弃
                else:
                    print(f"警告: 验证集目标索引数量({len(val_target_indices)})与验证集窗口数量({len(y_val_windows)})不匹配, 将不使用时间戳")
                    logger.warning(f"警告: 验证集目标索引数量({len(val_target_indices)})与验证集窗口数量({len(y_val_windows)})不匹配, 将不使用时间戳")
                    val_timestamps = None
            else:
                # 简单地使用最后len(y_val_windows)个时间戳
                if len(val_timestamps) >= len(y_val_windows):
                    val_timestamps = val_timestamps[-len(y_val_windows):]
                else:
                    # 时间戳不足，放弃使用
                    val_timestamps = None
        
        # 依次对每种算法应用特征选择
        print_separator(f"对{months_desc}数据进行特征选择")
        logger.info(f"对{months_desc}数据进行特征选择")
        
        # 为不同算法类型存储选择后的特征
        selected_features_dict = {}
        X_train_selected_dict = {}
        X_val_selected_dict = {}
        
        # 新增：记录是否为强制更新/首次运行
        is_forced_update_run = {}
        
        # 创建当前月份的模型文件夹
        current_model_folder = os.path.join(model_folder_today, f"{months}months" if months else "all")
        os.makedirs(current_model_folder, exist_ok=True)
        
        # 对每种算法应用特征选择
        for params in all_params:
            algo_type = params['name'].split('_')[0]  # 例如 'GBDT_1' -> 'GBDT'
            
            # 应用特征选择（不再检查模型文件夹，而是从固定目录加载特征重要性）
            print(f"检查{algo_type}的特征重要性文件并应用特征选择...")
            logger.info(f"检查{algo_type}的特征重要性文件并应用特征选择...")
            X_train_selected, X_val_selected, selected_features = apply_feature_selection(
                X_train_flat, X_val_flat, flat_feature_names, 
                algo_type, top_n=3000, current_date=Today
            )
            
            # 新增：判断是否返回了全部特征（强制更新或首次运行）
            is_forced_update_run[algo_type] = (len(selected_features) == len(flat_feature_names))
            if is_forced_update_run[algo_type]:
                print(f"ℹ️ {algo_type} 模型将使用全部特征进行训练（强制更新或首次运行）")
                logger.info(f"ℹ️ {algo_type} 模型将使用全部特征进行训练（强制更新或首次运行）")
                
                # 如果是全数据周期且是强制更新，标记该算法类型需要重训练
                if months is None:
                    needs_retraining[algo_type] = True
                    print(f"⚠️ 标记 {algo_type} 为需要重训练状态")
                    logger.warning(f"⚠️ 标记 {algo_type} 为需要重训练状态")
            else:
                print(f"ℹ️ {algo_type} 模型将使用选择的 {len(selected_features)} 个特征进行训练")
                logger.info(f"ℹ️ {algo_type} 模型将使用选择的 {len(selected_features)} 个特征进行训练")
            
            # 存储特征选择结果
            selected_features_dict[algo_type] = selected_features
            X_train_selected_dict[algo_type] = X_train_selected
            X_val_selected_dict[algo_type] = X_val_selected
        
        # 模型训练与评估
        results = {}
        for params in all_params:
            algo_type = params['name'].split('_')[0]
            model_name = params['name']
            
            print_separator(f"训练 {model_name} 模型 (使用{months_desc}数据)")
            logger.info(f"训练 {model_name} 模型 (使用{months_desc}数据)")
            
            # 使用对应算法类型的选择特征
            X_train_selected = X_train_selected_dict[algo_type]
            X_val_selected = X_val_selected_dict[algo_type]
            selected_features = selected_features_dict[algo_type]
            
            # 决定是否保存特征重要性（只在处理全部数据且使用全部特征时保存）
            should_save_importance = (months is None)
            # 修改：传递强制更新状态
            # 只有在是全数据周期 且 这次运行确实用了全特征时，才真的应该保存
            should_really_save = should_save_importance and is_forced_update_run[algo_type]
            
            if should_really_save:
                print(f"ℹ️ 满足保存条件 (全数据周期 + 强制更新/首次运行)，将保存 {model_name} 的特征重要性")
                logger.info(f"ℹ️ 满足保存条件 (全数据周期 + 强制更新/首次运行)，将保存 {model_name} 的特征重要性")
            elif should_save_importance:  # months is None 但 is_forced_update_run is False
                print(f"ℹ️ 全数据周期，但使用筛选特征，不覆盖 {model_name} 的特征重要性")
                logger.info(f"ℹ️ 全数据周期，但使用筛选特征，不覆盖 {model_name} 的特征重要性")
            
            # --- BEGIN MODIFICATION ---
            logger.info(f"[短效] 即将为模型 {model_name} (数据源: {months_desc}) 开始训练。")
            # --- END MODIFICATION ---
            
            # 训练单个模型
            model_results = train_and_evaluate(
                X_train_selected, y_train_windows,
                X_val_selected, y_val_windows,
                [params], scaler, current_model_folder,
                val_timestamps, selected_features,  # 传递特征名，用于保存特征重要性
                save_importance=should_really_save  # 只在months=None且使用全部特征时保存特征重要性
            )
            
            # 合并结果
            results.update(model_results)
            
            # 清理内存
            gc.collect()
        
        # 存储结果
        all_results[months] = results
        
        # 更新最佳模型
        for model_name, result in results.items():
            # 提取算法类型
            if 'GBDT' in model_name:
                algo_type = 'GBDT'
            elif 'DART' in model_name:
                algo_type = 'DART'
            elif 'GOSS' in model_name:
                algo_type = 'GOSS'
            else:
                print(f"未知算法类型: {model_name}")
                logger.info(f"未知算法类型: {model_name}")
                continue
            
            # 如果当前模型评分优于最佳模型，则更新
            if result['weighted_score'] > best_models[algo_type]['score']:
                best_models[algo_type]['model'] = result['model']
                best_models[algo_type]['score'] = result['weighted_score']
                best_models[algo_type]['months'] = months
                best_models[algo_type]['scaler'] = scaler
                print(f"✅ 使用{months_desc}的数据训练的{model_name}成为{algo_type}类型的最佳模型")
                logger.info(f"✅ 使用{months_desc}的数据训练的{model_name}成为{algo_type}类型的最佳模型")
        
        # 清理内存
        del X_train, X_val, y_train, y_val, X_train_flat, X_val_flat, y_train_windows, y_val_windows
        # 清理特征选择的中间结果
        del X_train_selected_dict, X_val_selected_dict, selected_features_dict
        gc.collect()
    
    # 全部数据训练完成后，执行重训练步骤
    print_separator("检查需要重训练的模型")
    logger.info("检查需要重训练的模型")
    
    # 检查是否有需要重训练的算法类型
    has_retraining_models = any(needs_retraining.values())
    if has_retraining_models:
        print(f"⚠️ 检测到需要重训练的模型: {[algo for algo, need in needs_retraining.items() if need]}")
        logger.warning(f"⚠️ 检测到需要重训练的模型: {[algo for algo, need in needs_retraining.items() if need]}")
        
        # 确认全量数据处理结果是否可用
        if full_data_processed['X_train_flat'] is None:
            print(f"❌ 全量数据处理结果不可用，无法进行重训练")
            logger.error(f"❌ 全量数据处理结果不可用，无法进行重训练")
        else:
            # 从保存的全量数据处理结果中获取数据
            X_train_flat = full_data_processed['X_train_flat']
            X_val_flat = full_data_processed['X_val_flat']
            y_train_windows = full_data_processed['y_train_windows']
            y_val_windows = full_data_processed['y_val_windows']
            flat_feature_names = full_data_processed['flat_feature_names']
            val_timestamps = full_data_processed['val_timestamps']
            scaler = full_data_processed['scaler']
            
            print(f"✅ 成功加载全量数据处理结果，准备重训练")
            logger.info(f"✅ 成功加载全量数据处理结果，准备重训练")
            
            # 获取全量数据的模型文件夹
            full_data_model_folder = os.path.join(model_folder_today, "all")
            
            # 对每种需要重训练的算法类型进行重训练
            for algo_type, need_retrain in needs_retraining.items():
                if need_retrain:
                    print_separator(f"重新训练 {algo_type} 最佳模型 (使用Top N特征)")
                    logger.info(f"重新训练 {algo_type} 最佳模型 (使用Top N特征)")
                    
                    try:
                        # 1. 重新加载刚刚保存的重要性文件，获取Top N特征
                        top_features, selected_indices = get_top_features(algo_type, top_n=3000, current_date=Today)
                        if top_features is None or selected_indices is None:
                            print(f"❌ 无法加载 {algo_type} 的特征重要性文件，无法重新训练！")
                            logger.error(f"❌ 无法加载 {algo_type} 的特征重要性文件，无法重新训练！")
                            continue
                        
                        # 2. 使用这些索引筛选全量数据
                        X_train_retrain = X_train_flat[:, selected_indices]
                        X_val_retrain = X_val_flat[:, selected_indices]
                        selected_features_retrain = ensure_feature_consistency(flat_feature_names, selected_indices)
                        
                        print(f"✅ 已筛选出 {algo_type} 的Top {len(selected_indices)} 个特征，准备重训练")
                        logger.info(f"✅ 已筛选出 {algo_type} 的Top {len(selected_indices)} 个特征，准备重训练")
                        
                        # 3. 找到该算法类型对应的最佳参数配置
                        best_params_for_algo = None
                        for params in all_params:
                            if params['name'].split('_')[0] == algo_type:
                                # 使用第一个找到的该类型的参数配置
                                best_params_for_algo = params
                                break
                        
                        if best_params_for_algo is None:
                            print(f"❌ 找不到 {algo_type} 的参数配置，无法重新训练！")
                            logger.error(f"❌ 找不到 {algo_type} 的参数配置，无法重新训练！")
                            continue
                        
                        # 4. 重新训练模型
                        print(f"重新训练 {best_params_for_algo['name']} 使用 {len(selected_features_retrain)} 个特征...")
                        logger.info(f"重新训练 {best_params_for_algo['name']} 使用 {len(selected_features_retrain)} 个特征...")
                        
                        retrain_results = train_and_evaluate(
                            X_train_retrain, y_train_windows,
                            X_val_retrain, y_val_windows,
                            [best_params_for_algo], scaler, full_data_model_folder,
                            val_timestamps, selected_features_retrain,
                            save_importance=False  # 不需要再次保存特征重要性
                        )
                        
                        # 5. 更新best_models字典中的模型
                        if best_params_for_algo['name'] in retrain_results:
                            # 获取重训练模型的评分
                            retrain_score = retrain_results[best_params_for_algo['name']]['weighted_score']
                            
                            # 更新最佳模型（无条件更新，确保使用Top N特征的模型）
                            best_models[algo_type]['model'] = retrain_results[best_params_for_algo['name']]['model']
                            best_models[algo_type]['score'] = retrain_score
                            best_models[algo_type]['months'] = None  # 表示使用全量数据
                            best_models[algo_type]['scaler'] = scaler
                            
                            print(f"✅ {algo_type} 的最佳模型已使用Top {len(selected_indices)} 个特征重新训练并更新")
                            logger.info(f"✅ {algo_type} 的最佳模型已使用Top {len(selected_indices)} 个特征重新训练并更新")
                            print(f"    新模型评分: {retrain_score:.4f}")
                            logger.info(f"    新模型评分: {retrain_score:.4f}")
                        else:
                            print(f"❌ 重新训练 {best_params_for_algo['name']} 后未找到结果，未更新最佳模型")
                            logger.error(f"❌ 重新训练 {best_params_for_algo['name']} 后未找到结果，未更新最佳模型")
                    
                    except Exception as retrain_err:
                        print(f"❌ 重新训练 {algo_type} 时出错: {str(retrain_err)}")
                        logger.error(f"❌ 重新训练 {algo_type} 时出错: {str(retrain_err)}")
                        import traceback
                        print(traceback.format_exc())
                        logger.error(traceback.format_exc())
    else:
        print("✅ 没有需要重训练的模型")
        logger.info("✅ 没有需要重训练的模型")
    
    # 清理保存的全量数据处理结果，释放内存
    for key in full_data_processed:
        full_data_processed[key] = None
    gc.collect()
    
    # 保存每种算法类型的最佳模型
    for algo_type, model_info in best_models.items():
        if model_info['model'] is not None:
            months = model_info['months']
            months_desc = f"{months}个月" if months else "全部数据"
            
            # 保存模型
            model_path = os.path.join(best_models_dir, f"{algo_type}.joblib")
            joblib.dump(model_info['model'], model_path)
            print(f"{algo_type} 最佳模型 (来自{months_desc}数据) 已保存到 {model_path}")
            logger.info(f"{algo_type} 最佳模型 (来自{months_desc}数据) 已保存到 {model_path}")
            
            # 保存Scaler
            scaler_path = os.path.join(best_models_dir, f"{algo_type}_scaler.joblib")
            joblib.dump(model_info['scaler'], scaler_path)
            print(f"{algo_type} Scaler (来自{months_desc}数据) 已保存到 {scaler_path}")
            logger.info(f"{algo_type} Scaler (来自{months_desc}数据) 已保存到 {scaler_path}")
    
    # 新增: 训练最终生产模型
    print_separator("训练最终生产模型")
    
    # 1. 确定总体最佳模型算法类型
    best_algo_type = None
    best_score = -float('inf')
    
    for algo_type, model_info in best_models.items():
        if model_info['model'] is not None and model_info['score'] > best_score:
            best_score = model_info['score']
            best_algo_type = algo_type
    
    if best_algo_type is None:
        print("❌ 未找到有效的最佳模型，无法训练最终生产模型")
        logger.error("❌ 未找到有效的最佳模型，无法训练最终生产模型")
    else:
        print(f"✅ 总体最佳模型算法类型: {best_algo_type}，评分: {best_score:.4f}")
        logger.info(f"✅ 总体最佳模型算法类型: {best_algo_type}，评分: {best_score:.4f}")
        
        try:
            # 获取最佳模型的关键信息
            best_model_obj = best_models[best_algo_type]['model']
            best_scaler = best_models[best_algo_type]['scaler']
            
            # 获取最佳模型的超参数
            best_params = best_model_obj.get_params()
            
            # 2. 加载和预处理全部历史数据
            print("开始准备全部历史数据用于最终模型训练...")
            logger.info("开始准备全部历史数据用于最终模型训练...")
            
            # 预处理数据（不过滤任何月份，使用全部数据）
            X_full, y_full = preprocess_data(data)
            print(f"全部数据预处理完成，特征维度: {X_full.shape}, 目标变量维度: {y_full.shape}")
            logger.info(f"全部数据预处理完成，特征维度: {X_full.shape}, 目标变量维度: {y_full.shape}")
            
            # 特征工程
            X_full_fe, nan_indices_full = feature_engineering(X_full, lags)
            
            # 删除含有NaN的行
            y_full = y_full.drop(index=nan_indices_full)
            X_full_fe = X_full_fe.drop(index=nan_indices_full)
            
            print(f"特征工程和NaN处理后，数据维度: {X_full_fe.shape}, 目标变量维度: {len(y_full)}")
            logger.info(f"特征工程和NaN处理后，数据维度: {X_full_fe.shape}, 目标变量维度: {len(y_full)}")
            
            # 使用最佳模型的scaler标准化全部数据
            X_full_scaled = best_scaler.transform(X_full_fe)
            
            # 创建时间窗口
            X_full_flat, y_full_windows, _ = create_flattened_windows_with_indices(
                X_full_scaled, y_full, window_size
            )
            
            print(f"窗口创建后，训练数据: {X_full_flat.shape}, 目标: {y_full_windows.shape}")
            logger.info(f"窗口创建后，训练数据: {X_full_flat.shape}, 目标: {y_full_windows.shape}")
            
            # 生成完整的扁平化特征名列表
            original_feature_names = X_full_fe.columns.tolist()
            flat_feature_names_full = generate_flat_feature_names(original_feature_names, window_size)
            
            # 3. 应用Top N特征选择
            top_features_final, selected_indices_final = get_top_features(
                best_algo_type, top_n=3000, current_date=Today
            )
            
            if selected_indices_final is None:
                print("⚠️ 无法获取特征重要性，将使用全部特征训练最终模型")
                logger.warning("⚠️ 无法获取特征重要性，将使用全部特征训练最终模型")
                X_final_train_selected = X_full_flat
                selected_features_final = flat_feature_names_full
            else:
                # 选择特征
                X_final_train_selected = X_full_flat[:, selected_indices_final]
                selected_features_final = ensure_feature_consistency(flat_feature_names_full, selected_indices_final)
                
                print(f"特征选择后，训练数据维度: {X_final_train_selected.shape} (使用 {len(selected_indices_final)} 个特征)")
                logger.info(f"特征选择后，训练数据维度: {X_final_train_selected.shape} (使用 {len(selected_indices_final)} 个特征)")
            
            # 4. 确定最终模型的n_estimators
            final_n_estimators = best_params.get('n_estimators', 100)  # 默认值
            try:
                # 尝试获取早停的最佳迭代次数
                if hasattr(best_model_obj, 'best_iteration_') and best_model_obj.best_iteration_ is not None and best_model_obj.best_iteration_ > 0:
                    final_n_estimators = best_model_obj.best_iteration_
                    print(f"使用早停得到的最佳迭代次数: {final_n_estimators}")
                    logger.info(f"使用早停得到的最佳迭代次数: {final_n_estimators}")
                else:
                    print(f"未使用早停或无最佳迭代次数，使用参数中的n_estimators: {final_n_estimators}")
                    logger.info(f"未使用早停或无最佳迭代次数，使用参数中的n_estimators: {final_n_estimators}")
            except Exception as e:
                print(f"获取最佳迭代次数时出错: {e}，将使用参数中的n_estimators: {final_n_estimators}")
                logger.warning(f"获取最佳迭代次数时出错: {e}，将使用参数中的n_estimators: {final_n_estimators}")
            
            # 更新参数中的n_estimators
            final_params = best_params.copy()
            final_params['n_estimators'] = final_n_estimators
            
            # 移除早停相关参数
            final_params.pop('early_stopping_rounds', None)
            final_params.pop('eval_metric', None)
            
            # 处理callbacks（如果存在）
            if isinstance(final_params.get('callbacks'), list):
                final_params['callbacks'] = None
            
            # 创建并训练最终模型
            print(f"开始训练最终生产模型 ({best_algo_type})，使用所有数据...")
            logger.info(f"开始训练最终生产模型 ({best_algo_type})，使用所有数据...")
            
            model_final = lgb.LGBMRegressor(**final_params)
            model_final.fit(X_final_train_selected, y_full_windows)  # 无早停，使用全部数据
            
            print(f"✅ 最终生产模型训练完成")
            logger.info(f"✅ 最终生产模型训练完成")
            
            # 5. 保存最终生产模型和相关资产
            final_model_path = os.path.join(best_models_dir, 'production_model.joblib')
            final_scaler_path = os.path.join(best_models_dir, 'production_scaler.joblib')
            final_features_path = os.path.join(best_models_dir, 'production_features.pkl')
            final_algo_path = os.path.join(best_models_dir, 'production_algo_type.txt')
            
            # 保存最终模型
            joblib.dump(model_final, final_model_path)
            
            # 保存scaler（使用与最佳模型相同的scaler）
            joblib.dump(best_scaler, final_scaler_path)
            
            # 保存特征信息
            with open(final_features_path, 'wb') as f:
                pickle.dump(
                    {
                        'selected_indices': selected_indices_final,
                        'feature_names': selected_features_final,
                        'algorithm_type': best_algo_type
                    },
                    f
                )
            
            # 保存算法类型到文本文件（方便查看）
            with open(final_algo_path, 'w') as f:
                f.write(best_algo_type)
            
            print(f"✅ 最终生产模型已保存到: {final_model_path}")
            print(f"✅ 最终生产Scaler已保存到: {final_scaler_path}")
            print(f"✅ 最终生产特征信息已保存到: {final_features_path}")
            print(f"✅ 最终生产算法类型已保存到: {final_algo_path}")
            logger.info(f"✅ 最终生产模型已保存到: {final_model_path}")
            logger.info(f"✅ 最终生产Scaler已保存到: {final_scaler_path}")
            logger.info(f"✅ 最终生产特征信息已保存到: {final_features_path}")
            logger.info(f"✅ 最终生产算法类型已保存到: {final_algo_path}")

            # --- 训练分位数模型 ---
            try:
                from models_short import get_quantile_params
                quantile_configs = get_quantile_params()
                best_algo_lower = best_algo_type.lower()

                algo_idx = {'gbdt': 0, 'dart': 1, 'goss': 2}.get(best_algo_lower, 0)

                quantile_model_dir = os.path.join(model_folder_today, 'best_models')
                os.makedirs(quantile_model_dir, exist_ok=True)

                for q_key, q_params_list in quantile_configs.items():
                    q_params = q_params_list[algo_idx]
                    q_params['num_iterations'] = model_final.best_iteration_ if hasattr(model_final, 'best_iteration_') and model_final.best_iteration_ is not None and model_final.best_iteration_ > 0 else q_params.get('num_iterations', 1000)
                    q_params.pop('early_stopping_round', None)

                    q_train_data = lgb.Dataset(X_final_train_selected, label=y_full_windows)
                    q_model = lgb.train(q_params, q_train_data, num_boost_round=q_params['num_iterations'])

                    q_model_path = os.path.join(quantile_model_dir, f'production_model_{q_key}.joblib')
                    joblib.dump(q_model, q_model_path)
                    print(f"  ✅ 分位数模型 {q_key} 已保存: {q_model_path}")
                    logging.info("分位数模型 %s 已保存: %s", q_key, q_model_path)
            except Exception as qe:
                print(f"  ⚠️ 分位数模型训练失败（不影响点预测）: {qe}")
                logging.warning("分位数模型训练失败（不影响点预测）: %s", qe, exc_info=True)
            # --- 分位数训练结束 ---

            # 记录到best_model_type.txt，覆盖原来每种算法类型的记录
            best_model_type_path = os.path.join(model_folder_today, 'best_model_type.txt')
            with open(best_model_type_path, 'w') as f:
                f.write("production_model")  # 指示predict.py使用production_model
            
            print(f"✅ 已更新最佳模型类型标记为production_model: {best_model_type_path}")
            logger.info(f"✅ 已更新最佳模型类型标记为production_model: {best_model_type_path}")
            
        except Exception as e:
            print(f"❌ 训练最终生产模型时出错: {str(e)}")
            logger.error(f"❌ 训练最终生产模型时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    # 修改返回值结构，包装为一个字典，包含'models'和'results'两个键
    return {'models': best_models, 'results': all_results}

def calculate_model_weights(best_models_info, validation_data, lags, window_size):
    """
    根据过去三天的预测结果计算最佳模型权重
    
    参数:
    best_models_info: 包含最佳模型的字典
    validation_data: 用于验证的数据 (过去三天)
    lags: 滞后特征数量
    window_size: 窗口大小
    
    返回:
    模型权重字典 {'GBDT': weight, 'DART': weight, 'GOSS': weight}
    """
    print_separator("计算模型权重")
    from sklearn.linear_model import LinearRegression
    
    # 默认权重
    default_weights = {'GBDT': 0.45, 'DART': 0.1, 'GOSS': 0.45}
    
    # 如果没有足够的验证数据，返回默认权重
    if validation_data is None or len(validation_data) < 24:  # 至少需要一天的数据
        print("❌ 验证数据不足，使用默认权重")
        logger.info("❌ 验证数据不足，使用默认权重")
        return default_weights
    
    try:
        # 获取模型和scaler
        models = {}
        scalers = {}
        # 新增：存储每个模型对应的特征索引
        feature_indices = {}
        
        print("加载最佳模型、scaler和特征信息...")
        logger.info("加载最佳模型、scaler和特征信息...")
        
        # 获取best_models字典，如果best_models_info已经包含'models'键，则直接使用
        best_models = best_models_info.get('models', best_models_info)
        
        for algo_type in ['GBDT', 'DART', 'GOSS']:
            if algo_type in best_models and best_models[algo_type]['model'] is not None:
                models[algo_type] = best_models[algo_type]['model']
                scalers[algo_type] = best_models[algo_type]['scaler']
                print(f"✅ 已加载 {algo_type} 模型和scaler")
                logger.info(f"✅ 已加载 {algo_type} 模型和scaler")
                
                # 新增：加载对应的Top N特征索引
                top_features, selected_indices = get_top_features(algo_type, top_n=3000, current_date=Today)
                if selected_indices is not None:
                    feature_indices[algo_type] = selected_indices
                    print(f"✅ 已加载 {algo_type} 的 TOP {len(selected_indices)} 特征索引")
                    logger.info(f"✅ 已加载 {algo_type} 的 TOP {len(selected_indices)} 特征索引")
                else:
                    # 如果找不到特征文件，可能需要决定是报错、使用默认权重还是使用全部特征
                    print(f"⚠️ 未找到 {algo_type} 的特征索引，将无法使用此模型计算权重")
                    logger.warning(f"⚠️ 未找到 {algo_type} 的特征索引，将无法使用此模型计算权重")
                    # 从 models 字典中移除，避免后续使用
                    models.pop(algo_type, None)
                    scalers.pop(algo_type, None)
            else:
                print(f"❌ 未找到 {algo_type} 模型")
                logger.info(f"❌ 未找到 {algo_type} 模型")
        
        # 如果没有足够的模型，返回默认权重
        if len(models) < 2:
            print("❌ 有效模型（且有特征信息）不足（少于2个），使用默认权重")
            logger.info("❌ 有效模型（且有特征信息）不足（少于2个），使用默认权重")
            return default_weights
        
        # 预处理验证数据
        print(f"预处理验证数据，共 {len(validation_data)} 条记录...")
        logger.info(f"预处理验证数据，共 {len(validation_data)} 条记录...")
        try:
            preprocessed_result = preprocess_data(validation_data)
            # 检查返回值格式
            if isinstance(preprocessed_result, tuple) and len(preprocessed_result) == 2:
                X, y = preprocessed_result
                print(f"验证数据预处理完成，特征维度: {X.shape}")
                logger.info(f"验证数据预处理完成，特征维度: {X.shape}")
            else:
                error_msg = f"preprocess_data返回了预期外的结果，类型: {type(preprocessed_result)}, 长度: {len(preprocessed_result) if hasattr(preprocessed_result, '__len__') else 'N/A'}"
                print(f"❌ {error_msg}")
                logger.error(error_msg)
                return default_weights
        except Exception as e:
            print(f"❌ 预处理验证数据时出错: {str(e)}")
            logger.error(f"❌ 预处理验证数据时出错: {str(e)}")
            return default_weights
        
        try:
            # 执行特征工程
            print(f"对验证数据进行特征工程...")
            logger.info(f"对验证数据进行特征工程...")
            X_fe, nan_indices = feature_engineering(X, lags)
            
            # 处理特征工程引入的NaN（通常是滞后特征导致）
            if len(nan_indices) > 0:
                print(f"特征工程产生了 {len(nan_indices)} 行含NaN的数据，将进行填充")
                logger.info(f"特征工程产生了 {len(nan_indices)} 行含NaN的数据，将进行填充")
                # 对于权重计算，我们选择填充而不是删除行，以保持数据完整性
                X_fe = X_fe.fillna(method='ffill')
                # 如果还有NaN（如起始行），使用后向填充
                if X_fe.isnull().any().any():
                    X_fe = X_fe.fillna(method='bfill')
                # 最后，如果仍有NaN，填充0
                X_fe = X_fe.fillna(0)
            
            print(f"验证数据特征工程完成，特征维度: {X_fe.shape}")
            logger.info(f"验证数据特征工程完成，特征维度: {X_fe.shape}")
        except Exception as e:
            print(f"❌ 特征工程时出错: {str(e)}")
            logger.error(f"❌ 特征工程时出错: {str(e)}")
            return default_weights
        
        # 生成完整的扁平化特征名列表
        original_feature_names = X.columns.tolist()  # 从预处理后的X获取原始特征名
        flat_feature_names = generate_flat_feature_names(original_feature_names, window_size)
        
        # 创建预测结果矩阵
        predictions = {}
        print("使用各模型进行预测...")
        logger.info("使用各模型进行预测...")
        successful_algos = []
        
        for algo_type, model in models.items():
            try:
                # 使用对应的scaler
                X_scaled = scalers[algo_type].transform(X_fe)
                X_windows = create_time_window_pre(X_scaled, window_size)
                X_windows_flat = X_windows.reshape(X_windows.shape[0], -1)  # 扁平化
                
                # 新增：应用特征选择
                selected_indices = feature_indices.get(algo_type)
                if selected_indices is None:
                    print(f"错误：模型 {algo_type} 缺少特征索引信息，跳过此模型权重计算。")
                    logger.error(f"错误：模型 {algo_type} 缺少特征索引信息，跳过此模型权重计算。")
                    continue  # 跳过这个模型
                
                # 检查索引是否有效
                if max(selected_indices) >= X_windows_flat.shape[1]:
                    print(f"错误：模型 {algo_type} 的特征索引 {max(selected_indices)} 超出输入特征维度 {X_windows_flat.shape[1]}，跳过此模型权重计算。")
                    logger.error(f"错误：模型 {algo_type} 的特征索引 {max(selected_indices)} 超出输入特征维度 {X_windows_flat.shape[1]}，跳过此模型权重计算。")
                    continue
                
                # 选择模型训练时使用的特征列
                X_windows_selected = X_windows_flat[:, selected_indices]
                
                print(f"使用 {algo_type} 模型预测 (使用 {X_windows_selected.shape[1]} 个特征)...")
                logger.info(f"使用 {algo_type} 模型预测 (使用 {X_windows_selected.shape[1]} 个特征)...")
                # 使用【选择后的特征】进行预测
                predictions[algo_type] = model.predict(X_windows_selected)
                successful_algos.append(algo_type)
                print(f"✅ {algo_type} 模型预测完成，预测结果数量: {len(predictions[algo_type])}")
                logger.info(f"✅ {algo_type} 模型预测完成，预测结果数量: {len(predictions[algo_type])}")
            
            except Exception as pred_err:
                print(f"❌ 使用 {algo_type} 模型预测时出错: {pred_err}")
                logger.error(f"❌ 使用 {algo_type} 模型预测时出错: {pred_err}")
                # 如果预测失败，跳过这个模型
        
        # 如果所有模型都预测失败了
        if not predictions:
            print("❌ 所有模型预测均失败，无法计算权重，使用默认权重")
            logger.error("❌ 所有模型预测均失败，无法计算权重，使用默认权重")
            return default_weights
        
        # 如果只有部分模型成功，需要调整
        if len(successful_algos) < 2:
            print(f"❌ 成功预测的模型不足（{len(successful_algos)}个），无法计算权重，使用默认权重")
            logger.error(f"❌ 成功预测的模型不足（{len(successful_algos)}个），无法计算权重，使用默认权重")
            return default_weights
        
        # 确保所有预测结果长度一致
        min_length = min(len(pred) for pred in predictions.values())
        y_true = y.values[-min_length:]
        print(f"对齐预测结果，使用最小长度: {min_length}")
        logger.info(f"对齐预测结果，使用最小长度: {min_length}")
        
        if len(y_true) != min_length:
            print(f"⚠️ 实际值长度 ({len(y_true)}) 与最小预测长度 ({min_length}) 不匹配，进行调整...")
            logger.info(f"⚠️ 实际值长度 ({len(y_true)}) 与最小预测长度 ({min_length}) 不匹配，进行调整...")
            if len(y_true) > min_length:
                y_true = y_true[-min_length:]
            else:
                # 如果实际值长度不足，截断预测值
                min_length = len(y_true)
                for algo_type in successful_algos:
                    predictions[algo_type] = predictions[algo_type][-min_length:]
                print(f"预测值已截断至匹配实际值长度: {min_length}")
                logger.info(f"预测值已截断至匹配实际值长度: {min_length}")
        
        # 创建特征矩阵和目标向量（只使用成功预测的模型）
        X_lr = np.column_stack([predictions[algo_type][-min_length:] for algo_type in successful_algos])
        y_lr = y_true
        print(f"创建线性回归的特征矩阵 {X_lr.shape} (基于 {successful_algos}) 和目标向量 {y_lr.shape}")
        logger.info(f"创建线性回归的特征矩阵 {X_lr.shape} (基于 {successful_algos}) 和目标向量 {y_lr.shape}")
        
        # 训练线性回归模型
        print("训练线性回归模型计算最优权重...")
        logger.info("训练线性回归模型计算最优权重...")
        lr = LinearRegression(fit_intercept=True, positive=True)  # 修改为包含偏置项
        lr.fit(X_lr, y_lr)
        
        # 获取权重（只获取成功预测模型的权重）
        calculated_weights = dict(zip(successful_algos, lr.coef_))
        calculated_weights['INTERCEPT'] = lr.intercept_
        print(f"线性回归得到的权重: {calculated_weights}")
        logger.info(f"线性回归得到的权重: {calculated_weights}")
        
        # 合并到最终权重字典，未成功预测的模型权重设为0
        final_weights = {}
        for algo_type in ['GBDT', 'DART', 'GOSS']:
            final_weights[algo_type] = calculated_weights.get(algo_type, 0.0)
            if algo_type not in successful_algos:
                print(f"为未成功预测的 {algo_type} 模型设置权重: 0.0")
                logger.info(f"为未成功预测的 {algo_type} 模型设置权重: 0.0")
        final_weights['INTERCEPT'] = calculated_weights.get('INTERCEPT', 0.0)  # 保留截距（如果计算了）
        
        print(f"最终计算的模型权重: {final_weights}")
        logger.info(f"最终计算的模型权重: {final_weights}")
        return final_weights
        
    except Exception as e:
        print(f"❌ 计算模型权重时发生意外错误: {str(e)}")
        import traceback
        print(traceback.format_exc())  # 打印详细堆栈信息
        print(f"使用默认权重: {default_weights}")
        logger.error(f"❌ 计算模型权重时发生意外错误: {str(e)}\n{traceback.format_exc()}")
        logger.info(f"使用默认权重: {default_weights}")
        return default_weights

def save_predictions(results_dict, y_val, output_base_dir):
    print_separator("保存预测结果")
    # 获取当前时间戳，用于创建子文件夹
    output_dir = os.path.join(output_base_dir, Today)
    
    # 创建目录结构
    os.makedirs(output_dir, exist_ok=True)
    print(f"预测结果将保存到目录: {output_dir}")
    logger.info(f"预测结果将保存到目录: {output_dir}")
    
    for model_name, result in results_dict.items():
        results = pd.DataFrame({
            'Predicted Power': result['y_pred'],
            'Actual Power': y_val
        })
        csv_filename = f'{model_name}_predicted_vs_actual_power.csv'
        csv_filepath = os.path.join(output_dir, csv_filename)
        results.to_csv(csv_filepath, index=False)
        print(f"预测结果已保存到 {csv_filepath}")
        logger.info(f"预测结果已保存到 {csv_filepath}")

# 添加特征选择相关函数
def get_top_features(algo_type, top_n=3000, current_date=None):
    """
    获取TOP N个重要特征
    
    参数:
    algo_type: 算法类型 ('GBDT', 'DART', 'GOSS')
    top_n: 返回的特征数量
    current_date: 当前日期，用于判断特征重要性文件是否需要更新
    
    返回:
    selected_features: 选出的特征名列表
    selected_indices: 选出的特征索引列表
    """
    # 使用固定的特征重要性目录
    importance_file = os.path.join(FEATURE_IMPORTANCE_DIR, f'{algo_type}_feature_importance.pkl')
    
    # 检查特征重要性文件是否存在
    if not os.path.exists(importance_file):
        print(f"⚠️ 未找到{algo_type}的特征重要性文件: {importance_file}")
        logger.warning(f"⚠️ 未找到{algo_type}的特征重要性文件: {importance_file}")
        return None, None

    try:
        # 加载特征重要性文件
        with open(importance_file, 'rb') as f:
            feature_importance_dict = pickle.load(f)
        
        # 检查日期是否需要更新（如果提供了当前日期）
        if current_date is not None and 'date' in feature_importance_dict:
            file_date = feature_importance_dict['date']
            
            # 修改检查逻辑以适应 YYYYMMDD 格式
            if isinstance(file_date, str) and len(file_date) == 8 and file_date.isdigit():
                # 提取月份 (索引4到6)
                file_month = file_date[4:6]
                current_month = current_date[4:6]
                
                if file_month != current_month:
                    print(f"⚠️ {algo_type}的特征重要性文件日期为{file_date}，建议更新")
                    logger.warning(f"⚠️ {algo_type}的特征重要性文件日期为{file_date}，建议更新")
            else:
                print(f"⚠️ {algo_type}特征重要性文件中的日期格式不正确或类型错误: {file_date} (类型: {type(file_date)})，期望YYYYMMDD格式")
                logger.warning(f"⚠️ {algo_type}特征重要性文件中的日期格式不正确或类型错误: {file_date} (类型: {type(file_date)})，期望YYYYMMDD格式")
        
        # 获取特征和重要性
        features = feature_importance_dict['features']
        importances = feature_importance_dict['importances']
        
        # 创建特征重要性DataFrame
        importance_df = pd.DataFrame({
            'feature': features,
            'importance': importances
        }).sort_values(by='importance', ascending=False)
        
        # 选择TOP N个特征
        # 确保不超出特征总数
        top_n = min(top_n, len(importance_df))
        top_features = importance_df.head(top_n)['feature'].tolist()
        
        # 获取特征索引
        all_features = features
        
        # 尝试获取索引，处理可能的找不到特征的情况
        selected_indices = []
        for feature in top_features:
            try:
                idx = all_features.index(feature)
                selected_indices.append(idx)
            except ValueError:
                print(f"⚠️ 特征 '{feature}' 在特征列表中未找到，将被跳过")
                logger.warning(f"⚠️ 特征 '{feature}' 在特征列表中未找到，将被跳过")
                
        if len(selected_indices) == 0:
            print(f"❌ 没有有效的特征被选中，将使用全部特征")
            logger.error(f"❌ 没有有效的特征被选中，将使用全部特征")
            return None, None
        
        print(f"✅ 从{algo_type}的特征重要性文件中选择了TOP {len(selected_indices)}个特征")
        logger.info(f"✅ 从{algo_type}的特征重要性文件中选择了TOP {len(selected_indices)}个特征")
        
        return top_features, selected_indices
        
    except Exception as e:
        print(f"❌ 读取或处理{algo_type}特征重要性文件时出错: {str(e)}")
        logger.error(f"❌ 读取或处理{algo_type}特征重要性文件时出错: {str(e)}")
        return None, None

def apply_feature_selection(X_train, X_val, flat_feature_names, algo_type, top_n=3000, current_date=None):
    """
    应用特征选择
    
    参数:
    X_train: 训练特征矩阵
    X_val: 验证特征矩阵
    flat_feature_names: 扁平化后的特征名列表
    algo_type: 算法类型 ('GBDT', 'DART', 'GOSS')
    top_n: 返回的特征数量
    current_date: 当前日期 (格式为'YYYYMMDD')
    
    返回:
    X_train_selected: 选择特征后的训练矩阵
    X_val_selected: 选择特征后的验证矩阵
    selected_features: 选出的特征名列表
    """
    # 初始化强制更新标志
    force_update = False
    # 使用固定的特征重要性目录
    importance_file = os.path.join(FEATURE_IMPORTANCE_DIR, f'{algo_type}_feature_importance.pkl')
    
    # 检查特征重要性文件是否存在，以及是否需要更新
    if os.path.exists(importance_file):
        try:
            with open(importance_file, 'rb') as f:
                feature_importance_dict = pickle.load(f)
            
            # 检查日期是否需要更新（如果提供了当前日期）
            if current_date is not None and 'date' in feature_importance_dict:
                file_date = feature_importance_dict['date']
                
                # 修改检查逻辑以适应 YYYYMMDD 格式
                if isinstance(file_date, str) and len(file_date) == 8 and file_date.isdigit():
                    # 提取月份 (索引4到6)
                    file_month = file_date[4:6]
                    current_month = current_date[4:6]
                    
                    if file_month != current_month:
                        print(f"⚠️ {algo_type}的特征重要性文件已过期({file_date})，将使用全部特征重新训练并更新")
                        logger.warning(f"⚠️ {algo_type}的特征重要性文件已过期({file_date})，将使用全部特征重新训练并更新")
                        force_update = True
                else:
                    print(f"⚠️ {algo_type}特征重要性文件中的日期格式不正确或类型错误: {file_date} (类型: {type(file_date)})，期望YYYYMMDD格式，将强制更新")
                    logger.warning(f"⚠️ {algo_type}特征重要性文件中的日期格式不正确或类型错误: {file_date} (类型: {type(file_date)})，期望YYYYMMDD格式，将强制更新")
                    force_update = True
                
        except Exception as e:
            print(f"❌ 读取或处理{algo_type}特征重要性文件时出错: {str(e)}，将使用全部特征重新训练")
            logger.error(f"❌ 读取或处理{algo_type}特征重要性文件时出错: {str(e)}，将使用全部特征重新训练")
            force_update = True
    
    # 如果需要强制更新或文件不存在，返回原始特征
    if force_update or not os.path.exists(importance_file):
        print(f"ℹ️ 使用全部特征进行训练 (强制更新或文件不存在)")
        logger.info(f"ℹ️ 使用全部特征进行训练 (强制更新或文件不存在)")
        return X_train, X_val, flat_feature_names
    
    # 获取TOP N个重要特征
    top_features, selected_indices = get_top_features(algo_type, top_n, current_date)
    
    # 如果没有找到特征重要性文件或者读取失败，返回原始特征
    if top_features is None or selected_indices is None:
        print(f"ℹ️ 使用全部特征进行训练")
        logger.info(f"ℹ️ 使用全部特征进行训练")
        return X_train, X_val, flat_feature_names
    
    # 确保特征一致性，获取正确的特征名列表
    selected_features = ensure_feature_consistency(flat_feature_names, selected_indices)
    
    # 选择特征
    X_train_selected = X_train[:, selected_indices]
    X_val_selected = X_val[:, selected_indices]
    
    print(f"✅ 特征选择后：训练集形状 {X_train_selected.shape}，验证集形状 {X_val_selected.shape}")
    logger.info(f"✅ 特征选择后：训练集形状 {X_train_selected.shape}，验证集形状 {X_val_selected.shape}")
    
    # 返回选择后的特征矩阵和特征名列表
    return X_train_selected, X_val_selected, selected_features

def generate_flat_feature_names(original_feature_names, window_size):
    """
    生成扁平化后的特征名列表
    
    注意：这个函数的扁平化逻辑必须与create_flattened_windows_with_indices函数完全一致
    
    在create_flattened_windows_with_indices函数中，扁平化是通过以下步骤实现的：
    1. 对每个样本，提取长度为window_size的窗口
    2. 使用window.reshape(1, -1)将窗口扁平化为一维数组
    3. 这意味着扁平化后，特征的排列顺序是：
       [时间步1的特征1, 时间步1的特征2, ..., 时间步1的特征N, 
        时间步2的特征1, 时间步2的特征2, ..., 时间步2的特征N,
        ...
        时间步W的特征1, 时间步W的特征2, ..., 时间步W的特征N]
    
    因此，本函数生成的特征名也必须遵循相同的顺序。
    
    参数:
    original_feature_names: 原始特征名列表
    window_size: 窗口大小
    
    返回:
    flat_feature_names: 扁平化后的特征名列表
    """
    flat_feature_names = []
    # 按照时间步（外循环）和特征（内循环）的顺序生成特征名
    # 这与create_flattened_windows_with_indices中window.reshape(1, -1)的扁平化顺序一致
    for i in range(window_size):
        time_lag_label = window_size - 1 - i  # 从 window_size-1 到 0
        for name in original_feature_names:
            flat_feature_names.append(f"{name}_t-{time_lag_label}")
    
    return flat_feature_names

def ensure_feature_consistency(flat_feature_names, selected_indices):
    """
    确保特征名和特征索引一致。
    这是为了确保generate_flat_feature_names和create_flattened_windows_with_indices的特征排序逻辑一致。
    
    参数:
    flat_feature_names: 扁平化后的完整特征名列表
    selected_indices: 选择的特征索引
    
    返回:
    selected_features: 选择的特征名列表
    """
    # 检查索引是否超出范围
    if selected_indices is not None:
        if max(selected_indices) >= len(flat_feature_names):
            print(f"⚠️ 特征索引超出范围: 最大索引 {max(selected_indices)}, 特征数量 {len(flat_feature_names)}")
            logger.warning(f"⚠️ 特征索引超出范围: 最大索引 {max(selected_indices)}, 特征数量 {len(flat_feature_names)}")
            return flat_feature_names  # 返回全部特征名
        
        # 根据索引选择特征名
        selected_features = [flat_feature_names[i] for i in selected_indices]
        return selected_features
    
    return flat_feature_names


# ---------------------------------------------------------------------------
# Optimized benchmark replacement
# ---------------------------------------------------------------------------

def train_multiple_datasets(data, months_list, train_ratio, lags, window_size, model_folder_today):
    """Train the optimized short-term ensemble from benchmark_shortterm.py."""
    from optimized_ensemble import fit_shortterm_ensemble
    from utils_base import get_farm_capacity

    farm_code = os.environ.get("FARM_CODE", "DEFAULT_FARM")
    capacity = get_farm_capacity(farm_code)
    logger.info("Training optimized short-term ensemble for farm %s", farm_code)
    result = fit_shortterm_ensemble(data, model_folder_today, capacity=capacity)
    bundle = result["bundle"]

    best_models = {
        "ENSEMBLE": {
            "model": bundle,
            "score": result.get("score", 0.0),
            "months": None,
            "scaler": None,
            "params": {"algorithm": "LGBM-DART + XGBoost-Weighted + CatBoost"},
            "training_samples": result.get("training_samples"),
        }
    }
    return {"models": best_models, "results": {"optimized_shortterm_ensemble": result}}
