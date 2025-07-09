# scripts/model_evaluator.py

import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os
import pathlib

class ModelEvaluator:
    def __init__(self, data_path, output_dir=None, wfcapacity=453.5):
        """
        初始化模型评估器
        
        Parameters:
        -----------
        data_path : str
            模型预测结果CSV文件路径
        output_dir : str, optional
            结果保存目录，如果未提供，将自动创建
        wfcapacity : float, optional
            风电场装机容量，默认为453.5 MW
        """
        # 读取数据
        self.data = pd.read_csv(data_path)
        self.model_name = pathlib.Path(data_path).stem
        
        # 确保时间戳列是datetime类型
        self.data['Timestamp'] = pd.to_datetime(self.data['Timestamp'])
        
        # 添加日期列
        self.data['date'] = self.data['Timestamp'].dt.date
        self.wfcapacity = wfcapacity
        
        # 初始化模型信息
        self.model_info = None
        
        # 创建结果保存目录
        if output_dir:
            self.output_dir = output_dir
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"结果将保存在: {self.output_dir}")
        else:
            self.create_output_dirs()

    def create_output_dirs(self):
        """
        创建输出目录结构
        """
        # 创建基础Fig目录
        base_dir = "Fig"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        
        # 创建时间戳+模型名称的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(base_dir, f"{timestamp}_{self.model_name}")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        print(f"结果将保存在: {self.output_dir}")

    def calculate_metrics(self, actual, predicted):
        """
        计算各项评估指标
        
        Parameters:
        -----------
        actual : array-like
            实际值
        predicted : array-like
            预测值
            
        Returns:
        --------
        dict : 包含各项评估指标的字典
        """
        threshold = 0.2 * self.wfcapacity
        mae = mean_absolute_error(actual, predicted)
        mse = mean_squared_error(actual, predicted)
        rmse = np.sqrt(mse)

        # 添加自定义的Acc指标
        acc = 1 - rmse / self.wfcapacity
        pe = (0.83 - acc) * self.wfcapacity if acc < 0.83 else 0 
    
        # 计算自定义指标 K
        m_values =  ((predicted - actual) / np.maximum(actual, threshold)) ** 2
        k_value = 1 - np.sqrt(np.mean(m_values))
        return {
            'MAE': mae,
            'MSE': mse,
            'RMSE': rmse,
            'ACC': acc,
            'PE': pe,
            'K': k_value
        }
        
    def calculate_overall_metrics(self):
        """
        计算总体评估指标
        
        Returns:
        --------
        dict : 包含评估指标的字典
        """
        return self.calculate_metrics(
            self.data['Actual Power'],
            self.data['Predicted Power'],
        )

    def calculate_daily_metrics(self):
        """
        计算每日评估指标
        
        Returns:
        --------
        pd.DataFrame : 包含每日评估指标的DataFrame
        """
        # 按日期分组
        daily_groups = self.data.groupby('date')
        
        # 创建存储每日指标的列表
        daily_metrics = []
        
        # 阈值定义
        threshold = 0.2 * self.wfcapacity
    
        # 对每一天的数据单独计算指标
        for date, group in daily_groups:
            actual = group['Actual Power'].values
            predicted = group['Predicted Power'].values
    
            # 计算基本指标
            mae = mean_absolute_error(actual, predicted)
            mse = mean_squared_error(actual, predicted)
            rmse = np.sqrt(mse)
            acc = 1 - rmse / self.wfcapacity
            pe = (0.83 - acc) * self.wfcapacity if acc < 0.83 else 0 
    
            # 计算自定义指标 K
            m_values =  ((predicted - actual) / np.maximum(actual, threshold)) ** 2
            k_value = 1 - np.sqrt(np.mean(m_values))
    
            # 添加到每日指标
            daily_metrics.append({
                'date': date,
                'MAE': mae,
                'MSE': mse,
                'RMSE': rmse,
                'ACC': acc,
                'K': k_value,
                'Pe': pe,
                'n_samples': len(group)
            })
    
        return pd.DataFrame(daily_metrics)

    def plot_actual_vs_predicted(self, save_path=None):
        """
        绘制实际值vs预测值的散点图
        """
        plt.figure(figsize=(10, 8))
        
        # 计算相关系数
        correlation = np.corrcoef(self.data['Actual Power'], self.data['Predicted Power'])[0, 1]
        
        # 创建散点图
        plt.scatter(self.data['Actual Power'], self.data['Predicted Power'], 
                   alpha=0.5, c='#3498db', label=f'Correlation: {correlation:.4f}')
        
        # 添加对角线
        min_val = min(self.data['Actual Power'].min(), self.data['Predicted Power'].min())
        max_val = max(self.data['Actual Power'].max(), self.data['Predicted Power'].max())
        plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='Perfect Prediction')
        
        plt.xlabel('Actual Values (MW)')
        plt.ylabel('Predicted Values (MW)')
        plt.title('Actual vs Predicted Values Comparison')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # 添加评估指标文本
        metrics = self.calculate_overall_metrics()
        metrics_text = f"RMSE: {metrics['RMSE']:.2f} MW\n"
        metrics_text += f"MAE: {metrics['MAE']:.2f} MW\n"
        metrics_text += f"ACC: {metrics['ACC']:.4f}"
        
        plt.text(0.05, 0.95, metrics_text,
                transform=plt.gca().transAxes,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            plt.savefig(full_path, bbox_inches='tight', dpi=300)
            print(f"图表已保存: {full_path}")
        plt.close()

    def plot_daily_metrics(self, metric='RMSE', save_path=None):
        """
        绘制每日指标趋势图，包括自定义指标 K。
        
        Parameters:
        -----------
        metric : str
            要绘制的指标名称（例如 'RMSE', 'MAE', 'ACC', 'K'）。
        save_path : str
            保存图表的文件名（可选）。
        """
        daily_metrics = self.calculate_daily_metrics()
    
        plt.figure(figsize=(12, 6))
        
        # 设置不同指标的颜色和单位
        metric_props = {
            'RMSE': {'color': '#e74c3c', 'unit': 'MW'},
            'MAE': {'color': '#3498db', 'unit': 'MW'},
            'ACC': {'color': '#f1c40f', 'unit': ''},
            'K': {'color': '#2ecc71', 'unit': ''}  # 添加 K 指标的颜色
        }
        
        color = metric_props.get(metric, {}).get('color', '#000000')
        unit = metric_props.get(metric, {}).get('unit', '')
        
        # 绘制趋势线
        plt.plot(daily_metrics['date'], daily_metrics[metric], 
                 marker='o', linestyle='-', linewidth=2, markersize=6,
                 color=color)
        
        plt.title(f'Daily {metric} Trend')
        plt.xlabel('Date')
        plt.ylabel(f'{metric} {unit}' if unit else metric)
        plt.grid(True, alpha=0.3)
        
        # 添加平均线
        mean_value = daily_metrics[metric].mean()

        if metric == 'ACC':
            plt.axhline(y=0.83, color='red', linestyle='-.', label='Baseline: 0.83')
        if metric == 'K':
            plt.axhline(y=0.60, color='red', linestyle='-.', label='Baseline: 0.60')
        # 添加统计信息
        stats_text = f"Mean: {mean_value:.4f}\n"
        stats_text += f"Max: {daily_metrics[metric].max():.4f}\n"
        stats_text += f"Min: {daily_metrics[metric].min():.4f}\n"
        stats_text += f"Std: {daily_metrics[metric].std():.4f}"
        
        plt.text(0.05, 0.95, stats_text,
                 transform=plt.gca().transAxes,
                 verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.legend()
        plt.xticks(rotation=45)
        
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            plt.savefig(full_path, bbox_inches='tight', dpi=300)
            print(f"图表已保存: {full_path}")
        plt.close()
    
    def plot_error_distribution(self, save_path=None):
        """
        绘制预测误差分布图
        """
        errors = self.data['Predicted Power'] - self.data['Actual Power']
        
        plt.figure(figsize=(12, 6))
        
        # 创建误差分布直方图
        sns.histplot(errors, bins=50, kde=True, color='#3498db')
        plt.axvline(x=0, color='r', linestyle='--', label='Zero Error')
        
        # 添加误差统计信息
        mean_error = errors.mean()
        std_error = errors.std()
        plt.axvline(x=mean_error, color='g', linestyle='--', 
                   label=f'Mean Error: {mean_error:.2f} MW')
        
        # 添加更多统计信息
        stats_text = f"Mean Error: {mean_error:.2f} MW\n"
        stats_text += f"Std Error: {std_error:.2f} MW\n"
        stats_text += f"Max Error: {errors.max():.2f} MW\n"
        stats_text += f"Min Error: {errors.min():.2f} MW"
        
        plt.text(0.95, 0.95, stats_text,
                transform=plt.gca().transAxes,
                verticalalignment='top',
                horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.title('Prediction Error Distribution')
        plt.xlabel('Prediction Error (MW)')
        plt.ylabel('Frequency')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            plt.savefig(full_path, bbox_inches='tight', dpi=300)
            print(f"图表已保存: {full_path}")
        plt.close()

    def generate_report(self, report_name='model_evaluation_report.txt'):
        """
        生成详细的评估报告，包括模型参数、误差分析和改进建议
        """
        report_path = os.path.join(self.output_dir, report_name)
        overall_metrics = self.calculate_overall_metrics()
        daily_metrics = self.calculate_daily_metrics()
        
        # 计算误差分析
        errors = self.data['Actual Power'] - self.data['Predicted Power']
        error_mean = errors.mean()
        error_std = errors.std()
        error_percentiles = np.percentile(errors, [5, 25, 50, 75, 95])
        
        # 计算相对误差
        relative_errors = np.abs(errors) / (self.data['Actual Power'] + 1e-10) * 100
        relative_error_mean = relative_errors.mean()
        
        with open(report_path, 'w', encoding='utf-8') as f:
            # 报告标题
            f.write(f"{'='*80}\n")
            f.write(f"{' '*30}风电功率预测详细评估报告\n")
            f.write(f"{'='*80}\n\n")
            
            # 生成时间和基本信息
            f.write(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"模型名称: {self.model_name}\n")
            f.write(f"风电场装机容量: {self.wfcapacity} MW\n\n")
            
            # 模型信息部分
            if self.model_info:
                f.write(f"{'='*80}\n")
                f.write("模型训练信息\n")
                f.write(f"{'='*80}\n\n")
                
                f.write(f"模型类型: {self.model_info.get('model_type', '未知')}\n")
                f.write(f"训练集占比: {self.model_info.get('train_ratio', 0.9)}\n")
                
                # 如果有自定义参数，添加到报告中
                custom_params = self.model_info.get('custom_params')
                if custom_params:
                    f.write("\n模型超参数:\n")
                    for param_name, param_value in custom_params.items():
                        f.write(f"  - {param_name}: {param_value}\n")
                f.write("\n")
            
            # 数据基本信息
            f.write(f"{'='*80}\n")
            f.write("数据基本信息\n")
            f.write(f"{'='*80}\n\n")
            f.write(f"总样本数: {len(self.data)}\n")
            f.write(f"时间范围: {self.data['Timestamp'].min()} 到 {self.data['Timestamp'].max()}\n")
            f.write(f"实际值范围: {self.data['Actual Power'].min():.2f} 到 {self.data['Actual Power'].max():.2f} MW\n")
            f.write(f"预测值范围: {self.data['Predicted Power'].min():.2f} 到 {self.data['Predicted Power'].max():.2f} MW\n")
            f.write(f"平均实际功率: {self.data['Actual Power'].mean():.2f} MW\n")
            f.write(f"平均预测功率: {self.data['Predicted Power'].mean():.2f} MW\n\n")
            
            # 总体评估指标
            f.write(f"{'='*80}\n")
            f.write("总体评估指标\n")
            f.write(f"{'='*80}\n\n")
            
            f.write(f"均方误差 (MSE): {overall_metrics['MSE']:.6f}\n")
            f.write(f"均方根误差 (RMSE): {overall_metrics['RMSE']:.6f} MW\n")
            f.write(f"平均绝对误差 (MAE): {overall_metrics['MAE']:.6f} MW\n")
            f.write(f"预测精度 (ACC): {overall_metrics['ACC']:.6f}\n")
            f.write(f"相关系数 (K): {overall_metrics['K']:.6f}\n")
            f.write(f"日均考核电量 (PE): {overall_metrics['PE']:.6f} MWh\n")
            f.write(f"平均相对误差: {relative_error_mean:.2f}%\n\n")
            
            # 误差分析
            f.write(f"{'='*80}\n")
            f.write("误差分析\n")
            f.write(f"{'='*80}\n\n")
            
            f.write(f"误差均值: {error_mean:.6f} MW\n")
            f.write(f"误差标准差: {error_std:.6f} MW\n")
            f.write("\n误差分布百分位数:\n")
            f.write(f"  - 5%分位数: {error_percentiles[0]:.6f} MW\n")
            f.write(f"  - 25%分位数: {error_percentiles[1]:.6f} MW\n")
            f.write(f"  - 50%分位数 (中位数): {error_percentiles[2]:.6f} MW\n")
            f.write(f"  - 75%分位数: {error_percentiles[3]:.6f} MW\n")
            f.write(f"  - 95%分位数: {error_percentiles[4]:.6f} MW\n\n")
            
            # 每日评估指标统计
            f.write(f"{'='*80}\n")
            f.write("每日评估指标统计\n")
            f.write(f"{'='*80}\n\n")
            
            for metric in ['RMSE', 'MAE', 'ACC', 'K', 'Pe']:
                metric_name = metric
                if metric == 'Pe':
                    metric_name = 'PE'
                
                f.write(f"\n{metric_name}统计：\n")
                f.write(f"平均值: {daily_metrics[metric].mean():.4f}\n")
                f.write(f"最大值: {daily_metrics[metric].max():.4f} (日期: {daily_metrics.loc[daily_metrics[metric].idxmax(), 'date']})\n")
                f.write(f"最小值: {daily_metrics[metric].min():.4f} (日期: {daily_metrics.loc[daily_metrics[metric].idxmin(), 'date']})\n")
                f.write(f"标准差: {daily_metrics[metric].std():.4f}\n")
            
            # 性能评估
            f.write(f"\n{'='*80}\n")
            f.write("预测性能评估\n")
            f.write(f"{'='*80}\n\n")
            
            # 根据ACC和K评估模型性能
            acc = overall_metrics['ACC']
            k = overall_metrics['K']
            
            if acc > 0.9 and k > 0.7:
                performance = "优秀"
            elif acc > 0.85 and k > 0.65:
                performance = "良好"
            elif acc > 0.83 and k > 0.6:
                performance = "达标"
            else:
                performance = "需要改进"
            
            f.write(f"模型整体性能评价: {performance}\n\n")
            
            # 提供改进建议
            f.write("改进建议:\n")
            if performance == "需要改进":
                f.write("  - 考虑增加训练数据量，特别是不同天气条件下的数据\n")
                f.write("  - 尝试更复杂的模型架构或集成多个模型\n")
                f.write("  - 进行更全面的特征工程，考虑添加更多气象特征\n")
                f.write("  - 调整模型超参数，尤其是学习率和树的深度\n")
                f.write("  - 分析预测误差较大的时间段，找出可能的系统性问题\n")
            elif performance == "达标":
                f.write("  - 尝试调整学习率和正则化参数以提高精度\n")
                f.write("  - 考虑添加更多相关特征，如风向变化特征\n")
                f.write("  - 对误差较大的时间段进行单独分析\n")
                f.write("  - 考虑使用时间序列特定的模型如LSTM或GRU\n")
            else:
                f.write("  - 当前模型表现良好，可以考虑部署到生产环境\n")
                f.write("  - 定期使用新数据重新训练模型以保持性能\n")
                f.write("  - 考虑建立模型监控系统，及时发现性能下降\n")
                f.write("  - 可以尝试进一步优化以提高极端天气条件下的预测准确性\n")
            
            # 结束语
            f.write(f"\n{'='*80}\n")
            f.write("报告结束\n")
            f.write(f"{'='*80}\n")
        
        print(f"详细评估报告已保存: {report_path}")
        return report_path

    def save_daily_metrics_to_csv(self, filename='daily_metrics.csv'):
        """
        保存每日指标到CSV文件
        """
        daily_metrics = self.calculate_daily_metrics()
        output_path = os.path.join(self.output_dir, filename)
        daily_metrics.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"每日指标数据已保存到: {output_path}")

def evaluate_model(
    data_path,
    save_plots=True,
    save_csv=True,
    save_report=True,
    custom_save_dir=None,
    wfcapacity=453.5,
    model_info=None,
):
    """
    评估模型并生成相关报告和图表。
    
    Parameters:
    -----------
    data_path : str
        模型预测结果CSV文件路径
    save_plots : bool, optional
        是否保存生成的图表，默认为True
    save_csv : bool, optional
        是否保存每日指标到CSV文件，默认为True
    save_report : bool, optional
        是否生成评估报告，默认为True
    custom_save_dir : str, optional
        自定义的结果保存目录，如果不提供则使用默认目录结构
    wfcapacity : float, optional
        风电场装机容量，默认为453.5 MW
    model_info : dict, optional
        模型相关信息，包括模型类型、训练参数等
    """
    evaluator = ModelEvaluator(data_path, output_dir=custom_save_dir, wfcapacity=wfcapacity)

    
    # 设置模型信息
    if model_info:
        evaluator.model_info = model_info
    
    # 绘制并保存实际值 vs 预测值图
    if save_plots:
        evaluator.plot_actual_vs_predicted(save_path='actual_vs_predicted.png')
        evaluator.plot_error_distribution(save_path='error_distribution.png')
        for metric in ['RMSE', 'MAE', 'ACC', 'K']:
            evaluator.plot_daily_metrics(metric=metric, save_path=f'daily_{metric.lower()}.png')
    
    # 保存每日指标到CSV
    if save_csv:
        evaluator.save_daily_metrics_to_csv(filename='daily_metrics.csv')
    
    # 生成评估报告
    if save_report:
        evaluator.generate_report()
    
    # 打印总体评估指标
    overall_metrics = evaluator.calculate_overall_metrics()
    print("\n总体评估指标:")
    for metric, value in overall_metrics.items():
        print(f"{metric}: {value:.4f}")
    
    return {
        'overall_metrics': overall_metrics,
        'output_dir': evaluator.output_dir
    }
