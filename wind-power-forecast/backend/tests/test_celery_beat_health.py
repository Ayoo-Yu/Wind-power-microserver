import json
from datetime import datetime, timedelta, timezone

from services import celery_beat_health


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttl = {}

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttl[key] = ttl

    def get(self, key):
        return self.values.get(key)


def test_beat_heartbeat_reports_fresh_scheduler():
    client = FakeRedis()
    now = datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)

    celery_beat_health.publish_beat_heartbeat(client, schedule_count=12, now=now)
    health = celery_beat_health.read_beat_heartbeat(
        client,
        now=now + timedelta(seconds=5),
    )

    assert client.ttl[celery_beat_health.HEARTBEAT_KEY] == celery_beat_health.HEARTBEAT_TTL_SECONDS
    assert health["status"] == "healthy"
    assert health["healthy"] is True
    assert health["schedule_count"] == 12
    assert health["age_seconds"] == 5.0


def test_beat_heartbeat_does_not_treat_missing_or_stale_state_as_running():
    client = FakeRedis()
    missing = celery_beat_health.read_beat_heartbeat(client)
    assert missing["status"] == "missing"
    assert missing["healthy"] is False

    observed = datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)
    client.values[celery_beat_health.HEARTBEAT_KEY] = json.dumps({
        "observed_at": observed.isoformat(),
        "schedule_count": 5,
    })
    stale = celery_beat_health.read_beat_heartbeat(
        client,
        now=observed + timedelta(seconds=celery_beat_health.HEARTBEAT_TTL_SECONDS + 1),
    )

    assert stale["status"] == "stale"
    assert stale["healthy"] is False
