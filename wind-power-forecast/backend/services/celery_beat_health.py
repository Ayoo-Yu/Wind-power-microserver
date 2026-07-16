import json
import os
from datetime import datetime, timezone


HEARTBEAT_KEY = os.environ.get(
    "CELERY_BEAT_HEARTBEAT_KEY",
    "windpower:celery-beat:heartbeat",
)
HEARTBEAT_INTERVAL_SECONDS = max(
    5,
    int(os.environ.get("CELERY_BEAT_HEARTBEAT_INTERVAL_SEC", "10")),
)
HEARTBEAT_TTL_SECONDS = max(
    30,
    int(os.environ.get("CELERY_BEAT_HEARTBEAT_TTL_SEC", "45")),
)


def publish_beat_heartbeat(client, *, schedule_count=0, now=None):
    """写入带过期时间的 Celery Beat 心跳。"""

    current = now or datetime.now(timezone.utc)
    payload = {
        "observed_at": current.isoformat(),
        "schedule_count": int(schedule_count or 0),
        "pid": os.getpid(),
    }
    client.setex(
        HEARTBEAT_KEY,
        HEARTBEAT_TTL_SECONDS,
        json.dumps(payload, ensure_ascii=False),
    )
    return payload


def read_beat_heartbeat(client, *, now=None):
    """读取心跳并将缺失、损坏和陈旧状态显式区分。"""

    raw = client.get(HEARTBEAT_KEY)
    if raw is None:
        return {
            "status": "missing",
            "healthy": False,
            "observed_at": None,
            "age_seconds": None,
            "schedule_count": None,
        }

    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        payload = json.loads(raw)
        observed_at = datetime.fromisoformat(str(payload["observed_at"]))
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        age_seconds = max(0.0, (current - observed_at.astimezone(timezone.utc)).total_seconds())
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {
            "status": "invalid",
            "healthy": False,
            "observed_at": None,
            "age_seconds": None,
            "schedule_count": None,
        }

    healthy = age_seconds <= HEARTBEAT_TTL_SECONDS
    return {
        "status": "healthy" if healthy else "stale",
        "healthy": healthy,
        "observed_at": observed_at.isoformat(),
        "age_seconds": round(age_seconds, 3),
        "schedule_count": int(payload.get("schedule_count") or 0),
    }


def get_beat_health(redis_url=None):
    """通过短超时 Redis 连接读取 Beat 心跳。"""

    import redis

    target_url = redis_url or os.environ.get(
        "CELERY_RESULT_BACKEND",
        os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    )
    try:
        client = redis.Redis.from_url(
            target_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return read_beat_heartbeat(client)
    except Exception:
        return {
            "status": "unavailable",
            "healthy": False,
            "observed_at": None,
            "age_seconds": None,
            "schedule_count": None,
        }
