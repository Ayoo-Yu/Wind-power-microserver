#run_auto_train.py
from data_processor import load_data, preprocess_data, split_data, feature_engineering, scale_data, create_time_window
from models import get_lightgbm_params
from train import train_and_evaluate, save_predictions
from utils import visualize_results
from config_middle import WINDOW_SIZE, TRAIN_RATIO, LAGS,OUTPUT_DIR_TRAIN,Today,PREC_SV_FOLDER,MODEL_FOLDER,OUTPUT_DIR_PRE
import os
import time

def train_model(DATA_FILE_PATH,MODEL_FOLDER_TODAY):
    # 配置
    file_path = DATA_FILE_PATH
    window_size = WINDOW_SIZE
    lags = LAGS
    train_radio = TRAIN_RATIO
    model_folder_today = MODEL_FOLDER_TODAY
    output_dir = OUTPUT_DIR_TRAIN
    print(f"输出结果将保存到: {output_dir}")
    
    # 数据加载与预处理
    data = load_data(file_path)
    X, y = preprocess_data(data)
    X_train, X_val, y_train, y_val = split_data(X, y, train_radio)
    X_train_fe, X_val_fe = feature_engineering(X_train, X_val, lags)
    
    # 数据标准化
    X_train_scaled, X_val_scaled, scaler = scale_data(X_train_fe, X_val_fe)
    
    # 创建时间窗口
    X_train_windows, y_train_windows = create_time_window(X_train_scaled, y_train.values, window_size)
    X_val_windows, y_val_windows = create_time_window(X_val_scaled, y_val.values, window_size)
    
    params_list = get_lightgbm_params()
    
    # 训练与评估
    results_dict = train_and_evaluate(X_train_windows, y_train_windows, X_val_windows, y_val_windows, params_list, scaler,model_folder_today)
    
    # 保存预测结果
    save_predictions(results_dict, y_val_windows, output_base_dir=output_dir)

    
    # 可视化结果
    visualize_results(results_dict, y_val_windows, output_dir)

# 获取今天的日期
today_date = Today
csv_file = os.path.join(PREC_SV_FOLDER, f'{today_date}.csv')
model_folder_today = os.path.join(MODEL_FOLDER, today_date)
model_file = os.path.join(model_folder_today, 'model.joblib')  # 模型文件名为'model.joblib'
scaler_file = os.path.join(model_folder_today, 'scaler.joblib')  # 假设缩放器文件名为'scaler.joblib'

# 记录今天是否已执行过训练
flag_file = os.path.join(OUTPUT_DIR_PRE, f'{today_date}_done.flag')

# 检查预测是否已执行
def check_prediction_done():
    return os.path.exists(flag_file)

# 监视文件夹的变化
def watch_folder():
    print(f"开始监视 {PREC_SV_FOLDER} 文件夹...")
    while True:
        # 如果今天的预测已经完成，跳过
        if check_prediction_done():
            print(f"今天的预测已经执行过，跳过...")
            break
        
        # 检查是否有新文件
        if os.path.exists(csv_file):
            print(f"发现新的文件：{csv_file}，执行预测...")
            train_model(csv_file,model_folder_today)
            with open(flag_file, 'w') as f:
                f.write(f'Prediction done for {today_date}\n')
            break
        
        time.sleep(5)  # 每5秒检查一次文件夹

# 启动监视程序
watch_folder()
