import lightgbm as lgb

def get_lightgbm_params(model):
    """
    根据指定的模型类型返回相应的LightGBM参数。

    参数:
    model (str): 模型类型，必须是 'GBDT'、'DART'、'GOSS' 或 'CUSTOM'。

    返回:
    dict: 对应模型的参数字典。

    异常:
    ValueError: 如果未提供模型类型或模型类型无效。
    """
    if model is None:
        raise ValueError("必须提供模型类型 'model' 参数。可选类型为: 'GBDT', 'DART', 'GOSS', 'CUSTOM'.")

    params_dict = {
        'GBDT': {
            'boosting_type': 'gbdt',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'name': 'GBDT'
        },
        'DART': {
            'boosting_type': 'dart',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'drop_rate': 0.1,
            'name': 'DART'
        },
        'GOSS': {
            'boosting_type': 'goss',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'top_rate': 0.2,
            'other_rate': 0.1,
            'name': 'GOSS'
        },
        'CUSTOM': {
            'boosting_type': 'gbdt',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'name': 'CUSTOM'
        }
    }
    
    return params_dict.get(model, None)