# train.py
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np
import lightgbm as lgb
import pandas as pd
import os
from datetime import datetime
import joblib  # 用于保存模型和 scaler
from flask import current_app
import json

def train_and_evaluate(X_train, y_train, X_val, y_val, params, scaler, models_dir='models'):
    """
    训练并评估每种模型，并将模型和 scaler 保存到本地路径
    """
    results_dict = {}
    
    # 获取当前时间戳，用于创建子文件夹
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_path = os.path.join(models_dir, current_time)
    
    # 创建目录结构
    os.makedirs(save_path, exist_ok=True)
    current_app.logger.info(f"模型和 scaler 将被保存到目录: {save_path}")
    
    # 确保params包含必要的参数
    model_params = params.copy()
    
    # 确保有objective和metric参数
    if 'objective' not in model_params:
        model_params['objective'] = 'regression'
    if 'metric' not in model_params:
        model_params['metric'] = 'rmse'
    
    # 移除name参数，因为LGBMRegressor不接受这个参数
    model_name = model_params.pop('name', 'Unknown')
    
    current_app.logger.info(f"开始训练 {model_name} 模型...")
    current_app.logger.info(f"使用参数: {model_params}")
    
    # 记录训练开始时间
    train_start_time = datetime.now()
    
    # 训练模型
    model = lgb.LGBMRegressor(**model_params)
    model.fit(X_train.reshape(X_train.shape[0], -1), y_train)
    
    # 记录训练结束时间和训练时长
    train_end_time = datetime.now()
    train_duration = (train_end_time - train_start_time).total_seconds()
    
    # 预测和评估
    y_pred = model.predict(X_val.reshape(X_val.shape[0], -1))
    
    # 计算多种评估指标
    mse = mean_squared_error(y_val, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_val, y_pred)
    r2 = r2_score(y_val, y_pred)
    
    # 计算相对误差指标
    mape = np.mean(np.abs((y_val - y_pred) / (y_val + 1e-10))) * 100  # 平均绝对百分比误差
    
    # 计算预测精度
    acc = 1 - np.sum(np.abs(y_val - y_pred)) / np.sum(y_val) if np.sum(y_val) > 0 else 0
    
    # 计算K值 (预测值与实际值的相关系数)
    k = np.corrcoef(y_val, y_pred)[0, 1] if len(y_val) > 1 else 0
    
    # 计算误差分布
    errors = y_val - y_pred
    error_mean = np.mean(errors)
    error_std = np.std(errors)
    error_percentiles = np.percentile(errors, [5, 25, 50, 75, 95])
    
    # 特征重要性
    feature_importance = None
    if hasattr(model, 'feature_importances_'):
        feature_importance = model.feature_importances_
    
    # 保存详细的评估结果
    evaluation_results = {
        'model_name': model_name,
        'model_params': model_params,
        'training_info': {
            'train_samples': X_train.shape[0],
            'validation_samples': X_val.shape[0],
            'train_start_time': train_start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'train_end_time': train_end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'train_duration_seconds': train_duration
        },
        'metrics': {
            'mse': mse,
            'rmse': rmse,
            'mae': mae,
            'r2': r2,
            'mape': mape,
            'acc': acc,
            'k': k
        },
        'error_analysis': {
            'error_mean': error_mean,
            'error_std': error_std,
            'error_percentiles': {
                'p5': error_percentiles[0],
                'p25': error_percentiles[1],
                'p50': error_percentiles[2],
                'p75': error_percentiles[3],
                'p95': error_percentiles[4]
            }
        }
    }
    
    # 如果有特征重要性，添加到评估结果中
    if feature_importance is not None:
        evaluation_results['feature_importance'] = feature_importance.tolist()
    
    # 保存评估结果到JSON文件
    evaluation_file = os.path.join(save_path, f"{model_name}_evaluation.json")
    with open(evaluation_file, 'w') as f:
        json.dump(evaluation_results, f, indent=2)
    
    current_app.logger.info(f"评估结果已保存到 {evaluation_file}")
    
    results_dict[model_name] = {
        'model': model,
        'y_pred': y_pred,
        'mse': mse,
        'rmse': rmse,
        'mae': mae,
        'r2': r2,
        'mape': mape,
        'acc': acc,
        'k': k,
        'evaluation_results': evaluation_results
    }
    
    current_app.logger.info(f"{model_name} 均方误差: {mse}")
    current_app.logger.info(f"{model_name} 均方根误差: {rmse}")
    current_app.logger.info(f"{model_name} 平均绝对误差: {mae}")
    current_app.logger.info(f"{model_name} R²分数: {r2}")
    current_app.logger.info(f"{model_name} 预测精度: {acc}")
    current_app.logger.info(f"{model_name} K值: {k}")
    
    # 保存模型
    model_filename = f"{model_name}.joblib"
    model_filepath = os.path.join(save_path, model_filename)
    joblib.dump(model, model_filepath)
    current_app.logger.info(f"{model_name} 模型已保存到 {model_filepath}")
    
    # 保存 scaler
    scaler_filename = 'scaler.joblib'
    scaler_filepath = os.path.join(save_path, scaler_filename)
    joblib.dump(scaler, scaler_filepath)
    current_app.logger.info(f"Scaler 已保存到 {scaler_filepath}")
    
    return results_dict, model_filepath, scaler_filepath


