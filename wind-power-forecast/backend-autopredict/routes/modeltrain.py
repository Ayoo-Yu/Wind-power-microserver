import os
import pandas as pd
from flask import Blueprint, request, jsonify, current_app, send_file
import glob
import datetime
import shutil
from services.file_service import find_file_by_id
from services.modeltrain_service import run_modeltrain
from services.evaluation_service import run_evaluation
from werkzeug.utils import secure_filename
from database_config import minio_client, SessionLocal
from models import Model, EvaluationMetrics, TrainingRecord
import uuid
# 预测蓝图
modeltrain_bp = Blueprint('modeltrain', __name__)

# 增加训练状态存储
training_status = {}

@modeltrain_bp.route('/modeltrain', methods=['POST'])
def train_model():
    """
    模型训练入口
    """
    data = request.get_json()
    current_app.logger.info(f"收到模型训练请求: {data}")
    if not data or 'file_id' not in data or 'model' not in data or 'wfcapacity' not in data:
        current_app.logger.warning("缺少训练数据集或模型参数")
        return jsonify({'error': "缺少 'file_id' 或 'model' 参数"}), 400

    file_id = data['file_id']
    model = data['model']
    wfcapacity = pd.to_numeric(data['wfcapacity'])
    train_ratio = 0.9
    if 'train_ratio' in data:
        train_ratio = pd.to_numeric(data['train_ratio'])
        if train_ratio < 0.1 or train_ratio > 0.95:
            current_app.logger.warning(f"训练集占比超出有效范围: {train_ratio}")
            return jsonify({'error': "训练集占比必须在0.1到0.95之间"}), 400
    
    custom_params = None
    if model == 'CUSTOM' and 'custom_params' in data:
        custom_params = data['custom_params']
        current_app.logger.info(f"收到自定义模型参数: {custom_params}")
    
    current_app.logger.info(f"训练集id: {file_id}, 模型选择: {model}, 装机容量: {wfcapacity}, 训练集占比: {train_ratio}, 类型: {type(wfcapacity)}")

    upload_path = find_file_by_id(file_id, current_app.config['UPLOAD_FOLDER'])
    if not upload_path:
        current_app.logger.warning(f"没有找到对应id的训练集: {file_id}")
        return jsonify({'error': '无效的 file_id'}), 400

    # 初始化状态记录
    training_status[file_id] = {
        "status": "in_progress",
        "message": "训练已开始",
        "start_time": datetime.datetime.now().isoformat()
    }

    # 运行预测与后处理
    try:
        forecast_file_path,model_filepath,scaler_filepath = run_modeltrain(upload_path, model, train_ratio, custom_params)
    except Exception as e:
        current_app.logger.error(f"预测过程中出错: {e}")
        return jsonify({'error': '预测过程中出错', 'details': str(e)}), 500

    if not isinstance(forecast_file_path, str) or not os.path.isfile(forecast_file_path):
        current_app.logger.error("预测时没有返回可用的文件路径")
        return jsonify({'error': '预测文件生成失败'}), 500

    # 保存预测结果到 DOWNLOAD_FOLDER
    forecast_timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename_wo_ext = os.path.splitext(os.path.basename(upload_path))[0]
    output_filename = f"forecast_{filename_wo_ext}_{forecast_timestamp_str}.csv"
    output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], output_filename)

    try:
        shutil.copy(forecast_file_path, output_path)
        current_app.logger.info(f"将原生预测文件复制到以下路径： {output_path}")
    except Exception as e:
        current_app.logger.error(f"无法保存预测结果文件: {e}")
        return jsonify({'error': '无法保存预测结果文件', 'details': str(e)}), 500

    # 评估模型
    try:
        evaluation_output_dir = os.path.join(current_app.config['DOWNLOAD_FOLDER'], f"evaluation_{filename_wo_ext}_{forecast_timestamp_str}")
        
        # 准备模型信息字典，用于增强报告
        model_info = {
            'model_type': model,
            'train_ratio': train_ratio,
            'custom_params': custom_params
        }
        
        evaluation_result, report_path = run_evaluation(
            output_path, 
            evaluation_output_dir, 
            wfcapacity=wfcapacity,
            model_info=model_info
        )
        current_app.logger.info(f"测试集评估完成。相关结果保存在以下路径：{evaluation_output_dir}")
    except Exception as e:
        current_app.logger.error(f"模型评估过程中出错: {e}")
        return jsonify({'error': '模型评估过程中出错', 'details': str(e)}), 500

    # 准备报告下载链接（如果存在）
    if report_path and os.path.exists(report_path):
        report_output_filename = f"report_{filename_wo_ext}_{forecast_timestamp_str}.txt"
        report_output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], report_output_filename)
        try:
            shutil.copy(report_path, report_output_path)
            current_app.logger.info(f"将原生报告复制到以下路径： {report_output_path}")
            report_download_url = f"/download/{secure_filename(report_output_filename)}"
        except Exception as e:
            current_app.logger.error(f"无法保存评估报告文件: {e}")
            return jsonify({'error': '无法保存评估报告文件', 'details': str(e)}), 500
    else:
        report_download_url = None

    download_url = f"/download/{secure_filename(output_filename)}"
    current_app.logger.info(f"预测文件下载url为: {download_url}")
    current_app.logger.info(f"训练报告下载url为: {report_download_url}")

    # 在模型训练之后增加MinIO上传和数据库记录
    db = SessionLocal()
    
    try:
        # 生成唯一标识
        model_version = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 上传模型文件到MinIO（wind-model桶）
        model_object_name = f"{model_version}/model.joblib"
        minio_client.fput_object(
            "wind-models", 
            model_object_name,
            model_filepath
        )
        
        # 上传scaler文件到MinIO（wind-scaler桶）
        scaler_object_name = f"{model_version}/scaler.joblib"
        minio_client.fput_object(
            "wind-scalers", 
            scaler_object_name,
            scaler_filepath
        )
        
        # 上传评估文件到MinIO（wind-metrics桶）
        metrics_files = []
        for root, dirs, files in os.walk(evaluation_output_dir):
            for file in files:
                local_path = os.path.join(root, file)
                object_name = f"{model_version}/metrics/{file}"
                minio_client.fput_object(
                    "wind-metrics",
                    object_name,
                    local_path
                )
                metrics_files.append(object_name)
        
        # 如果有评估报告则上传
        if report_path and os.path.exists(report_path):
            report_object_name = f"{model_version}/report.txt"
            minio_client.fput_object(
                "wind-metrics",
                report_object_name,
                report_path
            )
            metrics_files.append(report_object_name)

        # 保存到数据库（修改model_path和scaler_path为MinIO路径）
        new_model = Model(
            dataset_id=str(file_id),
            model_type=model,
            model_name=model_version,
            model_path=model_object_name,  # 改为MinIO路径
            scaler_path=scaler_object_name,  # 改为MinIO路径
            accuracy=float(evaluation_result['overall_metrics'].get('ACC')),
            train_time=datetime.datetime.now(),
            metrics_path=f"{model_version}/metrics",  # 改为存储父目录
            is_active=True
        )
        db.add(new_model)
        db.commit()
        db.refresh(new_model)
        # 保存评估指标
        evaluation_metrics = EvaluationMetrics(
            dataset_id=file_id,
            model_id=new_model.id,
            mae=float(evaluation_result['overall_metrics'].get('MAE')),
            mse=float(evaluation_result['overall_metrics'].get('MSE')),
            rmse=float(evaluation_result['overall_metrics'].get('RMSE')),
            acc=float(evaluation_result['overall_metrics'].get('ACC')),
            k=float(evaluation_result['overall_metrics'].get('K')),
            pe=float(evaluation_result['overall_metrics'].get('PE'))
        )
        db.add(evaluation_metrics)

        # 训练记录
        training_record = TrainingRecord(
            model_name=model_version,
            status='completed',
            dataset_path=upload_path,
            duration=(datetime.datetime.now() - new_model.train_time).total_seconds(),
            log_path=os.path.join(current_app.config['DOWNLOAD_FOLDER'], 'training_logs', f"{model_version}.log")
        )
        db.add(training_record)
        
        db.commit()

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"数据库操作失败: {e}")
        return jsonify({'error': '数据库操作失败', 'details': str(e)}), 500
    finally:
        db.close()

    # 在训练成功完成后更新状态
    def update_success_status(forecast_filename, report_filename=None):
        status_info = {
            "status": "completed",
            "message": "训练已完成",
            "end_time": datetime.datetime.now().isoformat(),
            "download_url": f"/download/{forecast_filename}"
        }
        
        if report_filename:
            status_info["report_download_url"] = f"/download/{report_filename}"
            
        training_status[file_id] = status_info
    
    # 在训练失败时更新状态
    def update_failure_status(error_message):
        training_status[file_id] = {
            "status": "failed",
            "message": f"训练失败: {error_message}",
            "end_time": datetime.datetime.now().isoformat()
        }
    
    # 在返回响应前更新状态信息
    update_success_status(output_filename, report_output_filename)

    return jsonify({
        'download_url': download_url,
        'report_download_url': report_download_url
    }), 200

