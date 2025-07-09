from scripts.train_run import train_run
from scripts.prediction_timestamp import post_process_predictions

def run_modeltrain(upload_path, model, train_ratio=0.9, custom_params=None):
    # 调用训练与预测函数
    forecast_file_path_temp,model_filepath,scaler_filepath = train_run(
        DATA_FILE_PATH=upload_path, 
        MODEL=model, 
        TRAIN_RATIO=train_ratio,
        CUSTOM_PARAMS=custom_params
    )
    # 后处理预测结果
    forecast_file_path = post_process_predictions(upload_path, forecast_file_path_temp)
    return forecast_file_path,model_filepath,scaler_filepath
