from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from minio import Minio
from config import KINGBASE_CONFIG, MINIO_CONFIG
from base import Base
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy.orm import Session
from db_models import Base, Model
from sqlalchemy import inspect
import time
import os
import subprocess
from sqlalchemy.pool import QueuePool  # 添加QueuePool导入
from sqlalchemy import event

# 导入自定义金仓方言
import kingbase_dialect

# 导出数据库连接URL供其他模块使用
print("构建数据库连接URL...")
print(f"DB_USER环境变量：{os.environ.get('DB_USER', '未设置')}")
print(f"KINGBASE_CONFIG['user']值：{KINGBASE_CONFIG['user']}")
print(f"DB_PASSWORD是否已设置：{'是' if os.environ.get('DB_PASSWORD') else '否'}")
print(f"DB_HOST环境变量：{os.environ.get('DB_HOST', '未设置')}")
print(f"DB_PORT环境变量：{os.environ.get('DB_PORT', '未设置')}")
print(f"DB_NAME环境变量：{os.environ.get('DB_NAME', '未设置')}")

# 使用KINGBASE_CONFIG中的配置构建连接URL
SQLALCHEMY_DATABASE_URI = f"postgresql+kingbase://{KINGBASE_CONFIG['user']}:{KINGBASE_CONFIG['password']}@{KINGBASE_CONFIG['host']}:{KINGBASE_CONFIG['port']}/{KINGBASE_CONFIG['database']}"

print(f"最终连接URL：{SQLALCHEMY_DATABASE_URI}")

# 保留旧变量名以保持兼容性
SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URI