# 新增接口：获取 daily_metrics.csv 文件
@modeltrain_bp.route('/get-daily-metrics', methods=['GET'])
def get_daily_metrics():
    file_id = request.args.get('file_id')
    if not file_id:
        return jsonify({'error': '缺少 file_id 参数'}), 400

    # 假设动态目录为 evaluation_output_dir
    upload_path = find_file_by_id(file_id, current_app.config['UPLOAD_FOLDER'])
    if not upload_path:
        return jsonify({'error': '无效的 file_id'}), 400

    filename_wo_ext = os.path.splitext(os.path.basename(upload_path))[0]
    evaluation_output_dir = os.path.join(current_app.config['DOWNLOAD_FOLDER'], f"evaluation_{filename_wo_ext}_*")

    # 找到动态目录下的 daily_metrics.csv 文件
    evaluation_dir = glob.glob(evaluation_output_dir)
    if not evaluation_dir:
        return jsonify({'error': '找不到评估结果文件'}), 404

    daily_metrics_path = os.path.join(evaluation_dir[0], 'daily_metrics.csv')
    if not os.path.exists(daily_metrics_path):
        return jsonify({'error': '找不到 daily_metrics.csv 文件'}), 404

    # 返回 CSV 文件内容给前端
    return send_file(daily_metrics_path, mimetype='text/csv', as_attachment=False)

