from database_config import engine
from db_models import Base
# 修改导入路径。如果scripts.init_users路径不正确，请调整为正确的路径
from init_users import init_users_and_roles

# 创建所有表
Base.metadata.create_all(bind=engine)

# 初始化用户和角色
init_users_and_roles()

print("数据库初始化完成") 