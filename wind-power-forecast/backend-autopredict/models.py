# models.py - 导入兼容层
# 此文件用于保持向后兼容性，将所有导入重定向到db_models包

# 导入所有db_models内容
from db_models import *

import warnings
warnings.warn(
    "从 'models' 模块直接导入已弃用。请使用 'from db_models import ...' 代替。",
    DeprecationWarning,
    stacklevel=2
)

# 不要在这里重新定义模型！
# 所有模型都应当从db_models包导入
