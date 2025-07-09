import numpy as np
import lightgbm as lgb
from lightgbm import LGBMRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import make_scorer, mean_squared_error
from utils_middle import evaluate_with_time_weights, calculate_rmse, calculate_k
import time
import logging

# 配置日志
logger = logging.getLogger()

def custom_scorer(y_true, y_pred, timestamps=None):
    """
    自定义评分函数，使用时间加权评分
    
    参数:
    y_true: 实际值
    y_pred: 预测值
    timestamps: 时间戳，如果提供则使用时间加权评分，否则使用简单的RMSE和K值的综合评分
    
    返回:
    分数 - 分数越高越好
    """
    if timestamps is not None and len(timestamps) == len(y_true):
        try:
            # 使用时间加权评分
            score, _, _ = evaluate_with_time_weights(y_true, y_pred, timestamps)
            return score
        except Exception as e:
            print(f"时间加权评分失败: {str(e)}，使用简单的RMSE和K值综合评分")
            # 如果时间加权评分失败，回退到简单的RMSE和K值综合评分
            rmse = calculate_rmse(y_true, y_pred)
            k = calculate_k(y_true, y_pred)
            
            # 归一化RMSE (使其在0到1之间，越小越好)
            # 这里假设RMSE最大不超过装机容量
            norm_rmse = min(1.0, rmse / 453.5)
            norm_weighted_rmse = 1 - norm_rmse  # 转换为越大越好
            
            # 综合评分 (加权平均)
            rmse_weight = 0.5
            k_weight = 0.5
            score = norm_weighted_rmse * rmse_weight + k * k_weight
            
            return score
    else:
        # 使用简单的RMSE和K值综合评分
        rmse = calculate_rmse(y_true, y_pred)
        k = calculate_k(y_true, y_pred)
        
        # 归一化RMSE (使其在0到1之间，越小越好)
        norm_rmse = min(1.0, rmse / 453.5)
        norm_weighted_rmse = 1 - norm_rmse  # 转换为越大越好
        
        # 综合评分 (加权平均)
        rmse_weight = 0.5
        k_weight = 0.5
        score = norm_weighted_rmse * rmse_weight + k * k_weight
        
        return score

