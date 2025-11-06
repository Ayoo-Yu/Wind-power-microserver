"""数据库引擎与对象存储的公共构建工具。"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

try:  # 可选依赖，只有在需要对象存储时才要求存在
    from minio import Minio
except Exception:  # pragma: no cover
    Minio = None  # type: ignore


def build_database_uri(kingbase_config: Mapping[str, Any], dialect: str = "postgresql+kingbase") -> str:
    """根据配置字典构建 SQLAlchemy 数据库 URI。"""

    user = kingbase_config.get("user")
    password = kingbase_config.get("password")
    host = kingbase_config.get("host")
    port = kingbase_config.get("port")
    database = kingbase_config.get("database")

    return f"{dialect}://{user}:{password}@{host}:{port}/{database}"


def _attach_pool_events(engine: Engine) -> None:
    """为连接池附加 checkout/checkin 事件，增强连接可用性追踪。"""

    @event.listens_for(engine, "checkout")
    def ping_connection(dbapi_connection, connection_record, connection_proxy):  # type: ignore[override]
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SELECT 1")
        except Exception:
            connection_proxy._pool.dispose()
            raise
        finally:
            cursor.close()

    @event.listens_for(engine, "checkin")
    def mark_last_use(dbapi_connection, connection_record):  # type: ignore[override]
        connection_record.info["last_use_time"] = time.time()


def create_engine_with_retry(
    database_uri: str,
    *,
    engine_options: Optional[Dict[str, Any]] = None,
    max_retries: int = 5,
    retry_delay: int = 5,
    attach_events: bool = True,
) -> Engine:
    """按照指定的重试策略创建 SQLAlchemy 引擎。"""

    default_options: Dict[str, Any] = {
        "poolclass": QueuePool,
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 30,
        "pool_use_lifo": True,
    }
    if engine_options:
        default_options.update(engine_options)

    for attempt in range(max_retries):
        try:
            engine = create_engine(database_uri, **default_options)
            if attach_events:
                _attach_pool_events(engine)
            return engine
        except Exception as exc:
            print(f"创建数据库引擎失败 (尝试 {attempt + 1}/{max_retries}): {exc}")
            if attempt == max_retries - 1:
                raise
            print(f"等待 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)

    # 理论上不会触发
    raise RuntimeError("无法创建数据库引擎")


def cleanup_idle_connections(
    engine: Optional[Engine],
    *,
    strategy: str = "dispose",
    idle_timeout: int = 120,
    min_checked_in: int = 5,
) -> None:
    """根据策略清理空闲连接。"""

    if engine is None:
        return

    try:
        pool = engine.pool

        if strategy == "dispose" and hasattr(pool, "dispose"):
            checked_in = getattr(pool, "checkedin", lambda: 0)()
            if checked_in > min_checked_in:
                print("检测到过多空闲连接，进行部分清理...")
                pool.dispose()
                print("✅ 已清理空闲连接")

        elif strategy == "invalidate":
            for connection in getattr(pool, "_pool", []):
                info = getattr(connection, "info", {})
                last_use = info.get("last_use_time")
                if last_use and time.time() - last_use > idle_timeout:
                    connection.invalidate()

    except Exception as exc:
        print(f"清理空闲连接时发生错误: {exc}")


def ensure_database_schema(engine: Optional[Engine], base) -> None:
    """确保关键数据表已经创建。"""

    if engine is None:
        print("警告: 数据库引擎不可用，跳过迁移检查")
        return

    try:
        inspector = inspect(engine)
        if not inspector.has_table("models"):
            base.metadata.create_all(engine)
            print("✅ 已自动创建缺失的数据库表")
    except Exception as exc:
        print(f"警告: 迁移检查失败: {exc}")


def _resolve_minio_endpoint(config: Mapping[str, Any]) -> str:
    host = config.get("endpoint") or config.get("endpoint_host") or config.get("host")
    port = config.get("port") or config.get("endpoint_port")

    if host and port:
        return f"{host}:{port}"
    return str(host)


def init_minio_client(
    minio_config: Mapping[str, Any],
    *,
    max_retries: int = 5,
    retry_delay: int = 5,
) -> Optional[Minio]:
    """按配置初始化 MinIO 客户端，并验证连接。"""

    if Minio is None:
        raise RuntimeError("minio 库未安装，无法初始化 MinIO 客户端")

    endpoint = _resolve_minio_endpoint(minio_config)
    access_key = minio_config.get("access_key")
    secret_key = minio_config.get("secret_key")
    secure = bool(minio_config.get("secure"))

    for attempt in range(max_retries):
        try:
            client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
            client.list_buckets()
            print("✅ MinIO 连接成功")
            return client
        except Exception as exc:
            print(f"MinIO 连接失败 (尝试 {attempt + 1}/{max_retries}): {exc}")
            if attempt == max_retries - 1:
                raise
            print(f"等待 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)

    return None


def ensure_minio_buckets(
    minio_client: Optional[Minio],
    buckets: Optional[Mapping[str, str]],
    policies: Optional[Mapping[str, Any]] = None,
    policy_setter: Optional[Callable[[Minio, str, Any], None]] = None,
    bucket_key_transform: Optional[Callable[[str], str]] = None,
) -> None:
    """确保存储桶存在并设置策略。"""

    if minio_client is None or not buckets:
        return

    existing = {b.name for b in minio_client.list_buckets()}

    for bucket_name in buckets.values():
        if bucket_name not in existing:
            minio_client.make_bucket(bucket_name)
            print(f"✅ 成功创建存储桶: {bucket_name}")
        else:
            print(f"✅ 存储桶已存在: {bucket_name}")

    if not policies or not policy_setter:
        return

    for policy_key, policy_value in policies.items():
        bucket_key = policy_key
        if bucket_key_transform:
            bucket_key = bucket_key_transform(policy_key)

        target_bucket = buckets.get(bucket_key)
        if not target_bucket:
            continue

        try:
            policy_setter(minio_client, target_bucket, policy_value)
            print(f"✅ 成功设置存储桶策略: {target_bucket} -> {policy_value}")
        except Exception as exc:
            print(f"警告: 设置存储桶策略失败 ({target_bucket}): {exc}")


