import matplotlib.pyplot as plt

def visualize_results(results_dict, y_val, output_path='power_predictions_comparison.png'):
    """
    可视化不同模型的预测结果与实际值
    """
    plt.figure(figsize=(20, 10))
    for model_name, result in results_dict.items():
        plt.plot(range(len(result['y_pred'])), result['y_pred'], label=f'{model_name} Predicted Power')
    
    plt.plot(range(len(y_val)), y_val, label='Actual Power', linestyle='dashed')
    plt.xlabel('Index')
    plt.ylabel('Power')
    plt.title('Verify set power predictions')
    plt.legend()
    
    # 保存图像
    plt.savefig(output_path)
    print(f"图像已保存为{output_path}")
    
