"""
集中管理后端运行时配置。

提供 ``get_settings`` / ``settings`` 便捷访问，后续所有模块应优先从此处读取配置，
避免在各处重复解析环境变量。
"""

from .settings import AppSettings, get_settings

__all__ = ["AppSettings", "get_settings"]

# 方便直接引用的单例
settings = get_settings()


