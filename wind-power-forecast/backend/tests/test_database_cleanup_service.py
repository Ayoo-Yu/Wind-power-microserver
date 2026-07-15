from services import database_cleanup_service as cleanup_service


def test_cleanup_plan_blocks_when_nwp_ingestion_is_enabled(monkeypatch):
    monkeypatch.setenv("NWP_INGESTION_ENABLED", "true")
    monkeypatch.setattr(
        cleanup_service,
        "_load_nwp_tables",
        lambda connection: [
            {
                "table_name": "ecmwf_grid_cf",
                "is_partition": False,
                "has_data": False,
                "total_size_bytes": 8192,
            }
        ],
    )

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class _Engine:
        def connect(self):
            return _Connection()

    plan = cleanup_service.plan_empty_nwp_cleanup(_Engine())

    assert plan["allowed"] is False
    assert plan["nwp_ingestion_enabled"] is True


def test_cleanup_plan_accepts_only_fully_empty_dynamic_family(monkeypatch):
    monkeypatch.setenv("NWP_INGESTION_ENABLED", "false")
    monkeypatch.setattr(
        cleanup_service,
        "_load_nwp_tables",
        lambda connection: [
            {
                "table_name": "ecmwf_grid_cf_p202607",
                "is_partition": True,
                "has_data": False,
                "total_size_bytes": 8192,
            },
            {
                "table_name": "ecmwf_grid_cf",
                "is_partition": False,
                "has_data": False,
                "total_size_bytes": 8192,
            },
        ],
    )

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class _Engine:
        def connect(self):
            return _Connection()

    plan = cleanup_service.plan_empty_nwp_cleanup(_Engine())

    assert plan["allowed"] is True
    assert plan["table_count"] == 2
    assert plan["partition_count"] == 1
