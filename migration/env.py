# 导入标准库
import os
import sys
import importlib
import pkgutil
from logging.config import fileConfig

# 导入 SQLAlchemy 和 Alembic 相关模块
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import create_engine
from alembic import context

# --- [新添加] 显式导入自定义的金仓方言 ---
try:
    import kingbase_dialect
    print("信息：已成功导入自定义 kingbase_dialect 模块。")
except ImportError as e:
    print(f"警告：无法导入自定义 kingbase_dialect 模块。错误: {e}")
    # 根据需要，您可以在这里决定是否让脚本失败，或者只是打印警告
# --- 结束新添加 ---

# --- [重要] 配置模块搜索路径 ---
# 这部分代码确保 Alembic 能够找到你的后端应用程序模块
# 添加多个可能的路径，提高Docker环境兼容性
project_dirs = [
    # 容器内可能的路径
    '/app',
    # 相对路径
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'wind-power-forecast', 'backend')),
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
    # 如果运行在wind-power-forecast目录下
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
]

# 添加所有可能的路径到sys.path
for dir_path in project_dirs:
    if os.path.exists(dir_path) and dir_path not in sys.path:
        sys.path.insert(0, dir_path)
        print(f"信息：添加 {dir_path} 到系统路径")
# --- 结束路径配置 ---

# --- [新添加] 显式导入自定义的金仓方言 ---
try:
    import kingbase_dialect
    print("信息：已成功导入自定义 kingbase_dialect 模块。")
except ImportError as e:
    print(f"警告：无法导入自定义 kingbase_dialect 模块。错误: {e}")
    # 根据需要，您可以在这里决定是否让脚本失败，或者只是打印警告
# --- 结束新添加 ---

# --- [关键配置 1] 导入所有模型 ---
# 导入Base定义
try:
    # 首先尝试从db_models包导入Base
    from db_models import Base
    print("信息：从 'db_models' 包导入 Base 成功")
except ImportError:
    try:
        # 如果失败，尝试从models包导入Base（兼容性）
        from models import Base
        print("信息：从 'models' 包导入 Base 成功")
    except ImportError:
        try:
            # 如果失败，尝试从base.py导入
            from base import Base
            print("信息：从 'base' 模块导入 Base 成功")
        except ImportError as e:
            print(f"错误：无法导入 Base。请确保 db_models/base.py 或 base.py 文件存在。错误详情: {e}")
            sys.exit(1)

# 自动导入所有模型模块确保它们被注册到Base.metadata
def import_all_models():
    """导入模型包下的所有模块以确保所有模型都被加载"""
    try:
        # 尝试从db_models包导入并注册所有模型
        import db_models
        for _, name, is_pkg in pkgutil.iter_modules(db_models.__path__):
            if not is_pkg:  # 只处理文件，不处理子包
                try:
                    importlib.import_module(f'db_models.{name}')
                    print(f"信息：已导入模型模块 'db_models.{name}'")
                except ImportError as e:
                    print(f"警告：无法导入模型模块 'db_models.{name}'。错误: {e}")
    except ImportError:
        # 如果没有找到db_models包，尝试使用models包（兼容性）
        try:
            import models
            for _, name, is_pkg in pkgutil.iter_modules(models.__path__):
                if not is_pkg:  # 只处理文件，不处理子包
                    try:
                        importlib.import_module(f'models.{name}')
                        print(f"信息：已导入模型模块 'models.{name}'")
                    except ImportError as e:
                        print(f"警告：无法导入模型模块 'models.{name}'。错误: {e}")
        except (ImportError, AttributeError):
            # 如果没有models包，尝试查找其他可能包含模型的模块
            print("警告：找不到模型包，尝试导入单独的模型文件...")
            try:
                # 尝试导入models.py
                import models
                print("信息：已导入 'models' 模块")
            except ImportError:
                print("警告：找不到 'models' 模块")
                
            # 尝试导入autopredict.py中的TaskHistory
            try:
                from routes.autopredict import TaskHistory
                print("信息：已导入 'routes.autopredict.TaskHistory' 模型")
            except ImportError:
                print("警告：找不到 'routes.autopredict.TaskHistory' 模型")

