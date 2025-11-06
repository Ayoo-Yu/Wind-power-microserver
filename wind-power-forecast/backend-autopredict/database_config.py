from config import KINGBASE_CONFIG, MINIO_CONFIG, set_bucket_policy
from db_models import Base
from sqlalchemy.orm import sessionmaker

import kingbase_dialect  # noqa: F401

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

SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URI


def _create_engine():
    engine_options = {
        "pool_size": 5,
        "max_overflow": 15,
        "echo_pool": True,
    }
    return create_engine_with_retry(SQLALCHEMY_DATABASE_URI, engine_options=engine_options)


try:
    engine = _create_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as exc:
    print(f"警告: 数据库引擎创建失败: {exc}")
    print("应用将继续启动，但数据库功能可能不可用")
    engine = None
    SessionLocal = None


def cleanup_idle_connections(engine, idle_timeout=120):
    core_cleanup_idle_connections(engine, strategy="invalidate", idle_timeout=idle_timeout)


ensure_database_schema(engine, Base)


try:
    minio_client = init_minio_client(MINIO_CONFIG)
    ensure_minio_buckets(
        minio_client,
        MINIO_CONFIG.get("buckets"),
        MINIO_CONFIG.get("policies"),
        set_bucket_policy,
    )
except Exception as exc:
    print(f"警告: MinIO初始化失败: {exc}")
    print("应用将继续启动，但MinIO功能可能不可用")
    minio_client = None


def _ensure_minio_client():
    if minio_client is not None:
        return minio_client
    try:
        return init_minio_client(MINIO_CONFIG)
    except Exception as exc:
        print(f"[ERROR] 无法获取 MinIO 客户端: {exc}")
        return None


def get_db():
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


def cleanup_old_models(keep_last=5):
    client = _ensure_minio_client()
    if not client:
        return

    bucket = MINIO_CONFIG["buckets"].get("models")
    if not bucket:
        print("[WARN] 未配置模型存储桶，跳过清理")
        return

    try:
        objects = [obj for obj in client.list_objects(bucket) if obj.object_name.endswith(".pkl")]
        objects.sort(key=lambda x: x.last_modified, reverse=True)

        for obj in objects[keep_last:]:
            try:
                client.remove_object(bucket, obj.object_name)
                print(f"[OK] 删除模型文件: {obj.object_name}")
            except Exception as exc:
                print(f"[ERROR] 删除模型文件失败 {obj.object_name}: {exc}")
    except Exception as exc:
        print(f"[ERROR] 清理模型文件失败: {exc}")


def cleanup_old_scalers(keep_last=5):
    client = _ensure_minio_client()
    if not client:
        return

    bucket = MINIO_CONFIG["buckets"].get("scalers")
    if not bucket:
        print("[WARN] 未配置scaler存储桶，跳过清理")
        return

    try:
        objects = [obj for obj in client.list_objects(bucket) if obj.object_name.endswith(".pkl")]
        objects.sort(key=lambda x: x.last_modified, reverse=True)

        for obj in objects[keep_last:]:
            try:
                client.remove_object(bucket, obj.object_name)
                print(f"[OK] 删除scaler文件: {obj.object_name}")
            except Exception as exc:
                print(f"[ERROR] 删除scaler文件失败 {obj.object_name}: {exc}")
    except Exception as exc:
        print(f"[ERROR] 清理scaler文件失败: {exc}")


def cleanup_old_metrics(keep_last=5):
    client = _ensure_minio_client()
    if not client:
        return

    bucket = MINIO_CONFIG["buckets"].get("metrics")
    if not bucket:
        print("[WARN] 未配置metrics存储桶，跳过清理")
        return

    try:
        objects = [obj for obj in client.list_objects(bucket) if obj.object_name.endswith(".json")]
        objects.sort(key=lambda x: x.last_modified, reverse=True)

        for obj in objects[keep_last:]:
            try:
                client.remove_object(bucket, obj.object_name)
                print(f"[OK] 删除metrics文件: {obj.object_name}")
            except Exception as exc:
                print(f"[ERROR] 删除metrics文件失败 {obj.object_name}: {exc}")
    except Exception as exc:
        print(f"[ERROR] 清理metrics文件失败: {exc}")


def setup_minio_buckets(client):
    ensure_minio_buckets(
        client,
        MINIO_CONFIG.get("buckets"),
        MINIO_CONFIG.get("policies"),
        set_bucket_policy,
    )
