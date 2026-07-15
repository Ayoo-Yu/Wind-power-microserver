from services.capability_service import build_capability_manifest


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
