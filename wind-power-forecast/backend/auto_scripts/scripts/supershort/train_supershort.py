import pandas as pd
import os
import sys # <--- 添加这一行
from datetime import datetime

# 添加backend到sys.path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# 这将导航到backend目录（从supershort向上三级）
path_to_backend = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
if path_to_backend not in sys.path:
    sys.path.insert(0, path_to_backend)
    # print(f"[DEBUG train_supershort] 已添加到sys.path: {path_to_backend}")

from predictor_model import WindPowerPredictor, preprocess_data # 从本地文件导入
from data_processor_supershort import load_and_merge_data_from_db, update_supershort_training_csv_from_db, interpolate_and_ffill_wp_true # 新增：从数据库加载数据和更新CSV，以及空值处理函数
import logging # 新增：日志记录

# --- 配置日志 ---
# 获取当前脚本文件所在的目录
current_script_dir = os.path.dirname(os.path.abspath(__file__))

# 定义日志目录和文件路径
log_dir_base = os.path.join(current_script_dir, "logs")
auto_train_log_dir = os.path.join(log_dir_base, "auto_train")
os.makedirs(auto_train_log_dir, exist_ok=True) # 创建 auto_train 目录

# 使用当前日期生成日志文件名
today_date_str = datetime.now().strftime("%Y%m%d")
log_file_name = f"{today_date_str}_train_supershort.log"
log_file_path = os.path.join(auto_train_log_dir, log_file_name)

# 获取根日志记录器
logger = logging.getLogger()
logger.setLevel(logging.INFO) # 设置日志级别

# 创建并设置文件处理器
file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 创建并设置控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter) # 可以使用相同的格式器，或为控制台定义不同的格式器
logger.addHandler(console_handler)

# --- 配置参数 ---
# 导入配置以获取数据集目录路径
try:
    from config_supershort import DATASET_FOLDER,MODEL_FOLDER
except ImportError:
    DATASET_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datasets')
    os.makedirs(DATASET_FOLDER, exist_ok=True)
    logging.warning(f"无法导入config_supershort，使用默认数据集目录: {DATASET_FOLDER}")
    MODEL_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved_models')
    os.makedirs(MODEL_FOLDER, exist_ok=True)
    logging.warning(f"无法导入config_supershort，使用默认模型目录: {MODEL_FOLDER}")

def get_current_farm_code():
    return str(os.environ.get('FARM_CODE') or os.environ.get('DEFAULT_FARM_CODE') or 'DEFAULT_FARM').strip()


def get_training_csv_path(farm_code):
    return os.path.join(DATASET_FOLDER, f"training_data_supershort_{farm_code}.csv")


# 训练数据集CSV文件名
TRAINING_CSV_FILENAME = "training_data_supershort.csv"
TRAINING_CSV_PATH = get_training_csv_path(get_current_farm_code())

MODEL_OUTPUT_DIR = MODEL_FOLDER # 保存训练好的模型的目录
MIN_SHIFT = 1
MAX_SHIFT = 16
# --- 配置结束 ---

