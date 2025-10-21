from scripts.train_run import train_run
from scripts.prediction_timestamp import post_process_predictions

def run_modeltrain(upload_path, model, train_ratio=0.9, custom_params=None, farm_code='DEFAULT_FARM'):
    """
    运行模型训练（支持多场站）

    Args:
        upload_path: 数据文件路径
        model: 模型类型
        train_ratio: 训练集比例
        custom_params: 自定义参数
        farm_code: 场站代码

    Returns:
        tuple: (预测文件路径, 模型文件路径, 标准化器文件路径)
    """
    # 调用训练与预测函数（添加场站信息）
    forecast_file_path_temp, model_filepath, scaler_filepath = train_run(
        DATA_FILE_PATH=upload_path,
        MODEL=model,
        TRAIN_RATIO=train_ratio,
        CUSTOM_PARAMS=custom_params,
        FARM_CODE=farm_code  # 传递场站代码
    )
    # 后处理预测结果（添加场站信息）
    forecast_file_path = post_process_predictions(upload_path, forecast_file_path_temp, farm_code=farm_code)
    return forecast_file_path, model_filepath, scaler_filepath
