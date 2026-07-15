from services import partition_maintenance_service as partition_service


class _ConnectionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Engine:
    def begin(self):
        return _ConnectionContext()


def test_disabled_nwp_does_not_create_ecmwf_tables(monkeypatch):
    monkeypatch.setattr(partition_service, "engine", _Engine())
    monkeypatch.setattr(partition_service, "FARM_MONTH_TABLES", [])
    monkeypatch.setattr(partition_service, "NWP_INGESTION_ENABLED", False)
    monkeypatch.setattr(partition_service, "_active_farm_codes", lambda connection: ["CF"])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("NWP 关闭时不应创建 ECMWF 表")

    monkeypatch.setattr(partition_service, "ensure_ecmwf_grid_table", fail_if_called)

    result = partition_service.ensure_future_partitions(months_ahead=2)

    assert result["nwp_ingestion_enabled"] is False
    assert result["tables"] == []