def save_predictions(results_dict, y_val, output_base_dir='results/'):
    """
    保存预测结果到以时间戳命名的子文件夹中的CSV文件
    """
    
    # 创建目录结构
    os.makedirs(output_base_dir, exist_ok=True)
    for model_name, result in results_dict.items():
        results = pd.DataFrame({
            'Predicted Power': result['y_pred'],
            'Actual Power': y_val,
            'Error': y_val - result['y_pred'],
            'Absolute Error': np.abs(y_val - result['y_pred']),
            'Relative Error (%)': np.abs((y_val - result['y_pred']) / (y_val + 1e-10)) * 100
        })
        csv_filename = f'{model_name}_predicted_vs_actual_power.csv'
        csv_filepath = os.path.join(output_base_dir, csv_filename)
        results.to_csv(csv_filepath, index=False)
        current_app.logger.info(f"原生预测结果已保存到 {csv_filepath}")
        
        # 生成详细的预测报告
        generate_detailed_report(result, y_val, output_base_dir, model_name)
        
    return csv_filepath


def generate_detailed_report(result, y_val, output_dir, model_name):
    """
    生成详细的预测报告，包括模型参数、评估指标和误差分析
    """
    report_filename = f'{model_name}_detailed_report.txt'
    report_filepath = os.path.join(output_dir, report_filename)
    
    with open(report_filepath, 'w', encoding='utf-8') as f:
        # 报告标题
        f.write(f"{'='*80}\n")
        f.write(f"{' '*30}风电功率预测详细报告\n")
        f.write(f"{'='*80}\n\n")
        
        # 生成时间
        f.write(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 模型信息
        f.write(f"{'='*80}\n")
        f.write("模型信息\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"模型名称: {model_name}\n")
        
        # 模型参数
        f.write("\n模型参数:\n")
        for param_name, param_value in result['evaluation_results']['model_params'].items():
            f.write(f"  - {param_name}: {param_value}\n")
        
        # 训练信息
        f.write("\n训练信息:\n")
        training_info = result['evaluation_results']['training_info']
        f.write(f"  - 训练样本数: {training_info['train_samples']}\n")
        f.write(f"  - 验证样本数: {training_info['validation_samples']}\n")
        f.write(f"  - 训练开始时间: {training_info['train_start_time']}\n")
        f.write(f"  - 训练结束时间: {training_info['train_end_time']}\n")
        f.write(f"  - 训练时长: {training_info['train_duration_seconds']:.2f} 秒\n")
        
        # 评估指标
        f.write(f"\n{'='*80}\n")
        f.write("评估指标\n")
        f.write(f"{'='*80}\n\n")
        
        metrics = result['evaluation_results']['metrics']
        f.write(f"均方误差 (MSE): {metrics['mse']:.6f}\n")
        f.write(f"均方根误差 (RMSE): {metrics['rmse']:.6f}\n")
        f.write(f"平均绝对误差 (MAE): {metrics['mae']:.6f}\n")
        f.write(f"决定系数 (R²): {metrics['r2']:.6f}\n")
        f.write(f"平均绝对百分比误差 (MAPE): {metrics['mape']:.2f}%\n")
        f.write(f"预测精度 (ACC): {metrics['acc']:.6f}\n")
        f.write(f"相关系数 (K): {metrics['k']:.6f}\n")
        
        # 误差分析
        f.write(f"\n{'='*80}\n")
        f.write("误差分析\n")
        f.write(f"{'='*80}\n\n")
        
        error_analysis = result['evaluation_results']['error_analysis']
        f.write(f"误差均值: {error_analysis['error_mean']:.6f}\n")
        f.write(f"误差标准差: {error_analysis['error_std']:.6f}\n")
        f.write("\n误差分布百分位数:\n")
        percentiles = error_analysis['error_percentiles']
        f.write(f"  - 5%分位数: {percentiles['p5']:.6f}\n")
        f.write(f"  - 25%分位数: {percentiles['p25']:.6f}\n")
        f.write(f"  - 50%分位数 (中位数): {percentiles['p50']:.6f}\n")
        f.write(f"  - 75%分位数: {percentiles['p75']:.6f}\n")
        f.write(f"  - 95%分位数: {percentiles['p95']:.6f}\n")
        
        # 特征重要性
        if 'feature_importance' in result['evaluation_results']:
            f.write(f"\n{'='*80}\n")
            f.write("特征重要性\n")
            f.write(f"{'='*80}\n\n")
            
            feature_importance = result['evaluation_results']['feature_importance']
            f.write("特征重要性分数:\n")
            for i, importance in enumerate(feature_importance):
                f.write(f"  - 特征 {i+1}: {importance:.6f}\n")
        
        # 预测性能总结
        f.write(f"\n{'='*80}\n")
        f.write("预测性能总结\n")
        f.write(f"{'='*80}\n\n")
        
        # 根据R²和ACC评估模型性能
        r2 = metrics['r2']
        acc = metrics['acc']
        
        if r2 > 0.9 and acc > 0.9:
            performance = "优秀"
        elif r2 > 0.8 and acc > 0.8:
            performance = "良好"
        elif r2 > 0.7 and acc > 0.7:
            performance = "一般"
        else:
            performance = "需要改进"
        
        f.write(f"模型整体性能评价: {performance}\n\n")
        
        # 提供改进建议
        f.write("改进建议:\n")
        if performance == "需要改进":
            f.write("  - 考虑增加训练数据量\n")
            f.write("  - 尝试更复杂的模型架构\n")
            f.write("  - 进行更全面的特征工程\n")
            f.write("  - 调整模型超参数\n")
        elif performance == "一般":
            f.write("  - 尝试调整学习率和正则化参数\n")
            f.write("  - 考虑添加更多相关特征\n")
            f.write("  - 尝试不同的模型类型\n")
        else:
            f.write("  - 当前模型表现良好，可以考虑部署到生产环境\n")
            f.write("  - 定期使用新数据重新训练模型以保持性能\n")
        
        # 结束语
        f.write(f"\n{'='*80}\n")
        f.write("报告结束\n")
        f.write(f"{'='*80}\n")
    
    current_app.logger.info(f"详细预测报告已保存到 {report_filepath}")
    return report_filepath


