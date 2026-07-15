from services.capability_service import build_capability_manifest


def _by_id(manifest):
    return {item["id"]: item for item in manifest["capabilities"]}


def test_capability_manifest_exposes_unavailable_placeholders():
    manifest = build_capability_manifest({"DEPLOYMENT_MODE": "development"})
    capabilities = _by_id(manifest)

    assert capabilities["forecasting"]["availability"] == "available"
    assert capabilities["extreme_weather"]["availability"] == "unavailable"
    assert capabilities["extreme_weather"]["maturity"] == "placeholder"
    assert manifest["counts"]["unavailable"] == 2


def test_capability_manifest_reflects_deployment_flags():
    manifest = build_capability_manifest(
        {
            "DEPLOYMENT_MODE": "field",
            "INTEGRATION_API_ENABLED": True,
            "SCADA_REALTIME_ENABLED": True,
            "NWP_INGESTION_ENABLED": True,
            "EXTREME_WEATHER_LIVE_ENABLED": True,
            "PHYSICAL_SIMULATION_ENABLED": True,
        }
    )
    capabilities = _by_id(manifest)

    assert manifest["deployment_mode"] == "field"
    assert capabilities["integration_ingest"]["availability"] == "available"
    assert capabilities["extreme_weather"]["maturity"] == "placeholder"
    assert manifest["counts"]["unavailable"] == 1