def main():
    """主函数：从数据库加载数据，使用全部数据训练16个模型并保存"""
    farm_code = get_current_farm_code()
    training_csv_path = get_training_csv_path(farm_code)

    # 1. 从数据库加载数据并保存到本地CSV文件
    logging.info("开始更新本地训练数据集 CSV, farm_code=%s...", farm_code)
    try:
        # 更新本地训练数据CSV文件
        update_success = update_supershort_training_csv_from_db(training_csv_path, farm_code=farm_code)
        
        if not update_success:
            logging.error(f"更新本地训练数据集 CSV 失败: {training_csv_path}")
            sys.exit(1)
        
        if not os.path.exists(training_csv_path):
            logging.error(f"本地训练数据集 CSV 不存在: {training_csv_path}")
            # 尝试直接从数据库加载
            logging.info("尝试直接从数据库加载数据作为备选方案...")
            data = load_and_merge_data_from_db(farm_code=farm_code)
            if data.empty:
                logging.error("直接从数据库加载的数据也为空，无法进行训练。请检查 data_processor_supershort.py 的日志。")
                sys.exit(1)
            logging.info(f"成功从数据库直接加载 {len(data)} 条记录用于训练。")
        else:
            # 2. 从本地CSV加载训练数据
            logging.info(f"从本地CSV文件加载训练数据: {training_csv_path}")
            try:
                data = pd.read_csv(training_csv_path)
                if 'Timestamp' in data.columns:
                    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
                logging.info(f"成功从CSV加载 {len(data)} 条记录用于训练。")
            except Exception as e:
                logging.error(f"从CSV加载数据失败: {e}", exc_info=True)
                # 尝试直接从数据库加载作为备选方案
                logging.info("尝试直接从数据库加载数据作为备选方案...")
                data = load_and_merge_data_from_db(farm_code=farm_code)
                if data.empty:
                    logging.error("直接从数据库加载的数据也为空，无法进行训练。请检查 data_processor_supershort.py 的日志。")
                    sys.exit(1)
                logging.info(f"成功从数据库直接加载 {len(data)} 条记录用于训练。")
    except Exception as e:
        logging.error(f"处理训练数据时发生严重错误: {e}", exc_info=True)
        sys.exit(1)

    if data.empty:
        logging.error("获取的数据为空，无法进行训练。请检查CSV文件或数据库连接。")
        sys.exit(1)

    # 3. 预处理数据
    logging.info("开始预处理训练数据...")
    try:
        # 先使用插值和前向填充处理wp_true的空值
        logging.info("处理wp_true中的空值...")
        data = interpolate_and_ffill_wp_true(data)
        
        # 然后使用predictor_model.py中的通用预处理
        data = preprocess_data(data) # 使用 predictor_model.py 中的通用预处理
    except Exception as e:
        logging.error(f"数据预处理过程中发生错误: {e}", exc_info=True)
        sys.exit(1) # <--- 修改点：以非零码退出
    logging.info("训练数据预处理完成。")

    # 4. 定义训练集 (使用全部加载的数据)
    train_data = data.copy() 
    logging.info(f"\n数据总量 (预处理后): {len(data)}")
    logging.info(f"训练集大小: {len(train_data)} (使用全部加载和预处理后的数据)")

    if train_data.empty: # 确保在这一点也检查，尽管 preprocess_data 内部可能已处理
        logging.error("错误：预处理后的训练数据为空，无法进行训练。")
        sys.exit(1) # <--- 修改点：以非零码退出

    # 5. 创建模型输出目录
    try:
        os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)
        logging.info(f"模型将保存到: {MODEL_OUTPUT_DIR}")
    except OSError as e:
        logging.error(f"创建模型输出目录 {MODEL_OUTPUT_DIR} 失败: {e}")
        sys.exit(1) # <--- 修改点：以非零码退出

    # 6. 循环训练和保存 16 个模型 (n=2 到 n=17)
    successful_trains = 0
    for n in range(MIN_SHIFT, MAX_SHIFT + 1):
        logging.info(f"\n{'='*10} 开始处理训练 Horizon (Shift) = {n} {'='*10}")

        # 初始化预测器
        predictor = WindPowerPredictor(n_shift=n)

        # 训练模型
        try:
            if predictor.train(train_data): # train 方法现在返回 True/False
                # 定义当前模型的保存子目录
                model_n_dir = os.path.join(MODEL_OUTPUT_DIR, f'shift_{n}')
                # 保存模型状态 (scaler, model, features)
                if predictor.save_state(model_n_dir):
                    successful_trains += 1
                    logging.info(f"Shift={n} 的模型成功训练并保存到 {model_n_dir}")
                    # 训练分位数模型（复用已训练的 predictor 实例）
                    try:
                        predictor.train_quantile(train_data, alpha=0.05)
                        predictor.train_quantile(train_data, alpha=0.95)
                        predictor.save_state(model_n_dir)
                    except Exception as qe:
                        logging.warning("shift %d 分位数训练失败: %s", n, qe)
                else:
                    logging.warning(f"Shift={n} 的模型训练成功，但保存失败。")
            else:
                logging.warning(f"[失败] Shift={n} 的模型未能成功训练。检查 predictor_model.py 中的日志获取详细信息。")
        except Exception as e:
            logging.error(f"训练或保存 Shift={n} 模型时发生意外错误: {e}", exc_info=True)

    logging.info(f"\n{'='*10} 训练过程完成 {'='*10}")
    logging.info(f"总共成功训练并保存了 {successful_trains} 个模型。")

    # --- 注册模型到 ModelRegistry ---
    try:
        from model_registry import ModelRegistry
        farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')
        registry = ModelRegistry()

        for n in range(MIN_SHIFT, MAX_SHIFT + 1):
            model_dir = os.path.join(MODEL_OUTPUT_DIR, f'shift_{n}')
            model_path = os.path.join(model_dir, 'model.joblib')
            scaler_path = os.path.join(model_dir, 'scaler.joblib')

            if not os.path.exists(model_path):
                continue

            registry.register(
                farm_code=farm_code,
                task_type="supershort",
                algorithm="xgboost",
                model_path=model_path,
                scaler_path=scaler_path if os.path.exists(scaler_path) else None,
                val_accuracy=None,
            )
        logging.info("已注册超短期模型到 ModelRegistry")
    except Exception as reg_e:
        logging.warning(f"超短期模型注册失败（不影响训练结果）: {reg_e}", exc_info=True)
    # --- 注册结束 ---

    # 确保所有模型都已成功训练
    expected_model_count = MAX_SHIFT - MIN_SHIFT + 1
    if successful_trains < expected_model_count:
        logging.error(f"错误：未能成功训练所有预期的 {expected_model_count} 个模型。实际成功: {successful_trains}")
        sys.exit(1)
    else:
        logging.info(f"成功训练并保存了所有预期的 {successful_trains}/{expected_model_count} 个模型。")

if __name__ == '__main__':
    main()
    print("TRAIN_SUPERSHORT.PY SCRIPT IS TRULY FINISHING NOW AND EXITING.") # 添加一个明确的结束打印
    logging.info("TRAIN_SUPERSHORT.PY SCRIPT IS TRULY FINISHING NOW AND EXITING.") # 也记录到日志
