from services import database_governance_service as governance_service


def test_table_classification_distinguishes_governed_families():
    managed = {"users"}

    assert governance_service.classify_table("users", managed) == "managed"
    assert governance_service.classify_table("ecmwf_grid_cf", managed) == "nwp_parent"
    assert governance_service.classify_table("ecmwf_grid_cf_p202607", managed) == "nwp_partition"
    assert governance_service.classify_table("custom_runtime_table", managed) == "unmanaged"


def test_recommendations_report_nwp_indexes_and_scada_growth(monkeypatch):
    monkeypatch.setenv("NWP_INGESTION_ENABLED", "false")
    migration = {"ready": True}
    tables = [
        {"category": "nwp_partition", "empty_estimate": True},
    ]
    duplicate_indexes = [{"table_name": "users"}]
    scada_growth = {"projected_30d_rows": 1_500_000}

    recommendations = governance_service._recommendations(
        migration,
        tables,
        duplicate_indexes,
        scada_growth,
    )

    titles = [item["title"] for item in recommendations]
    assert any("NWP" in title for title in titles)
    assert any("重复索引" in title for title in titles)
    assert any("SCADA" in title for title in titles)
