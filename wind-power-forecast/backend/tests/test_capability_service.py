from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models import IngestionBatch, WindFarm
from services.capability_service import (
    build_capability_manifest,
    build_nwp_runtime_snapshot,
)


def _by_id(manifest):
    return {item["id"]: item for item in manifest["capabilities"]}


def test_capability_manifest_exposes_unavailable_placeholders():
    manifest = build_capability_manifest({"DEPLOYMENT_MODE": "development"})
    capabilities = _by_id(manifest)

    assert capabilities["forecasting"]["availability"] == "available"
    assert capabilities["extreme_weather"]["availability"] == "unavailable"
    assert capabilities["extreme_weather"]["maturity"] == "placeholder"
    assert manifest["counts"]["unavailable"] == 1


def test_capability_manifest_reflects_deployment_flags():
    manifest = build_capability_manifest(
        {
            "DEPLOYMENT_MODE": "field",
            "INTEGRATION_API_ENABLED": True,
            "SCADA_REALTIME_ENABLED": True,
            "NWP_INGESTION_ENABLED": True,
            "EXTREME_WEATHER_LIVE_ENABLED": True,
        }
    )
    capabilities = _by_id(manifest)

    assert manifest["deployment_mode"] == "field"
    assert capabilities["integration_ingest"]["availability"] == "available"
    assert capabilities["extreme_weather"]["maturity"] == "placeholder"
    assert manifest["counts"]["unavailable"] == 1


def test_capability_manifest_uses_scada_runtime_health():
    runtime = {
        "scada": {
            "availability": "degraded",
            "reason": "4/5 个数据源健康",
            "connections": [],
        }
    }
    manifest = build_capability_manifest(
        {
            "SCADA_REALTIME_ENABLED": True,
            "SCADA_REQUIRED": True,
        },
        runtime,
    )
    capability = _by_id(manifest)["scada_realtime"]

    assert capability["availability"] == "degraded"
    assert capability["attention_required"] is True
    assert capability["runtime"] == runtime["scada"]
    assert manifest["counts"]["degraded"] == 1


def test_optional_placeholders_do_not_request_banner_attention():
    manifest = build_capability_manifest({"DEPLOYMENT_MODE": "development"})
    capabilities = _by_id(manifest)

    assert capabilities["integration_ingest"]["attention_required"] is False
    assert capabilities["nwp_ingestion"]["attention_required"] is False
    assert capabilities["extreme_weather"]["attention_required"] is False


def test_capability_manifest_uses_nwp_runtime_health():
    runtime = {
        "nwp": {
            "availability": "degraded",
            "reason": "1 个场站数据过期",
            "farms": [],
        }
    }
    manifest = build_capability_manifest(
        {
            "NWP_INGESTION_ENABLED": True,
            "NWP_INGESTION_REQUIRED": True,
        },
        runtime,
    )
    capability = _by_id(manifest)["nwp_ingestion"]

    assert capability["availability"] == "degraded"
    assert capability["reason"] == "1 个场站数据过期"
    assert capability["attention_required"] is True


def test_nwp_runtime_requires_fresh_batch_for_every_active_farm():
    engine = create_engine("sqlite:///:memory:")
    WindFarm.__table__.create(engine)
    IngestionBatch.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    now = datetime(2026, 7, 15, 6, 0, 0)
    session.add_all([
        WindFarm(farm_code="WF001", farm_name="一号场站", is_active=True),
        WindFarm(farm_code="WF002", farm_name="二号场站", is_active=True),
        IngestionBatch(
            message_id="nwp-WF001",
            source_type="nwp",
            source_id="zone2.nwp",
            farm_code="WF001",
            schema_version="nwp-grid-v1",
            event_time=now - timedelta(minutes=10),
            received_at=now - timedelta(minutes=5),
            completed_at=now - timedelta(minutes=4),
            status="completed",
            quality_status="good",
            record_count=100,
            accepted_count=100,
            rejected_count=0,
            payload_sha256="a" * 64,
            payload_filename="WF001.csv",
        ),
    ])
    session.commit()

    snapshot = build_nwp_runtime_snapshot(
        session,
        {"NWP_DATA_STALE_AFTER_SECONDS": 21600},
        now=now,
    )

    assert snapshot["availability"] == "unavailable"
    assert snapshot["missing_farms"] == ["WF002"]
