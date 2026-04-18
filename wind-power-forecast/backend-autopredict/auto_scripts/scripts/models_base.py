"""Shared LightGBM model parameter definitions.

Contains parameter version history and helper functions for retrieving,
adding, and persisting parameter sets. Both ``models_short`` and
``models_middle`` re-export everything from this module.
"""

# ---------------------------------------------------------------------------
# Parameter version history
# ---------------------------------------------------------------------------

PARAM_VERSIONS = {
    # Initial parameter set
    '20250321': {
        'gbdt': {
            'boosting_type': 'gbdt',
            'objective': 'regression',
            'metric': 'rmse',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'name': 'GBDT',
            'importance_type': 'gain',
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
            'importance_type': 'gain',
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
            'importance_type': 'gain',
        },
    },
    # New versions are appended here automatically
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_latest_param_version():
    """Return the latest parameter version key."""
    return sorted(PARAM_VERSIONS.keys())[-1]


def get_lightgbm_params(version=None):
    """Return a list of three LightGBM parameter dicts (GBDT, DART, GOSS).

    Parameters
    ----------
    version : str | None
        Parameter version key.  If *None* the latest version is used.
    """
    if version is None:
        version = get_latest_param_version()

    if version not in PARAM_VERSIONS:
        print(f"警告: 参数版本 {version} 不存在，使用最新版本")
        version = get_latest_param_version()

    params = PARAM_VERSIONS[version]
    return [params['gbdt'], params['dart'], params['goss']]


def get_unified_params(version=None):
    """Return unified hyper-parameters for multi-dataset training.

    Currently identical to :func:`get_lightgbm_params`.
    """
    return get_lightgbm_params(version)


def add_new_param_version(version, gbdt_params, dart_params, goss_params):
    """Register a new parameter version.

    Returns *True* on success, *False* on validation failure.
    """
    if version in PARAM_VERSIONS:
        print(f"错误: 参数版本 {version} 已经存在")
        return False

    required_keys = ['boosting_type', 'objective', 'metric', 'name']
    for params in [gbdt_params, dart_params, goss_params]:
        for key in required_keys:
            if key not in params:
                print(f"错误: 参数缺少必要的键 {key}")
                return False

    PARAM_VERSIONS[version] = {
        'gbdt': gbdt_params,
        'dart': dart_params,
        'goss': goss_params,
    }
    print(f"成功添加新参数版本: {version}")
    return True


def get_quantile_params(version=None):
    """Generate 5% and 95% quantile parameters for each algorithm variant.

    Returns
    -------
    dict
        ``{'q05': [...], 'q95': [...]}`` with three param dicts each.
    """
    import copy
    base_params_list = get_unified_params(version)
    result = {}
    for quantile_key, alpha_val in [('q05', 0.05), ('q95', 0.95)]:
        q_params = []
        for params in base_params_list:
            p = copy.deepcopy(params)
            p['objective'] = 'quantile'
            p['alpha'] = alpha_val
            if 'metric' in p:
                p['metric'] = 'mae'
            q_params.append(p)
        result[quantile_key] = q_params
    return result


def save_param_versions_to_file():
    """Persist current parameter versions back to the source file."""
    import os
    from datetime import datetime

    current_file = os.path.abspath(__file__)

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

    try:
        with open(current_file, 'w', encoding='utf-8') as f:
            f.write("# models.py\n\n")
            f.write("# 所有LightGBM参数组版本记录\n")
            f.write("PARAM_VERSIONS = {\n")

            for version, params in sorted(PARAM_VERSIONS.items()):
                f.write(f"    # 版本 {version}\n")
                f.write(f"    '{version}': {{\n")
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

            with open(__file__, 'r', encoding='utf-8') as src:
                in_param_versions = False
                for line in src:
                    if line.strip() == "# 所有LightGBM参数组版本记录":
                        in_param_versions = True
                    elif in_param_versions and (
                        line.strip() == "}" or line.strip() == "})"
                    ):
                        in_param_versions = False
                        continue

                    if not in_param_versions and not line.startswith(
                            "PARAM_VERSIONS"):
                        if line.strip() and not line.strip().startswith("#"):
                            f.write(line)

        print("成功更新参数文件")
        return True
    except Exception as e:
        print(f"更新文件失败: {str(e)}")
        return False