# 创建engine，添加重试机制
def create_engine_with_retry():
    max_retries = 5
    retry_delay = 5  # 秒
    
    print("DEBUG: 进入 create_engine_with_retry 函数...")
    for attempt in range(max_retries):
        try:
            print(f"DEBUG: 尝试第 {attempt+1} 次创建引擎，使用 URI: {SQLALCHEMY_DATABASE_URI}")
            # 确保SQLALCHEMY_DATABASE_URI使用的是我们硬编码的值
            if 'postgres:' in SQLALCHEMY_DATABASE_URI:
                print("警告! 检测到连接字符串中包含 'postgres:' 用户!")
            
            # 更新连接池设置
            engine = create_engine(
                SQLALCHEMY_DATABASE_URI,
                poolclass=QueuePool,      # 使用QueuePool
                pool_size=10,             # 增加连接池大小
                max_overflow=10,          # 增加额外连接数
                pool_timeout=30,          # 等待连接的超时时间(秒)
                pool_recycle=300,         # 连接回收时间(5分钟)
                pool_pre_ping=True,       # 使用前检查连接是否有效
                # 使用LIFO方式可以让最近使用过的连接被复用，增加缓存命中率
                pool_use_lifo=True,
                echo_pool=True            # 输出连接池日志
            )
            
            # 添加连接池监听器，处理连接检出和归还事件
            @event.listens_for(engine, "checkout")
            def ping_connection(dbapi_connection, connection_record, connection_proxy):
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("SELECT 1")
                except:
                    # 如果连接失效，断开它，这样在下次使用时会创建新连接
                    connection_proxy._pool.dispose()
                    raise
                cursor.close()
            
            # 定期清理空闲连接
            @event.listens_for(engine, "checkin")
            def checkout_connection(dbapi_connection, connection_record):
                # 记录上次使用时间
                connection_record.info['last_use_time'] = time.time()
            
            return engine
            
        except Exception as e:
            print(f"创建数据库引擎失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                print("达到最大重试次数，无法创建数据库引擎")
                raise

# 使用重试机制创建engine
try:
    engine = create_engine_with_retry()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    print(f"警告: 数据库引擎创建失败: {e}")
    print("应用将继续启动，但数据库功能可能不可用")
    # 创建一个空的引擎和会话，以便应用能够启动
    engine = None
    SessionLocal = None

# 添加一个检查和清理空闲连接的函数
def cleanup_idle_connections(engine, idle_timeout=120):
    """清理空闲超过指定时间的连接"""
    if not engine:
        return
        
    try:
        for connection in engine.pool._pool:
            if hasattr(connection, 'info') and 'last_use_time' in connection.info:
                if time.time() - connection.info['last_use_time'] > idle_timeout:
                    # 标记连接为无效，这样它将被丢弃
                    connection.invalidate()
    except Exception as e:
        print(f"清理空闲连接时发生错误: {e}")

# 在engine创建之后检查迁移
def check_migrations():
    if engine is None:
        print("警告: 数据库引擎不可用，跳过迁移检查")
        return
        
    try:
        inspector = inspect(engine)
        
        if not inspector.has_table("models"):
            Base.metadata.create_all(engine)
            print("✅ 已自动创建缺失的数据库表")
    except Exception as e:
        print(f"警告: 迁移检查失败: {e}")

try:
    check_migrations()  # 现在engine已经定义
except Exception as e:
    print(f"警告: 迁移检查失败: {e}")

# 初始化MinIO客户端（使用config中的配置），添加重试机制
def init_minio_client():
    max_retries = 5
    retry_delay = 5  # 秒
    
    for attempt in range(max_retries):
        try:
            # 构建完整的endpoint字符串，包含端口
            endpoint = f"{MINIO_CONFIG['endpoint']}:{MINIO_CONFIG['port']}"
            
            client = Minio(
                endpoint,
                access_key=MINIO_CONFIG["access_key"],
                secret_key=MINIO_CONFIG["secret_key"],
                secure=MINIO_CONFIG["secure"]
            )
            
            # 测试连接
            client.list_buckets()
            return client
            
        except Exception as e:
            print(f"MinIO连接失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                print("达到最大重试次数，无法连接到MinIO")
                raise

try:
    minio_client = init_minio_client()
    
    # 修改后的初始化部分
    required_buckets = list(MINIO_CONFIG["buckets"].values())
    existing_buckets = [b.name for b in minio_client.list_buckets()]

    for bucket in required_buckets:
        if bucket not in existing_buckets:
            minio_client.make_bucket(bucket)
            print(f"✅ 成功创建存储桶: {bucket}")
        else:
            print(f"✅ 存储桶已存在: {bucket}")
            
    # 导入策略设置函数
    from config import set_bucket_policy
    
    # 设置存储桶策略
    for bucket_name, policy in MINIO_CONFIG["policies"].items():
        bucket_value = MINIO_CONFIG["buckets"].get(bucket_name.replace("wind-", ""))
        if bucket_value:
            try:
                set_bucket_policy(minio_client, bucket_value, policy)
                print(f"✅ 成功设置存储桶策略: {bucket_value} -> {policy}")
            except Exception as e:
                print(f"警告: 设置存储桶策略失败 ({bucket_value}): {e}")
                
except Exception as e:
    print(f"警告: MinIO初始化失败: {e}")
    print("应用将继续启动，但MinIO功能可能不可用")
    minio_client = None

def get_db():
    """获取数据库会话，并确保在使用后正确关闭"""
    print("调试: get_db函数被调用")
    if SessionLocal is None:
        print("警告: 数据库会话不可用")
        raise Exception("数据库连接不可用")
    
    # 清理空闲连接
    if engine:
        cleanup_idle_connections(engine)
    
    print(f"调试: 创建数据库会话，引擎连接URL为: {SQLALCHEMY_DATABASE_URI}")
    db = SessionLocal()
    try:
        yield db
    finally:
        # 确保会话关闭并归还到连接池
        if db:
            print("调试: 关闭数据库会话")
            db.close()

def cleanup_old_models(db: Session, keep_last=5):
    """保留最近5个模型版本"""
    if minio_client is None:
        print("警告: MinIO客户端不可用，跳过清理旧模型")
        return
        
    try:
        # 获取所有模型按时间倒序
        models = db.query(Model).order_by(Model.train_time.desc()).all()
        
        # 删除旧版本
        if len(models) > keep_last:
            for model in models[keep_last:]:
                print(f"准备删除旧模型: {model.model_name}")
                
                # 删除S3上的模型文件
                if model.model_path:
                    try:
                        bucket_name = MINIO_CONFIG["buckets"]["models"]
                        object_name = model.model_path.split("/")[-1]
                        minio_client.remove_object(bucket_name, object_name)
                        print(f"✅ 已从S3删除模型文件: {object_name}")
                    except Exception as e:
                        print(f"警告: 从S3删除模型文件失败: {e}")
                
                # 删除关联的缩放器
                if model.scaler_path:
                    try:
                        bucket_name = MINIO_CONFIG["buckets"]["scalers"]
                        object_name = model.scaler_path.split("/")[-1]
                        minio_client.remove_object(bucket_name, object_name)
                        print(f"✅ 已从S3删除缩放器文件: {object_name}")
                    except Exception as e:
                        print(f"警告: 从S3删除缩放器文件失败: {e}")
                
                # 删除关联的指标
                if model.metrics_path:
                    try:
                        bucket_name = MINIO_CONFIG["buckets"]["metrics"]
                        object_name = model.metrics_path.split("/")[-1]
                        minio_client.remove_object(bucket_name, object_name)
                        print(f"✅ 已从S3删除指标文件: {object_name}")
                    except Exception as e:
                        print(f"警告: 从S3删除指标文件失败: {e}")
                
                # 删除数据库中的记录
                db.delete(model)
            
            db.commit()
            print(f"✅ 成功清理旧模型，保留最新的{keep_last}个")
    except Exception as e:
        print(f"警告: 清理旧模型失败: {e}")
        db.rollback()