# 导入所有模型
print("信息：开始导入所有模型...")
import_all_models()
# --- 结束关键配置 1 ---

# 尝试获取数据库连接 URI
try:
    # 1. 尝试从环境变量 'DATABASE_URL' 读取
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    # 2. 如果环境变量没有，尝试从 database_config.py (如果存在)
    if not SQLALCHEMY_DATABASE_URI:
        try:
            from database_config import SQLALCHEMY_DATABASE_URI as db_uri_from_config
            if db_uri_from_config:
                 SQLALCHEMY_DATABASE_URI = db_uri_from_config
                 print("信息：从 database_config.py 获取数据库 URI")
        except ImportError:
            # database_config.py 不存在或不包含 URI，继续尝试下一个
            pass
        except NameError:
             # database_config.py 中可能没有这个变量名
             pass

    # 3. 如果还是没有，尝试从 config.py (你需要根据实际情况调整)
    if not SQLALCHEMY_DATABASE_URI:
        try:
            from config import Config # 假设你的配置在 Config 类中
            # 你需要根据你的 config.py 实现来获取 URI
            # 示例 (如果 URI 是 Config 类的静态/类属性):
            # SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI
            # 示例 (如果需要实例化 Config):
            # app_config = Config()
            # SQLALCHEMY_DATABASE_URI = app_config.SQLALCHEMY_DATABASE_URI

            # --- ↓↓↓ 如果你使用 config.py，请取消注释并修改下面的逻辑 ↓↓↓ ---
            # pass # 占位符，需要你根据 config.py 实现
            # --- ↑↑↑ 如果你使用 config.py，请取消注释并修改上面的逻辑 ↑↑↑ ---
            if SQLALCHEMY_DATABASE_URI: # 检查是否通过config.py获取到了值
                 print("信息：从 config.py 获取数据库 URI")

        except ImportError:
            # config.py 不存在或获取失败，继续
            pass

    # 4. 尝试从容器环境变量构建连接字符串
    if not SQLALCHEMY_DATABASE_URI:
        db_host = os.environ.get("DB_HOST", "kingbase")  # 使用服务名作为主机名
        db_port = os.environ.get("DB_PORT", "54321")     # 金仓数据库端口
        db_user = os.environ.get("DB_USER", "system")
        db_password = os.environ.get("DB_PASSWORD", "12345678ab")
        db_name = os.environ.get("DB_NAME", "windpower")
        # 使用自定义的kingbase方言
        SQLALCHEMY_DATABASE_URI = f"postgresql+kingbase://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        print(f"信息：从环境变量构建数据库连接URI: {SQLALCHEMY_DATABASE_URI[:SQLALCHEMY_DATABASE_URI.find('://')+3]}... (密码已隐藏)")

    # 5. 如果以上方法都失败，使用之前脚本中的硬编码作为最后的备选 (强烈不推荐用于生产！)
    if not SQLALCHEMY_DATABASE_URI:
        # 使用自定义的kingbase方言
        SQLALCHEMY_DATABASE_URI = "postgresql+kingbase://system:12345678ab@localhost:54321/windpower"
        print("\n" + "*"*80)
        print("警告：无法从环境变量或配置文件中找到数据库连接 URI。")
        print(f"警告：正在使用 env.py 中硬编码的 URI: {SQLALCHEMY_DATABASE_URI}")
        print("警告：请务必通过环境变量 DATABASE_URL 或修改 env.py 配置来提供正确的数据库连接！")
        print("*"*80 + "\n")

except ImportError as e:
    print(f"错误：导入数据库配置时出错。请检查 backend/database_config.py 或 backend/config.py。错误详情: {e}")
    sys.exit(1)