@modeltrain_bp.route('/check-training-status', methods=['GET'])
def check_training_status():
    """检查训练状态的接口
    
    根据file_id查询训练状态和结果链接
    """
    file_id = request.args.get('file_id')
    
    if not file_id:
        return jsonify({"error": "缺少file_id参数"}), 400
    
    # 从状态字典中获取该训练任务的状态
    status_info = training_status.get(file_id, {})
    
    # 如果找不到状态记录，尝试检查文件是否存在
    if not status_info:
        # 查找是否有对应的结果文件
        forecast_pattern = f"forecast_train_test_{file_id}_*.csv"
        report_pattern = f"report_train_test_{file_id}_*.txt"
        
        forecast_files = glob.glob(os.path.join(current_app.config['FORECAST_FOLDER'], forecast_pattern))
        report_files = glob.glob(os.path.join(current_app.config['FORECAST_FOLDER'], report_pattern))
        
        if forecast_files or report_files:
            # 文件存在，说明训练已完成
            status_info = {
                "status": "completed",
                "message": "训练已完成"
            }
            
            # 提取最新的文件
            if forecast_files:
                latest_forecast = max(forecast_files, key=os.path.getctime)
                forecast_filename = os.path.basename(latest_forecast)
                status_info["download_url"] = f"/download/{forecast_filename}"
            
            if report_files:
                latest_report = max(report_files, key=os.path.getctime)
                report_filename = os.path.basename(latest_report)
                status_info["report_download_url"] = f"/download/{report_filename}"
                
            # 更新状态记录
            training_status[file_id] = status_info
        else:
            # 检查是否存在正在进行的训练任务
            if os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], f"{file_id}.csv")):
                status_info = {
                    "status": "in_progress",
                    "message": "训练正在进行中"
                }
            else:
                status_info = {
                    "status": "not_found",
                    "message": "未找到相关训练任务"
                }
    
    return jsonify(status_info)
