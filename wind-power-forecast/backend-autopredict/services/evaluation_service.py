import os
from scripts.evaluator_model import evaluate_model

def run_evaluation(data_path, evaluation_output_dir, wfcapacity, model_info=None):
    evaluation_result = evaluate_model(
        data_path=data_path,
        save_plots=True,
        save_csv=True,
        save_report=True,
        custom_save_dir=evaluation_output_dir,
        wfcapacity=wfcapacity,
        model_info=model_info
    )
    # 假设 report 文件名固定为 model_evaluation_report.txt
    report_path = os.path.join(evaluation_output_dir, 'model_evaluation_report.txt')
    print("run_evaluation 没问题")
    return evaluation_result, report_path if os.path.exists(report_path) else None
