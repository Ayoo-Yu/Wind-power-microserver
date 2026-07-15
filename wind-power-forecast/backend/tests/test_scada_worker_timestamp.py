from datetime import datetime, timedelta, timezone

import pytest

from services.scada_worker import (
    BEIJING_TZ,
    point_quality_label,
    round_to_quarter_hour,
    select_sample_timestamp,
    submit_sample,
)


def test_default_timestamp_policy_preserves_quarter_window():
    now = datetime(2026, 7, 15, 10, 14, tzinfo=BEIJING_TZ)
    assert select_sample_timestamp(now, {}) == round_to_quarter_hour(now)


def test_receive_time_policy_keeps_sample_time():
    now = datetime(2026, 7, 15, 10, 7, 23, tzinfo=BEIJING_TZ)
    selected = select_sample_timestamp(now, {"timestamp_policy": "receive_time"})
    assert selected == datetime(2026, 7, 15, 10, 7, 23)


def test_source_time_policy_prefers_protocol_timestamp():
    received = datetime(2026, 7, 15, 10, 7, tzinfo=BEIJING_TZ)
    source = datetime(2026, 7, 15, 2, 6, tzinfo=timezone.utc)
    selected = select_sample_timestamp(
        received,
        {"timestamp_policy": "source_time"},
        source,
    )
    assert selected == datetime(2026, 7, 15, 10, 6)


def test_floor_quarter_policy_is_suitable_for_continuous_local_simulation():
    now = datetime(2026, 7, 15, 10, 7, 23, tzinfo=BEIJING_TZ)
    selected = select_sample_timestamp(now, {"timestamp_policy": "floor_quarter"})
    assert selected == datetime(2026, 7, 15, 10, 0)


def test_unknown_timestamp_policy_is_rejected():
    with pytest.raises(ValueError, match="timestamp_policy"):
        select_sample_timestamp(
            datetime.now(timezone(timedelta(hours=8))),
            {"timestamp_policy": "unknown"},
        )


def test_point_quality_is_normalized():
    class Quality:
        def __init__(self, good):
            self.good = good

        def is_good(self):
            return self.good

    class Point:
        def __init__(self, good):
            self.quality = Quality(good)

    assert point_quality_label(Point(True)) == "good"
    assert point_quality_label(Point(False)) == "bad"


def test_sample_submission_only_falls_back_for_old_backend(monkeypatch):
    calls = []

    def fake_post_json(url, payload, headers=None):
        calls.append((url, payload, headers))
        return 404, {"error": "endpoint_not_found"}

    monkeypatch.setattr("services.scada_worker._post_json", fake_post_json)
    monkeypatch.setattr("services.scada_worker.post_power", lambda *args: 201)

    status, result = submit_sample(
        {
            "connection_id": 1,
            "farm_code": "CF",
            "backend_url": "http://backend",
        },
        power=12.5,
        normalized_timestamp=datetime(2026, 7, 15, 10, 0),
        source_timestamp=None,
        ioa=16385,
        quality="good",
    )

    assert status == 201
    assert result["outcome"] == "legacy_actual_power"
    assert calls[0][0].endswith("/api/v1/scada/ingest")
