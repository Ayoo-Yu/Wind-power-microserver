import os
from flask import Blueprint, request, jsonify, current_app
import datetime
import shutil
from services.file_service import find_file_by_id
from services.predict_service import run_predict
from werkzeug.utils import secure_filename
from models import PredictionRecord, Model, Dataset
from database_config import minio_client, SessionLocal
import pandas as pd

# 预测蓝图
predict_bp = Blueprint('predict', __name__)

@predict_bp.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    current_app.logger.info(f"收到预测请求: {data}")
    if not data or 'csvfileId' not in data or 'modelfileId' not in data or 'scalerfileId' not in data:
        current_app.logger.warning("缺少部分数据ID参数")
        return jsonify({'error': "缺少 'file_id' 或 'model' 参数"}), 400

    csvfileId = data['csvfileId']
    modelfileId = data['modelfileId']
    scalerfileId = data['scalerfileId']
    current_app.logger.info(f"预测数据选择: {csvfileId}, 预测模型选择: {modelfileId}, 归一化模型选择: {scalerfileId}")

    csvupload_path = find_file_by_id(csvfileId, current_app.config['UPLOAD_FOLDER'])
    modelupload_path = find_file_by_id(modelfileId, current_app.config['UPLOAD_FOLDER'])
    scalerupload_path = find_file_by_id(scalerfileId, current_app.config['UPLOAD_FOLDER'])
    if not csvupload_path:
        current_app.logger.warning(f"没有找到对应id的预测数据: {csvfileId}")
        return jsonify({'error': '无效的csvfileId'}), 400
    if not modelupload_path:
        current_app.logger.warning(f"没有找到对应id的预测模型: {modelfileId}")
        return jsonify({'error': '无效的modelfileId'}), 400
    if not scalerupload_path:
        current_app.logger.warning(f"没有找到对应id的归一化模型: {scalerfileId}")
        return jsonify({'error': '无效的scalerfileId'}), 400

    # 获取数据库会话
    db = SessionLocal()

    # 获取关联的数据库记录
    dataset_record = db.query(Dataset).filter(Dataset.file_id == csvfileId).first()
    
    if not dataset_record:
        current_app.logger.error("找不到对应的数据集或模型记录")
        return jsonify({'error': '无效的数据集或模型ID'}), 400

    # 运行预测与后处理
    try:
        forecast_file_path = run_predict(CSV_FILE_PATH=csvupload_path, MODEL_PATH=modelupload_path, SCALER_PATH=scalerupload_path)
    except Exception as e:
        current_app.logger.error(f"预测过程中出错: {e}")
        return jsonify({'error': '预测过程中出错', 'details': str(e)}), 500

    if not isinstance(forecast_file_path, str) or not os.path.isfile(forecast_file_path):
        current_app.logger.error("预测时没有返回可用的文件路径")
        return jsonify({'error': '预测文件生成失败'}), 500

    # 读取预测结果
    try:
        predictions_df = pd.read_csv(forecast_file_path)
        predictions_data = predictions_df.to_dict('records')
        
        # 保存预测结果到 DOWNLOAD_FOLDER
        forecast_timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename_wo_ext = os.path.splitext(os.path.basename(csvupload_path))[0]
        output_filename = f"forecast_{filename_wo_ext}_{forecast_timestamp_str}.csv"
        output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], output_filename)

        shutil.copy(forecast_file_path, output_path)
        current_app.logger.info(f"将原生预测文件复制到以下路径： {output_path}")
        
        # 使用minio_client直接上传
        bucket_name = "wind-predictions"
        object_name = output_filename
        
        minio_client.fput_object(
            bucket_name,
            object_name,
            forecast_file_path
        )
        current_app.logger.info(f"文件已上传到MinIO: {bucket_name}/{object_name}")
        
        # 创建预测记录时添加minio信息
        prediction_record = PredictionRecord(
            model_id=modelfileId,
            input_data_id=csvfileId,
            scaler_id=scalerfileId,
            prediction_time=datetime.datetime.now(),
            output_path=f"s3://{bucket_name}/{object_name}",
            prediction_type='batch',
            status='completed',
        )
        db.add(prediction_record)
        db.commit()
        
        # 更新返回的下载URL为MinIO路径
        download_url = f"/download/{secure_filename(output_filename)}"
        
        return jsonify({
            'download_url': download_url,
            'prediction_id': prediction_record.id,
            'predictions': predictions_data
        }), 200
        
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"处理预测结果失败: {e}")
        return jsonify({'error': '无法处理预测结果', 'details': str(e)}), 500