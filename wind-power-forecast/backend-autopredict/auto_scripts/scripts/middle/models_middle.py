# models_middle.py

# 所有LightGBM参数组版本记录
PARAM_VERSIONS = {
    # 初始参数组（起始版本）
    '20250321': {
        'gbdt': {
            'boosting_type': 'gbdt',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'name': 'GBDT',
            'importance_type':'gain'
        },
        'dart': {
            'boosting_type': 'dart',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'drop_rate': 0.1,
            'name': 'DART',
            'importance_type':'gain'
        },
        'goss': {
            'boosting_type': 'goss',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'top_rate': 0.2,
            'other_rate': 0.1,
            'name': 'GOSS',
            'importance_type':'gain'
        }
    }
    # 新版本参数会在这里自动添加
}

# 获取最新版本的参数组
def get_latest_param_version():
    """返回最新版本的参数组版本号"""
    return sorted(PARAM_VERSIONS.keys())[-1]

def get_lightgbm_params(version=None):
    """
    定义三种不同的LightGBM模型参数
    
    参数:
    version: 参数版本号，如果不指定则使用最新版本
    
    返回:
    包含三种不同LightGBM参数配置的列表
    """
    if version is None:
        version = get_latest_param_version()
    
    if version not in PARAM_VERSIONS:
        print(f"警告: 参数版本 {version} 不存在，使用最新版本")
        version = get_latest_param_version()
    
    params = PARAM_VERSIONS[version]
    return [params['gbdt'], params['dart'], params['goss']]

def get_unified_params(version=None):
    """
    返回统一的模型超参数，将用于不同的数据子集训练
    
    参数:
    version: 参数版本号，如果不指定则使用最新版本
    
    返回:
    包含三种不同LightGBM参数配置的列表
    """
    return get_lightgbm_params(version)

def add_new_param_version(version, gbdt_params, dart_params, goss_params):
    """
    添加新的参数版本
    
    参数:
    version: 新的版本号，通常为日期格式如'20250328'
    gbdt_params: GBDT算法的参数字典
    dart_params: DART算法的参数字典
    goss_params: GOSS算法的参数字典
    
    返回:
    是否成功添加
    """
    if version in PARAM_VERSIONS:
        print(f"错误: 参数版本 {version} 已经存在")
        return False
    
    # 确保参数包含必要的键
    required_keys = ['boosting_type', 'objective', 'metric', 'name']
    for params in [gbdt_params, dart_params, goss_params]:
        for key in required_keys:
            if key not in params:
                print(f"错误: 参数缺少必要的键 {key}")
                return False
    
    # 添加新版本
    PARAM_VERSIONS[version] = {
        'gbdt': gbdt_params,
        'dart': dart_params,
        'goss': goss_params
    }
    
    print(f"成功添加新参数版本: {version}")
    return True

def save_param_versions_to_file():
    """
    将当前参数版本保存到文件
    """
    import os
    import json
    from datetime import datetime
    
    # 获取当前文件路径
    current_file = os.path.abspath(__file__)
    
    # 备份当前文件
    backup_file = f"{current_file}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
    try:
        with open(current_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"已备份当前文件到: {backup_file}")
    except Exception as e:
        print(f"备份文件失败: {str(e)}")
        return False
    
    # 更新文件内容
    try:
        with open(current_file, 'w', encoding='utf-8') as f:
            f.write("# models.py\n\n")
            f.write("# 所有LightGBM参数组版本记录\n")
            f.write("PARAM_VERSIONS = {\n")
            
            # 写入所有版本的参数
            for version, params in sorted(PARAM_VERSIONS.items()):
                f.write(f"    # 版本 {version}\n")
                f.write(f"    '{version}': {{\n")
                
                # 写入每种算法的参数
                for algo, algo_params in params.items():
                    f.write(f"        '{algo}': {{\n")
                    for k, v in algo_params.items():
                        if isinstance(v, str):
                            f.write(f"            '{k}': '{v}',\n")
                        else:
                            f.write(f"            '{k}': {v},\n")
                    f.write("        },\n")
                
                f.write("    },\n")
            
            f.write("}\n\n")
            
            # 写入函数定义
            with open(__file__, 'r', encoding='utf-8') as src:
                in_param_versions = False
                for line in src:
                    if line.strip() == "# 所有LightGBM参数组版本记录":
                        in_param_versions = True
                    elif in_param_versions and line.strip() == "}" or line.strip() == "})":
                        in_param_versions = False
                        continue
                    
                    if not in_param_versions and not line.startswith("PARAM_VERSIONS"):
                        if line.strip() and not line.strip().startswith("#"):
                            f.write(line)
        
        print(f"成功更新参数文件")
        return True
    except Exception as e:
        print(f"更新文件失败: {str(e)}")
        return False