def find_best_params(X, y, K=5, n_iter=10, random_state=42, timestamps=None, boosting_type=None):
    """
    优化 LightGBM 参数，使用简单的训练/验证集分割而不是交叉验证
    
    参数:
    X: 特征矩阵
    y: 目标变量
    K: 不使用
    n_iter: 随机搜索迭代次数
    random_state: 随机种子
    timestamps: 时间戳数组，用于时间加权评分
    boosting_type: 指定优化的boosting类型，可以是'gbdt'、'dart'、'goss'或None(优化所有类型)
    
    返回:
    最佳参数字典
    """
    # 将数据转换为float32，减少内存占用
    X = np.float32(X)
    y = np.float32(y)
    
    # 分割数据集为训练集和验证集 (90%:10%)，对时间序列数据保持时间顺序
    # 使用最后10%的数据作为验证集
    split_idx = int(len(X) * 0.9)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    # 如果有时间戳，相应地分割时间戳
    val_timestamps = None
    if timestamps is not None:
        if len(timestamps) == len(y):
            # 同样保持时间顺序分割时间戳
            val_timestamps = timestamps[split_idx:]
        else:
            logger.warning(f"时间戳长度({len(timestamps)})与目标变量长度({len(y)})不匹配，不使用时间戳进行评分")
    
    # 准备GPU参数
    gpu_params = {
        'device': 'gpu',
        'gpu_platform_id': 0,
        'gpu_device_id': 0,
        'gpu_use_dp': False
    }
    
    # 准备基本参数
    base_params = {
        'objective': 'regression',
        'metric': 'rmse',
        'random_state': random_state,
        'verbose': -1
    }
    
    # 构建参数搜索空间
    param_spaces = []
    
    # 根据boosting_type构建参数搜索空间
    if boosting_type == 'gbdt' or boosting_type is None:
        gbdt_params = base_params.copy()
        gbdt_params['boosting_type'] = 'gbdt'
        gbdt_params['name'] = 'GBDT'
        gbdt_params.update(gpu_params)
        param_spaces.append((gbdt_params, {
            'num_leaves': np.arange(20, 100, 10),
            'learning_rate': [0.01, 0.05, 0.1, 0.2],
            'feature_fraction': [0.6, 0.7, 0.8, 0.9],
            'max_depth': np.arange(3, 10),
            'n_estimators': np.arange(50, 200, 20)
        }))
    
    if boosting_type == 'dart' or boosting_type is None:
        dart_params = base_params.copy()
        dart_params['boosting_type'] = 'dart'
        dart_params['name'] = 'DART'
        dart_params.update(gpu_params)
        param_spaces.append((dart_params, {
            'num_leaves': np.arange(20, 100, 10),
            'learning_rate': [0.01, 0.05, 0.1, 0.2],
            'feature_fraction': [0.6, 0.7, 0.8, 0.9],
            'max_depth': np.arange(3, 10),
            'n_estimators': np.arange(50, 200, 20),
            'drop_rate': [0.1, 0.2, 0.3, 0.4],
            'skip_drop': [0.3, 0.5, 0.7]
        }))
    
    if boosting_type == 'goss' or boosting_type is None:
        goss_params = base_params.copy()
        goss_params['boosting_type'] = 'goss'
        goss_params['name'] = 'GOSS'
        goss_params.update(gpu_params)
        param_spaces.append((goss_params, {
            'num_leaves': np.arange(20, 100, 10),
            'learning_rate': [0.01, 0.05, 0.1, 0.2],
            'feature_fraction': [0.6, 0.7, 0.8, 0.9],
            'max_depth': np.arange(3, 10),
            'n_estimators': np.arange(50, 200, 20),
            'top_rate': [0.1, 0.2, 0.3],
            'other_rate': [0.1, 0.2, 0.3]
        }))
    
    # 如果指定了具体的boosting_type，只保留相应的参数空间
    if boosting_type is not None:
        param_spaces = [ps for ps in param_spaces if ps[0]['boosting_type'] == boosting_type]
    
    best_score = float('-inf')
    best_params = None
    best_model = None
    
    # 对每种boosting类型进行参数优化
    for base_params, param_space in param_spaces:
        boosting_type_name = base_params['name']
        logger.info(f"开始为 {boosting_type_name} 进行随机参数搜索 ({n_iter} 次迭代)")
        
        # 保存当前boosting类型的最佳分数和参数
        current_best_score = float('-inf')
        current_best_params = None
        current_best_model = None
        
        # 进行n_iter次随机搜索
        for i in range(n_iter):
            # 随机采样参数
            params = base_params.copy()
            for param_name, param_values in param_space.items():
                params[param_name] = np.random.choice(param_values)
            
            try:
                # 创建并训练模型
                start_time = time.time()
                model = lgb.LGBMRegressor(**params)
                
                # 使用训练集和验证集进行训练，DART模式不支持早停
                if params.get('boosting_type') == 'dart':
                    model.fit(
                        X_train, y_train,
                        eval_set=[(X_val, y_val)],
                        eval_metric='rmse'
                    )
                else:
                    # 非DART模式使用早停
                    model.fit(
                        X_train, y_train,
                        eval_set=[(X_val, y_val)],
                        eval_metric='rmse',
                        callbacks=[lgb.early_stopping(10)]
                    )
                
                # 在验证集上预测
                y_pred = model.predict(X_val)
                
                # 计算分数
                if val_timestamps is not None and len(val_timestamps) == len(y_val):
                    try:
                        score, rmse, k = evaluate_with_time_weights(y_val, y_pred, val_timestamps)
                    except Exception as e:
                        logger.warning(f"时间加权评分失败: {str(e)}，使用简单评分")
                        # 使用简单评分
                        rmse = calculate_rmse(y_val, y_pred)
                        k = calculate_k(y_val, y_pred)
                        
                        # 计算综合分数
                        norm_rmse = min(1.0, rmse / 453.5)
                        norm_weighted_rmse = 1 - norm_rmse
                        score = norm_weighted_rmse * 0.5 + k * 0.5
                else:
                    # 使用简单评分
                    rmse = calculate_rmse(y_val, y_pred)
                    k = calculate_k(y_val, y_pred)
                    
                    # 计算综合分数
                    norm_rmse = min(1.0, rmse / 453.5)
                    norm_weighted_rmse = 1 - norm_rmse
                    score = norm_weighted_rmse * 0.5 + k * 0.5
                
                # 记录时间和结果
                elapsed_time = time.time() - start_time
                logger.info(f"[{boosting_type_name}] 迭代 {i+1}/{n_iter}: score={score:.4f}, rmse={rmse:.4f}, k={k:.4f}, 用时={elapsed_time:.2f}秒")
                
                # 更新当前最佳结果
                if score > current_best_score:
                    current_best_score = score
                    current_best_params = params.copy()
                    current_best_model = model
                    logger.info(f"[{boosting_type_name}] 新的最佳分数: {score:.4f}, 参数: {current_best_params}")
                
            except Exception as e:
                logger.error(f"[{boosting_type_name}] 迭代 {i+1}/{n_iter} 失败: {str(e)}")
        
        # 更新全局最佳结果
        if current_best_score > best_score:
            best_score = current_best_score
            best_params = current_best_params
            best_model = current_best_model
            logger.info(f"发现更好的模型类型: {boosting_type_name}, 分数: {best_score:.4f}")
    
    # 如果没有找到有效的参数，返回默认参数
    if best_params is None:
        logger.warning("未找到有效参数，返回默认参数")
        best_params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'name': 'GBDT',
            'num_leaves': 31,
            'learning_rate': 0.1,
            'feature_fraction': 0.9,
            'max_depth': 6,
            'n_estimators': 100,
            'random_state': random_state,
            'verbose': -1
        }
    
    return best_params
