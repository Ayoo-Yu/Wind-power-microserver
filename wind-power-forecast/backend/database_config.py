from config import KINGBASE_CONFIG, MINIO_CONFIG, set_bucket_policy
from db_models import Base, Model
from sqlalchemy.orm import Session, sessionmaker

import kingbase_dialect  # noqa: F401  确保方言注册

from windpower_core.database import (
    build_database_uri,
    cleanup_idle_connections as core_cleanup_idle_connections,
    create_engine_with_retry,
    ensure_database_schema,
    ensure_minio_buckets,
    init_minio_client,
)


print("构建数据库连接URL...")
SQLALCHEMY_DATABASE_URI = build_database_uri(KINGBASE_CONFIG)
print(f"最终连接URL：{SQLALCHEMY_DATABASE_URI}")

# 保留旧变量名以保持兼容性
SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URI


def _create_engine():
    engine_options = {
        "pool_size": 10,
        "max_overflow": 10,
        "echo_pool": True,
    }

    return create_engine_with_retry(
        SQLALCHEMY_DATABASE_URI,
        engine_options=engine_options,
    )


try:
    engine = _create_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as exc:
    print(f"警告: 数据库引擎创建失败: {exc}")
    print("应用将继续启动，但数据库功能可能不可用")
    engine = None
    SessionLocal = None


def cleanup_idle_connections(engine):  # 向后兼容旧函数名
    core_cleanup_idle_connections(engine, strategy="dispose", idle_timeout=120, min_checked_in=5)


ensure_database_schema(engine, Base)


try:
    minio_client = init_minio_client(MINIO_CONFIG)
    ensure_minio_buckets(
        minio_client,
        MINIO_CONFIG.get("buckets"),
        MINIO_CONFIG.get("policies"),
        set_bucket_policy,
        bucket_key_transform=lambda key: key.replace("wind-", ""),
    )
except Exception as exc:
    print(f"警告: MinIO初始化失败: {exc}")
    print("应用将继续启动，但MinIO功能可能不可用")
    minio_client = None


def get_db():
    """获取数据库会话，并确保在使用后正确关闭"""

    print("调试: get_db函数被调用")
    if SessionLocal is None:
        print("警告: 数据库会话不可用")
        raise Exception("数据库连接不可用")

    if engine:
        cleanup_idle_connections(engine)

    print(f"调试: 创建数据库会话，引擎连接URL为: {SQLALCHEMY_DATABASE_URI}")
    db = SessionLocal()
    try:
        yield db
    finally:
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
