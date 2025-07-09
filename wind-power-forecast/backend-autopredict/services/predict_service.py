from scripts.predict import predict


def run_predict(CSV_FILE_PATH, MODEL_PATH, SCALER_PATH):
    # 调用训练与预测函数
    print("开始预测,执行run_predict函数")
    predcit_file_path_temp = predict(CSV_FILE_PATH=CSV_FILE_PATH, MODEL_PATH=MODEL_PATH, SCALER_PATH=SCALER_PATH,WINDOW_SIZE=16)

    return predcit_file_path_temp
