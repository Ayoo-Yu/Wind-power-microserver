from scripts.predict import predict


def run_predict(CSV_FILE_PATH, MODEL_PATH, SCALER_PATH, farm_code=''):
    """
    运行预测（支持多场站）

    Args:
        CSV_FILE_PATH: 数据文件路径
        MODEL_PATH: 模型文件路径
        SCALER_PATH: 标准化器文件路径
        farm_code: 场站代码

    Returns:
        str: 预测结果文件路径
    """
    # 调用训练与预测函数（传递场站信息）
    print(f"开始预测,执行run_predict函数，场站代码: {farm_code}")
    predcit_file_path_temp = predict(CSV_FILE_PATH=CSV_FILE_PATH, MODEL_PATH=MODEL_PATH, SCALER_PATH=SCALER_PATH, WINDOW_SIZE=16, farm_code=farm_code)

    return predcit_file_path_temp
