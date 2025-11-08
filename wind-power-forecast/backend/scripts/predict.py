# predict.py

import os
import pandas as pd
import numpy as np
import joblib
try:
    from .data_processor import preprocess_data_pre, feature_engineering, create_time_window_pre
except ImportError:  # 在脚本模式下回退到绝对导入
    from data_processor import preprocess_data_pre, feature_engineering, create_time_window_pre

try:
    from .config import LAGS, OUTPUT_DIR, WINDOW_SIZE
except ImportError:  # 在脚本模式下回退到绝对导入
    from config import LAGS, OUTPUT_DIR, WINDOW_SIZE


def load_models_and_scaler(model_path, scaler_path):
    """
    根据传入的模型路径和 scaler 文件路径加载模型和 scaler
    """
    # 加载 scaler
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(f"Scaler 文件未找到: {scaler_path}")
    scaler = joblib.load(scaler_path)
    print(f"已加载 scaler。")
    # 加载模型
    model = joblib.load(model_path)
    print(f"已加载模型。")
    return model, scaler

def preprocess_new_data(file_path, lags):
    """
    对新数据进行预处理，包括特征工程和标准化
    """
    # 加载数据
    data = pd.read_csv(file_path)
    data = data.dropna()
    
    # 预处理
    X, timestamps = preprocess_data_pre(data)  # 获取时间戳
    
    # 特征工程
    X_fe, _ = feature_engineering(X, X, lags)  # 对新数据，验证集可以忽略

    X_fe = X_fe.reset_index(drop=True)
    if len(X_fe) < len(timestamps):
        timestamps = timestamps.iloc[len(timestamps) - len(X_fe):]
    else:
        timestamps = timestamps.iloc[:len(X_fe)]
    timestamps = timestamps.reset_index(drop=True)

    return X_fe, timestamps


def make_predictions(model, scaler, X_new, window_size, LAGS):
    """
    对新数据进行预测（带形状验证）
    """
    # ================== 输入验证阶段 ==================
    # 验证1：检查特征数量与缩放器匹配
    if X_new.shape[1] != scaler.n_features_in_:
        raise ValueError(
            f"特征数量不匹配！缩放器需要 {scaler.n_features_in_} 个特征，"
            f"但输入数据有 {X_new.shape[1]} 个特征\n"
            f"解决方案：检查是否包含多余特征或缺少必要特征"
        )

    # 验证2：检查数据长度足够创建窗口
    min_required_length = window_size + LAGS
    if X_new.shape[0] < min_required_length:
        raise ValueError(
            f"数据长度不足！需要至少 {min_required_length} 个时间步，"
            f"当前只有 {X_new.shape[0]} 个\n"
            f"解决方案：提供更长的输入数据或调整窗口参数"
        )

    # ================== 数据处理阶段 ==================
    try:
        X_scaled = scaler.transform(X_new)
    except ValueError as e:
        print("⚠️ 标准化失败！可能原因：")
        print(f"- 特征顺序与训练时不一致（第一个特征名：{scaler.feature_names_in_[0]}）")
        print(f"- 包含无效值（NaN/Inf），当前NaN数量：{np.isnan(X_new).sum()}")
        raise

    # ================== 窗口验证阶段 ==================
    X_windows = create_time_window_pre(X_scaled, window_size)
    
    # 验证3：检查窗口创建后的维度
    expected_window_shape = (X_new.shape[0] - window_size + 1, window_size, X_new.shape[1])
    if X_windows.shape != expected_window_shape:
        raise ValueError(
            f"窗口形状异常！预期 {expected_window_shape}，实际得到 {X_windows.shape}\n"
            f"可能原因：create_time_window_pre 函数参数错误"
        )

    # ================== 模型预测阶段 ==================
    # 将窗口数据展平（适配模型输入格式）
    model_input = X_windows.reshape(X_windows.shape[0], -1)
    
    # 验证4：检查模型输入维度
    if model_input.shape[1] != model.n_features_in_:
        raise ValueError(
            f"模型输入维度不匹配！模型需要 {model.n_features_in_} 个特征，"
            f"实际输入 {model_input.shape[1]} 个\n"
            f"可能原因：窗口大小设置错误（当前window_size={window_size}）"
        )

    # 执行预测
    try:
        preds = model.predict(model_input)
    except:
        print("❌ 预测失败！最后5行输入数据：")
        print(model_input[-5:])
        raise

    print(f"✅ 成功生成 {len(preds)} 个预测")
    return preds

def save_predictions_to_csv(
    predictions,
    timestamps,
    output_dir,
    model_path,
):
    """
    保存预测结果到 CSV 文件
    """
    os.makedirs(output_dir, exist_ok=True)
    
    if len(predictions) != len(timestamps):
        raise ValueError(
            f"预测结果与时间戳数量不一致，predictions={len(predictions)}, timestamps={len(timestamps)}"
        )

    df = pd.DataFrame({
        'Timestamp': timestamps,
        'Predicted Power': predictions
    })
    
    # 确保列名清晰可见
    df.columns = ['Timestamp', 'Predicted Power']
    
    model_name = model_path.split('/')[-1].split('.')[0]
    print(model_name)
    csv_filename = f'{model_name}_prediction.csv'
    csv_filepath = os.path.join(output_dir, csv_filename)
    df.to_csv(csv_filepath, index=False)
    print(f"{model_name} 的预测结果已保存到 {csv_filepath}")
    
    return csv_filepath
    
def predict(CSV_FILE_PATH, MODEL_PATH, SCALER_PATH, WINDOW_SIZE=16):
    """
    主预测函数，接收数据文件路径、模型文件路径和 scaler 文件路径
    """
    # 配置
    new_data_file_path = CSV_FILE_PATH
    model_path = MODEL_PATH
    scaler_path = SCALER_PATH
    window_size = WINDOW_SIZE
    output_dir = OUTPUT_DIR
    print(f"开始预测，使用的模型路径为：{MODEL_PATH}")
    # 加载模型和 scaler
    try:
        models, scaler = load_models_and_scaler(model_path, scaler_path)
    except FileNotFoundError as e:
        print(e)
        return None
    
    # 预处理新数据
    X_new, timestamps = preprocess_new_data(new_data_file_path, LAGS)
    print(f"新数据预处理完成，共 {len(X_new)} 个样本。")
    # 预测
    predictions = make_predictions(models, scaler, X_new, window_size, LAGS)
    print("预测完成。")
    # 保存预测结果
    predict_file_path = save_predictions_to_csv(predictions, timestamps, output_dir, MODEL_PATH)
    print("预测结果已保存。")
    return predict_file_path