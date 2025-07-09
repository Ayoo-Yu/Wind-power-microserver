#run_auto_predict.py
import os
import time
import logging
from datetime import datetime
from predict import predict_power
from config_middle import PREC_SV_FOLDER, MODEL_FOLDER, OUTPUT_DIR_PRE

# 配置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

today_date = datetime.today().strftime('%Y%m%d')
csv_file = os.path.join(PREC_SV_FOLDER, f'{today_date}.csv')
model_folder_today = os.path.join(MODEL_FOLDER, today_date)

# 检查最佳模型目录，优先使用best_models目录下的模型
best_models_dir = os.path.join(model_folder_today, 'best_models')
if os.path.exists(best_models_dir):
    models_dir = best_models_dir
    print(f"将使用最佳模型目录: {best_models_dir}")
    logger.info(f"将使用最佳模型目录: {best_models_dir}")
else:
    models_dir = model_folder_today
    print(f"未找到最佳模型目录，使用当日模型目录: {model_folder_today}")
    logger.info(f"未找到最佳模型目录，使用当日模型目录: {model_folder_today}")

# 输出文件路径
output_dir = os.path.join(OUTPUT_DIR_PRE, today_date)
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, f'{today_date}.csv')

# 标志文件，用于检查是否已经执行过预测
flag_file = os.path.join(OUTPUT_DIR_PRE, f'{today_date}_done.flag')

def check_prediction_done():
    """检查今天的预测是否已经执行过"""
    return os.path.exists(flag_file)

def watch_folder():
    """监视文件夹，发现新文件时执行预测"""
    print(f"开始监视 {PREC_SV_FOLDER} 文件夹...")
    logger.info(f"开始监视 {PREC_SV_FOLDER} 文件夹...")
    
    while True:
        if check_prediction_done():
            print(f"今天的预测已经执行过，跳过...")
            logger.info(f"今天的预测已经执行过，跳过...")
            break
        
        if os.path.exists(csv_file):
            print(f"发现新的文件：{csv_file}，执行预测...")
            logger.info(f"发现新的文件：{csv_file}，执行预测...")
            
            # 调用predict_power函数代替旧的predict函数
            # 默认窗口大小=16，滞后特征数=3，不指定特定模型类型和权重
            try:
                predict_power(
                    input_file=csv_file,
                    models_dir=models_dir,
                    output_file=output_file,
                    window_size=16,
                    lags=3,
                    model_types=None,  # 使用所有可用模型
                    weights=None,      # 使用等权重
                    months_back=None   # 使用所有数据
                )
                
                # 创建标志文件表示预测已完成
                with open(flag_file, 'w') as f:
                    f.write(f'Prediction done for {today_date}\n')
                
                print(f"预测完成，结果已保存到: {output_file}")
                logger.info(f"预测完成，结果已保存到: {output_file}")
            except Exception as e:
                print(f"预测过程中出错: {str(e)}")
                logger.error(f"预测过程中出错: {str(e)}")
                import traceback
                traceback.print_exc()
            
            break
        
        # 每5秒检查一次
        time.sleep(5)

# 启动监视程序
if __name__ == "__main__":
    watch_folder()
