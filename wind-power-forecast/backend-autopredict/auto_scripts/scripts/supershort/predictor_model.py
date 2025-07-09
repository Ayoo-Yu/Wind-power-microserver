import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import os
import joblib
import sys
import logging

# 添加backend-autopredict到sys.path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# 这将导航到backend-autopredict目录（从supershort向上三级）
path_to_backend_autopredict = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
if path_to_backend_autopredict not in sys.path:
    sys.path.insert(0, path_to_backend_autopredict)
    # print(f"[DEBUG predictor_model] 已添加到sys.path: {path_to_backend_autopredict}")

class WindPowerPredictor:
    def __init__(self, n_shift):
        self.n_shift = n_shift
        self.model = xgb.XGBRegressor(
            n_estimators=100, learning_rate=0.1, max_depth=6,
            min_child_weight=1, subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.numeric_features = None # 将在训练时首次设置或从文件加载(预测时)
        self.target_col_name = f'power_diff_{self.n_shift}'
        self.feature_power_t_minus_N_col_name = f'power_actual_at_t_minus_{self.n_shift}'
        self._is_fitted = False

    def _prepare_features_common(self, data):
        features_original_copy = data.copy()
        new_feature_series_list = []

        # 1. 计算 power_actual(t-N)
        # 假设传入的 data['wp_true'] 已经在调用此方法前（例如在 predict.py 中）经过了必要的填充处理
        if 'wp_true' not in features_original_copy.columns:
            print(f"[警告 Shift={self.n_shift}] _prepare_features_common: 'wp_true' 列在输入数据中未找到。")
            print(f"         '{self.feature_power_t_minus_N_col_name}' 将全为NaN，可能导致预测重构失败。")
            power_at_t_minus_N_series = pd.Series(np.nan, index=features_original_copy.index)
        else:
            power_at_t_minus_N_series = features_original_copy['wp_true'].shift(self.n_shift)
            num_nan_in_shifted_series = power_at_t_minus_N_series.isnull().sum()
            num_nan_in_original_wp_true = features_original_copy['wp_true'].isnull().sum()

            if num_nan_in_shifted_series > 0:
                # 情况1: 原始 wp_true (填充后) 在开头就有 NaN，shift 后这些 NaN 仍然存在
                if num_nan_in_original_wp_true > 0 and num_nan_in_shifted_series >= num_nan_in_original_wp_true:
                    # 差值部分是由于 shift 本身在数据头部引入的
                    nan_due_to_shift_op = num_nan_in_shifted_series - num_nan_in_original_wp_true
                    print(f"[信息 Shift={self.n_shift}] '{self.feature_power_t_minus_N_col_name}' 中存在 {num_nan_in_shifted_series} 个NaN值.")
                    if num_nan_in_original_wp_true > 0:
                        print(f"         其中约 {num_nan_in_original_wp_true} 个NaN可能源于原始 'wp_true' 列数据开头部分的NaN (即使经过ffill也无法填充的部分)。")
                    if nan_due_to_shift_op > 0 :
                         print(f"         另外约 {nan_due_to_shift_op} 个NaN是由于 .shift({self.n_shift}) 操作在数据有效部分的开头引入的（预期行为）。")

                # 情况2: 原始 wp_true (填充后) 没有 NaN，所有 NaN 都是 shift 引入的
                elif num_nan_in_original_wp_true == 0 and num_nan_in_shifted_series > 0:
                    print(f"[信息 Shift={self.n_shift}] '{self.feature_power_t_minus_N_col_name}' 中存在 {num_nan_in_shifted_series} 个NaN值，均由 .shift({self.n_shift}) 操作在数据开头引入（预期行为）。")
                # 其他可能组合（理论上较少见，如果ffill有效）
                else:
                    print(f"[信息 Shift={self.n_shift}] '{self.feature_power_t_minus_N_col_name}' 中存在 {num_nan_in_shifted_series} 个NaN值。原始 'wp_true' 有 {num_nan_in_original_wp_true} 个NaN。")


        power_at_t_minus_N_series.name = self.feature_power_t_minus_N_col_name
        new_feature_series_list.append(power_at_t_minus_N_series)

        # 2. 计算目标变量: power(t) - power(t-N) (主要用于训练)
        if 'wp_true' not in features_original_copy.columns:
            target_series = pd.Series(np.nan, index=features_original_copy.index)
        else:
            # 如果 wp_true 或 wp_true.shift(N) 有 NaN，目标也会有 NaN
            target_series = features_original_copy['wp_true'] - features_original_copy['wp_true'].shift(self.n_shift)
        target_series.name = self.target_col_name
        
        # --- 其他特征工程部分 (风速差等) ---
        heights = [10, 100, 200]
        for height in heights:
            ws_cols_base = [f'ws{height}_{i}' for i in range(1, 16)]
            ws_cols = [col for col in ws_cols_base if col in features_original_copy.columns]
            
            if len(ws_cols) < 2 and len(ws_cols_base) >=2 :
                 print(f"[警告 Shift={self.n_shift}] _prepare_features_common: 高度 {height}m 的风速列不足 ({len(ws_cols)}/{len(ws_cols_base)})，无法计算部分差分特征。")

            for i in range(len(ws_cols)-1):
                new_col_name = f'ws{height}_diff_{i}'
                series = features_original_copy[ws_cols[i+1]] - features_original_copy[ws_cols[i]]
                series.name = new_col_name
                new_feature_series_list.append(series)
            for col in ws_cols:
                series_prev1 = features_original_copy[col] - features_original_copy[col].shift(1)
                series_prev1.name = f'{col}_diff_prev1'
                new_feature_series_list.append(series_prev1)
                series_prev2 = features_original_copy[col] - features_original_copy[col].shift(2)
                series_prev2.name = f'{col}_diff_prev2'
                new_feature_series_list.append(series_prev2)
                series_prev3 = features_original_copy[col] - features_original_copy[col].shift(3)
                series_prev3.name = f'{col}_diff_prev3'
                new_feature_series_list.append(series_prev3)
        
        all_series_to_concat = [features_original_copy] + [target_series] + new_feature_series_list
        features_with_all_cols = pd.concat(all_series_to_concat, axis=1)
        
        numeric_cols_after_concat = features_with_all_cols.select_dtypes(include=[np.number]).columns
        
        potential_features_exclusions = [self.target_col_name]
        if 'wp_true' in features_with_all_cols.columns:
            potential_features_exclusions.append('wp_true')

        potential_features = [
            col for col in numeric_cols_after_concat 
            if col not in potential_features_exclusions
        ]
        
        original_index = features_with_all_cols.index
        
        # 定义用于 dropna 的列集合
        subset_for_dropna = []
        if self.numeric_features is None or not self._is_fitted: # 训练阶段
            # 训练时，需要所有潜在特征和目标列都没有 NaN
            subset_for_dropna.extend(potential_features)
            if self.target_col_name in features_with_all_cols.columns:
                 subset_for_dropna.append(self.target_col_name)
            # 如果 power_t_minus_N 被视为一个潜在特征，它已经在 potential_features 中
        else: # 预测阶段
            # 预测时，需要模型训练时使用的所有数值特征都没有 NaN
            subset_for_dropna.extend(self.numeric_features)
            # 并且，用于重构的 power_actual_at_t_minus_N_col_name 也必须没有 NaN
            if self.feature_power_t_minus_N_col_name in features_with_all_cols.columns and \
               self.feature_power_t_minus_N_col_name not in subset_for_dropna:
                subset_for_dropna.append(self.feature_power_t_minus_N_col_name)
        
        # 确保 subset_for_dropna 中的列实际存在于 DataFrame 中，避免 KeyError
        valid_subset_for_dropna = [col for col in subset_for_dropna if col in features_with_all_cols.columns]

        if not valid_subset_for_dropna and subset_for_dropna: # 如果期望有列但实际都没有
            print(f"[警告 Shift={self.n_shift}] _prepare_features_common: 用于 dropna 的列 {subset_for_dropna} 均不在 DataFrame 中。将不执行 dropna，可能导致后续错误。")
            features_cleaned = features_with_all_cols.copy() # 或者可以考虑引发错误
        elif not valid_subset_for_dropna: # 如果本来就没有列用于dropna
            features_cleaned = features_with_all_cols.copy()
        else:
            features_cleaned = features_with_all_cols.dropna(subset=valid_subset_for_dropna)
        
        valid_index_after_dropna = features_cleaned.index

        if self.numeric_features is None: # 训练时第一次设置
            # 从 potential_features 中筛选出在 features_cleaned 中仍然存在的列
            self.numeric_features = [f for f in potential_features if f in features_cleaned.columns]
            
            if self.feature_power_t_minus_N_col_name in self.numeric_features:
                print(f"[信息 Shift={self.n_shift}] 训练时，特征 '{self.feature_power_t_minus_N_col_name}' 已作为输入特征。")
            elif self.feature_power_t_minus_N_col_name in features_cleaned.columns and \
                 self.feature_power_t_minus_N_col_name in potential_features: # 检查它是否本应是特征
                print(f"[警告 Shift={self.n_shift}] 训练时，特征 '{self.feature_power_t_minus_N_col_name}' 存在于处理后数据中但未被选为数值输入特征。可能在 dropna 中被移除或排除逻辑问题。")
            
            if not self.numeric_features:
                 print(f"[严重警告 Shift={self.n_shift}] 训练时，dropna 后未找到任何可用数值特征。模型无法训练。")
        
        else: # 预测时，self.numeric_features 已经从文件加载
            missing_from_cleaned = [f for f in self.numeric_features if f not in features_cleaned.columns]
            if missing_from_cleaned:
                print(f"[警告 Shift={self.n_shift}] _prepare_features_common (预测时): 模型训练时使用的特征 {missing_from_cleaned} 在当前处理后的数据 (features_cleaned) 中不存在。这可能因为它们在原始预测数据中缺失，或者在 dropna 步骤中因NaN被移除。这将导致后续构建 X_test 时出错。")

        return features_cleaned, valid_index_after_dropna, original_index

    def train(self, train_data):
        print(f"--- 开始训练模型 (Shift={self.n_shift}) ---")
        
        # 确保在准备特征时，dropna 会正确考虑目标列 (通过 self._is_fitted 状态)
        original_is_fitted_state = self._is_fitted 
        self._is_fitted = False # 标记为"非拟合"状态，以触发训练时的dropna逻辑
        
        features_cleaned, valid_idx, _ = self._prepare_features_common(train_data) 
        
        self._is_fitted = original_is_fitted_state # 恢复 _is_fitted 状态 (虽然如果训练成功，下面会设为True)

        if self.numeric_features is None or not self.numeric_features:
            print(f"[错误 Shift={self.n_shift}] 没有可用的数值特征进行训练。请检查数据预处理和特征工程步骤。")
            return False
        if self.target_col_name not in features_cleaned.columns:
            print(f"[错误 Shift={self.n_shift}] 目标列 '{self.target_col_name}' 在处理后的特征中未找到。")
            return False
        
        if features_cleaned.loc[valid_idx, self.target_col_name].isnull().any():
            num_null_targets = features_cleaned.loc[valid_idx, self.target_col_name].isnull().sum()
            print(f"[错误 Shift={self.n_shift}] 目标列 '{self.target_col_name}' 在有效索引处仍包含 {num_null_targets} 个 NaN 值，尽管已执行 dropna。检查 dropna 的 subset 配置。")
            return False

        X_train = features_cleaned.loc[valid_idx, self.numeric_features]
        y_train = features_cleaned.loc[valid_idx, self.target_col_name]

        if X_train.empty or y_train.empty:
            print(f"[警告 Shift={self.n_shift}] 训练集 X_train ({len(X_train)}行) 或 y_train ({len(y_train)}行) 为空，跳过训练。")
            return False
        
        # 确保 X_train 的所有列名都是字符串类型
        X_train.columns = X_train.columns.astype(str)

        logging.info(f"[超短效] 即将为模型 (Shift={self.n_shift}) 开始训练。")
        # logging.info(f"[超短效] 最后10行 X_train (特征数据) 预览:\n{X_train.tail(10).to_string()}")
        # logging.info(f"[超短效] 最后10行 y_train (目标数据) 预览:\n{y_train.tail(10).to_string()}")

        try:
            X_train_scaled = self.scaler.fit_transform(X_train)
        except ValueError as e:
             print(f"[错误 Shift={self.n_shift}] 特征标准化失败: {e}. 通常是因为 X_train 包含NaN或非数值数据，或者数据维度问题。")
             # print(f"X_train dtypes:\n{X_train.dtypes}")
             # print(f"X_train NaN sum:\n{X_train.isnull().sum()}")
             return False
        
        self.model.fit(X_train_scaled, y_train)
        self._is_fitted = True # 标记为已拟合
        print(f"--- 模型训练完成 (Shift={self.n_shift}) ---")
        return True

    def predict(self, test_data):
        if not self._is_fitted:
            print(f"[错误 Shift={self.n_shift}] 模型尚未训练或加载状态，无法预测。")
            return pd.Series(index=test_data.index, dtype=float) # 返回与输入索引一致的空序列

        print(f"--- 开始预测 (Shift={self.n_shift}) ---")
        # 预测时，_is_fitted 应该是 True，_prepare_features_common 会使用对应的 dropna 逻辑
        features_cleaned, valid_idx, original_idx_of_test_data = self._prepare_features_common(test_data)
        
        # 初始化一个与原始 test_data 索引对齐的 Series 来存储最终预测结果
        predictions_aligned_to_original = pd.Series(np.nan, index=original_idx_of_test_data, dtype=float)

        if self.numeric_features is None or not self.numeric_features:
            print(f"[错误 Shift={self.n_shift}] 预测时 self.numeric_features 未设置 (可能未成功加载或训练时为空)。无法预测。")
            return predictions_aligned_to_original
        
        if valid_idx.empty: 
            print(f"[警告 Shift={self.n_shift}] 处理后的测试特征 (features_cleaned) 在 dropna 后为空，无法预测。")
            return predictions_aligned_to_original
        
        # 检查 X_test 所需的特征是否存在
        missing_for_xtest = [col for col in self.numeric_features if col not in features_cleaned.columns]
        if missing_for_xtest:
             print(f"[错误 Shift={self.n_shift}] 准备 X_test 时，模型需要的特征 {missing_for_xtest} 在 features_cleaned 中找不到。无法进行标准化和预测。")
             return predictions_aligned_to_original 

        X_test = features_cleaned.loc[valid_idx, self.numeric_features]
        
        if X_test.empty:
            print(f"[警告 Shift={self.n_shift}] 筛选后的 X_test (在有效索引上) 为空，无法预测。")
            return predictions_aligned_to_original
        
        # 确保 X_test 的所有列名都是字符串类型
        X_test.columns = X_test.columns.astype(str)
        
        # logging.info(f"[超短效] 最后10行 X_test (最终预测输入特征) 预览:\n{X_test.tail(10).to_string()}")

        try:
            X_test_scaled = self.scaler.transform(X_test)
        except Exception as e: 
            print(f"[错误 Shift={self.n_shift}] 预测时特征标准化失败: {e}. 请检查 X_test 的列是否与训练时完全一致，并且不含NaN。")
            # print(f"X_test columns for scaler: {X_test.columns.tolist()}")
            # print(f"Scaler's expected n_features_in_: {self.scaler.n_features_in_}")
            # print(f"X_test NaN sum:\n{X_test.isnull().sum()}")
            return predictions_aligned_to_original

        power_diff_pred_values = self.model.predict(X_test_scaled)
        power_diff_pred_series = pd.Series(power_diff_pred_values, index=valid_idx)
        
        # 重构最终功率预测值
        if self.feature_power_t_minus_N_col_name not in features_cleaned.columns:
            print(f"[错误 Shift={self.n_shift}] 预测重构时关键特征 '{self.feature_power_t_minus_N_col_name}' 未在 features_cleaned 中找到。最终预测将不包含此项，可能导致结果为NaN或仅为差值。")
            power_actual_t_minus_N_for_reconstruction = pd.Series(np.nan, index=valid_idx)
        else:
            power_actual_t_minus_N_for_reconstruction = features_cleaned.loc[valid_idx, self.feature_power_t_minus_N_col_name]
            if power_actual_t_minus_N_for_reconstruction.isnull().all() and not power_diff_pred_series.empty and not power_diff_pred_series.isnull().all():
                 print(f"[警告 Shift={self.n_shift}] 用于重构的 '{self.feature_power_t_minus_N_col_name}' 在有效索引上全为 NaN。最终预测可能全为 NaN 或与差值预测相同（如果差值非NaN）。")
            elif power_actual_t_minus_N_for_reconstruction.isnull().any():
                 num_nans_reconstruct = power_actual_t_minus_N_for_reconstruction.isnull().sum()
                 total_valid_points = len(power_actual_t_minus_N_for_reconstruction)
                 print(f"[信息 Shift={self.n_shift}] 用于重构的 '{self.feature_power_t_minus_N_col_name}' 在 {total_valid_points} 个有效索引点中有 {num_nans_reconstruct} 个 NaN 值。这些点的最终预测将是 NaN。")

        final_predictions_on_valid_idx = power_diff_pred_series + power_actual_t_minus_N_for_reconstruction
        final_predictions_clipped_on_valid_idx = np.maximum(final_predictions_on_valid_idx, 0) # 确保功率不为负

        # 使用 .update() 将计算得到的预测值（在valid_idx上）更新到与原始输入对齐的Series中
        # .update() 会原地修改 predictions_aligned_to_original，只在 matching index labels 处更新
        predictions_aligned_to_original.update(final_predictions_clipped_on_valid_idx)
        
        num_actual_predictions = predictions_aligned_to_original.notna().sum()
        if num_actual_predictions == 0 and not final_predictions_clipped_on_valid_idx.empty and not final_predictions_clipped_on_valid_idx.isnull().all():
             print(f"[警告 Shift={self.n_shift}] 预测值已计算，但在对齐到原始索引后，未能生成任何非NaN的预测。检查索引对齐或所有重构组件是否为NaN。")
        elif num_actual_predictions > 0:
             print(f"[信息 Shift={self.n_shift}] 成功生成 {num_actual_predictions} 个预测点。")
        else: # final_predictions_clipped_on_valid_idx 为空或全为 NaN
            print(f"[信息 Shift={self.n_shift}] 未能生成任何有效预测值（可能由于输入数据不足或处理后为空）。")


        print(f"--- 完成预测 (Shift={self.n_shift}) ---")
        return predictions_aligned_to_original

    def save_state(self, directory):
        if not self._is_fitted:
            print(f"[警告 Shift={self.n_shift}] 模型未拟合，无法保存状态。")
            return False
        try:
            os.makedirs(directory, exist_ok=True)
            model_path = os.path.join(directory, 'xgb_model.json')
            scaler_path = os.path.join(directory, 'scaler.joblib')
            features_path = os.path.join(directory, 'numeric_features.joblib')
            config_path = os.path.join(directory, 'predictor_config.joblib')

            self.model.save_model(model_path)
            joblib.dump(self.scaler, scaler_path)
            joblib.dump(self.numeric_features, features_path)
            
            config_data = {
                'feature_power_t_minus_N_col_name': self.feature_power_t_minus_N_col_name,
                'target_col_name': self.target_col_name,
                'n_shift_saved': self.n_shift # 保存 n_shift 以便校验
            }
            joblib.dump(config_data, config_path)

            print(f"模型状态 (Shift={self.n_shift}) 已保存到: {directory}")
            return True
        except Exception as e:
            print(f"[错误 Shift={self.n_shift}] 保存模型状态失败: {e}")
            return False

    def load_state(self, directory):
        try:
            model_path = os.path.join(directory, 'xgb_model.json')
            scaler_path = os.path.join(directory, 'scaler.joblib')
            features_path = os.path.join(directory, 'numeric_features.joblib')
            config_path = os.path.join(directory, 'predictor_config.joblib')

            required_files = [model_path, scaler_path, features_path, config_path]
            if not all(os.path.exists(p) for p in required_files):
                missing_files_str = ", ".join([os.path.basename(f) for f in required_files if not os.path.exists(f)])
                print(f"[错误 Shift={self.n_shift}] 状态文件不完整于: {directory}. 缺少: {missing_files_str}")
                self._is_fitted = False
                return False

            self.model = xgb.XGBRegressor() 
            self.model.load_model(model_path)
            self.scaler = joblib.load(scaler_path)
            self.numeric_features = joblib.load(features_path) 
            if not self.numeric_features: # 如果加载的特征列表为空
                print(f"[警告 Shift={self.n_shift}] 加载的 numeric_features 列表为空。这可能表明训练时没有选出特征。")


            config_data = joblib.load(config_path)
            
            # 校验 n_shift (可选但推荐)
            n_shift_saved = config_data.get('n_shift_saved')
            if n_shift_saved is not None and n_shift_saved != self.n_shift:
                print(f"[警告 Shift={self.n_shift}] 当前 n_shift ({self.n_shift}) 与模型保存时的 n_shift ({n_shift_saved}) 不匹配。")
                # 可以根据需要决定是否中止或继续
                # self.n_shift = n_shift_saved # 或者强制使用保存的 n_shift

            loaded_p_t_minus_n_name = config_data.get('feature_power_t_minus_N_col_name')
            if loaded_p_t_minus_n_name:
                self.feature_power_t_minus_N_col_name = loaded_p_t_minus_n_name
            else:
                print(f"[警告 Shift={self.n_shift}] predictor_config.joblib 中未找到 'feature_power_t_minus_N_col_name'。将使用基于当前 n_shift 的默认名称: f'power_actual_at_t_minus_{self.n_shift}'")
                self.feature_power_t_minus_N_col_name = f'power_actual_at_t_minus_{self.n_shift}' # 确保与 _prepare_features_common 一致
            
            loaded_target_col_name = config_data.get('target_col_name')
            if loaded_target_col_name:
                self.target_col_name = loaded_target_col_name
            else:
                print(f"[警告 Shift={self.n_shift}] predictor_config.joblib 中未找到 'target_col_name'。将使用基于当前 n_shift 的默认名称: f'power_diff_{self.n_shift}'")
                self.target_col_name = f'power_diff_{self.n_shift}' # 确保与 _prepare_features_common 一致

            self._is_fitted = True
            print(f"模型状态 (Shift={self.n_shift}) 已从 {directory} 加载。")
            # print(f"  Loaded numeric_features: {self.numeric_features}")
            # print(f"  Loaded feature_power_t_minus_N_col_name: {self.feature_power_t_minus_N_col_name}")
            # print(f"  Loaded target_col_name: {self.target_col_name}")

            return True
        except Exception as e:
            print(f"[错误 Shift={self.n_shift}] 加载模型状态失败: {e}")
            self._is_fitted = False
            return False

def preprocess_data(data_input: pd.DataFrame) -> pd.DataFrame:
    """
    通用数据预处理函数。
    - 创建副本以避免修改原始 DataFrame。
    - 转换 Timestamp 列为 datetime 对象。
    - 移除 'Unnamed: 0' 列。
    - 去除重复行。
    - 使用 ffill 和 bfill 填充缺失值。
    """
    data = data_input.copy() 
    print("开始通用数据预处理...")
    if 'Timestamp' in data.columns:
        try:
            data['Timestamp'] = pd.to_datetime(data['Timestamp'])
            print("  已转换 'Timestamp' 列为 datetime 对象。")
        except Exception as e: 
            print(f"  转换 'Timestamp' 列为 datetime 对象失败: {e}")
    
    if 'Unnamed: 0' in data.columns:
        data = data.drop(columns=['Unnamed: 0'])
        print("  已移除 'Unnamed: 0' 列。")
    
    initial_rows = len(data)
    data = data.drop_duplicates()
    if len(data) < initial_rows: 
        print(f"  移除了 {initial_rows - len(data)} 行重复数据。")
    else:
        print("  未发现重复行。")
        
    nan_before = data.isnull().sum().sum()
    if nan_before > 0:
        print(f"  数据中存在 {nan_before} 个缺失值 (在所有列中)，尝试通用填充 (ffill then bfill)...")
        data_ffilled = data.fillna(method='ffill')
        data_filled = data_ffilled.fillna(method='bfill') # 再次填充以处理开头的 NaN
        
        # 检查哪些列在填充后仍然有NaN
        remaining_nan_cols = data_filled.columns[data_filled.isnull().any()].tolist()
        nan_after = data_filled.isnull().sum().sum()

        print(f"  通用填充后，移除了 {nan_before - nan_after} 个缺失值。")
        if nan_after > 0: 
            print(f"[警告] 数据在通用填充后仍有 {nan_after} 个缺失值。")
            print(f"       这些可能由于整列都是 NaN 或者数据开头/结尾的连续 NaN (ffill/bfill无法完全消除)。")
            print(f"       仍然包含 NaN 值的列 ( 后总体填充): {remaining_nan_cols}")
            # 特别注意：如果'wp_true'在这些列中， predict.py 中的 handle_wp_true_missing 会再次尝试处理它。
        data = data_filled
    else: 
        print("  数据中无缺失值 (在通用检查阶段)。")
        
    print("通用数据预处理完成。")
    return data