from sqlalchemy.orm import declarative_base
Base = declarative_base()

# 这个文件将被迁移到db_models/base.py
# 为了保持兼容性，我们导入新模型包的Base
try:
    from db_models.base import Base, TimeStampMixin
except ImportError:
    # 当直接导入此文件时，不需要额外操作
    pass