# Alembic Config 对象，提供对 .ini 文件值的访问。
config = context.config

# 解释 .ini 文件用于 Python 日志记录。(通常不需要修改)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- [关键配置 2] 设置 target_metadata ---
# 将此变量指向你的 SQLAlchemy 模型的元数据对象 (Base.metadata)
# 这是 Alembic 进行 autogenerate (自动生成迁移脚本) 所必需的
target_metadata = Base.metadata
# --- 结束关键配置 2 ---

# --- [新位置] 定义 include_object 为模块级函数 ---
def include_object(object, name, type_, reflected, compare_to):
    schema_name = object.schema if hasattr(object, 'schema') else None
    # 保持这个详细的打印，直到问题解决
    print(f"DEBUG [include_object]: name='{name}', type='{type_}', schema='{schema_name}', reflected={reflected}")

    if type_ == "table" and reflected: # 只关心从数据库反射回来的表
        # 如果表名是这两个之一，并且 Alembic 报告其 schema 为 None
        if name == "_kingbase_loginfo" and schema_name is None:
            print(f"INFO: [include_object] Intentionally ignoring reflected table '{name}' (schema reported as None by Alembic).")
            return False
        if name == "dual" and schema_name is None:
            print(f"INFO: [include_object] Intentionally ignoring reflected table '{name}' (schema reported as None by Alembic).")
            return False
    return True


def run_migrations_offline() -> None:
    """在 'offline' 模式下运行迁移。
    这种模式主要用于生成 SQL 脚本，而不直接连接数据库。
    """
    # --- [关键配置 3] 离线模式使用获取到的 URI ---
    # 不再从 alembic.ini 读取 sqlalchemy.url
    url = SQLALCHEMY_DATABASE_URI
    context.configure(
        url=url,                       # 使用我们获取的数据库连接 URI
        target_metadata=target_metadata, # 指向你的模型元数据
        literal_binds=True,            # 使生成的 SQL 包含字面值而不是占位符
        dialect_opts={"paramstyle": "named"},
    )
    # --- 结束关键配置 3 ---

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在 'online' 模式下运行迁移。
    这种模式会直接连接到数据库来应用迁移。
    """
    # --- [关键配置 4 - 修正] 在线模式配置数据库引擎 ---
    connectable = None # 初始化 connectable
    
    # 确保将数据库URL注入配置
    config_section = config.get_section(config.config_ini_section, {})
    config_section['sqlalchemy.url'] = SQLALCHEMY_DATABASE_URI
    
    try:
        # 1. 尝试使用engine_from_config
        print("信息：使用配置创建数据库引擎...")
        connectable = engine_from_config(
            config_section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        print("信息：使用 engine_from_config 创建引擎成功。")
    except Exception as e:
        # 2. 如果失败，尝试直接使用create_engine
        print(f"警告：engine_from_config 失败 ({e})。尝试直接使用 create_engine...")
        try:
            connectable = create_engine(SQLALCHEMY_DATABASE_URI, poolclass=pool.NullPool)
            print("信息：直接使用 create_engine 创建引擎成功。")
        except Exception as ce_exc:
            print(f"\n错误：创建数据库引擎失败！")
            print(f"错误：请检查数据库连接 URI 是否正确以及数据库服务是否可达。")
            print(f"错误详情: {ce_exc}\n")
            sys.exit(1)

    # 使用连接运行迁移
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object # 引用模块级别的函数
        )

        with context.begin_transaction():
            context.run_migrations()

# 根据 Alembic 的调用方式（离线或在线）选择执行相应的函数
if context.is_offline_mode():
    print("信息：在离线模式下运行迁移...")
    run_migrations_offline()
else:
    print("信息：在在线模式下运行迁移...")
    run_migrations_online()

print("信息：migration/env.py 执行完毕。")
