from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models import (
    IngestionBatch,
    ModelVersion,
    PredictionInputSnapshot,
    PredictionRun,
    PredictionTask,
    ReportOutbox,
    ScadaConnection,
    SourceObservation,
)
from services import operations_overview_service as overview_service
from services.operations_overview_service import build_operations_overview
from services.scada_contract import REQUIRED_SCADA_METRICS, SCADA_METRICS


def _session():
    engine = create_engine("sqlite:///:memory:")
    tables = [
        ScadaConnection.__table__,
        SourceObservation.__table__,
        IngestionBatch.__table__,
        PredictionTask.__table__,
        PredictionRun.__table__,
        PredictionInputSnapshot.__table__,
        ReportOutbox.__table__,
        ModelVersion.__table__,
    ]
    for table in tables:
        table.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _seed_healthy_state(session, now):
    session.add(ScadaConnection(
        farm_code="WF001",
        name="一号场站",
        protocol="c104",
        server_ip="10.20.0.10",
        is_enabled=True,
        status="running",
        last_data_at=now,
        point_catalog_version="scada-point-v2",
    ))
    for sequence, metric in enumerate(REQUIRED_SCADA_METRICS, start=1):
        session.add(SourceObservation(
            observation_key=f"obs-{sequence:02d}".ljust(64, "0"),
            source_type="scada",
            source_id="c104:10.20.0.10",
            farm_code="WF001",
            metric=metric,
            event_time=now - timedelta(seconds=30),
            received_at=now - timedelta(seconds=20),
            value=90.0 if metric == "availability_pct" else 12.5,
            unit=SCADA_METRICS[metric]["unit"],
            quality="good",
            schema_version="scada-point-v2",
        ))
    session.add(IngestionBatch(
        message_id="nwp-WF001-001",
        source_type="nwp",
        source_id="simulation-nwp",
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
    ))
    task = PredictionTask(farm_code="WF001", task_type="supershort", enabled=True)
    session.add(task)
    session.flush()
    run = PredictionRun(
        task_id=task.id,
        action="predict",
        status="success",
        started_at=now - timedelta(minutes=2),
        finished_at=now - timedelta(minutes=1),
        duration_sec=60,
        created_at=now - timedelta(minutes=2),
    )
    session.add(run)
    session.flush()
    model = ModelVersion(
        farm_code="WF001",
        task_type="supershort",
        algorithm="xgboost",
        val_accuracy=0.91,
        is_active=True,
        local_path="models/WF001.bin",
        dataset_version="b" * 64,
        artifact_sha256="c" * 64,
        lifecycle_status="approved",
        trained_at=now - timedelta(days=1),
    )
    session.add(model)
    session.flush()
    session.add(PredictionInputSnapshot(
        prediction_run_id=run.id,
        farm_code="WF001",
        task_type="supershort",
        captured_at=now - timedelta(minutes=2),
        contract_version="prediction-input-v1",
        dataset_version="d" * 64,
        model_version_id=model.id,
        scada_observation_count=5,
        nwp_record_count=100,
        missing_rate=0.0,
        status="ready",
        quality_summary={"state": "good"},
        input_manifest={"scada": [], "nwp": {}},
        manifest_sha256="e" * 64,
    ))
    session.add(ReportOutbox(
        idempotency_key="report-WF001-001",
        config_id=1,
        farm_code="WF001",
        report_type="supershort",
        target_url="http://10.30.0.20/report",
        payload_json="{}",
        payload_sha256="f" * 64,
        status="sent",
        created_at=now - timedelta(minutes=1),
        updated_at=now,
    ))
    session.commit()


def test_overview_reports_healthy_closed_loop(tmp_path, monkeypatch):
    now = datetime(2026, 7, 15, 4, 0, 0)
    session = _session()
    _seed_healthy_state(session, now)
    monkeypatch.setattr(
        overview_service.shutil,
        "disk_usage",
        lambda _: overview_service.shutil._ntuple_diskusage(1000, 500, 500),
    )

    result = build_operations_overview(
        session,
        now=now,
        farm_code="WF001",
        scada_enabled=True,
        scada_required=True,
        nwp_enabled=True,
        nwp_required=True,
        storage_path=str(tmp_path),
    )

    assert result["overall"]["state"] == "healthy"
    assert result["scada"]["state"] == "healthy"
    assert result["scada"]["missing_metric_count"] == 0
    assert result["nwp"]["state"] == "healthy"
    assert result["prediction"]["status_counts"] == {"success": 1}
    assert result["reporting"]["dead_count"] == 0
    assert result["models"]["active_count"] == 1
    assert result["prediction"]["latest_input_snapshots"][0]["status"] == "ready"


def test_required_stale_inputs_and_dead_letter_are_critical(tmp_path, monkeypatch):
    now = datetime(2026, 7, 15, 4, 0, 0)
    session = _session()
    _seed_healthy_state(session, now)
    monkeypatch.setattr(
        overview_service.shutil,
        "disk_usage",
        lambda _: overview_service.shutil._ntuple_diskusage(1000, 500, 500),
    )
    session.add(ReportOutbox(
        idempotency_key="report-WF001-dead",
        config_id=1,
        farm_code="WF001",
        report_type="supershort",
        target_url="http://10.30.0.20/report",
        payload_json="{}",
        payload_sha256="1" * 64,
        status="dead",
        last_error="目标服务器不可达",
        created_at=now,
        updated_at=now,
    ))
    session.commit()

    result = build_operations_overview(
        session,
        now=now + timedelta(hours=7),
        farm_code="WF001",
        scada_enabled=True,
        scada_required=True,
        scada_stale_after_seconds=1200,
        nwp_enabled=True,
        nwp_required=True,
        nwp_stale_after_seconds=21600,
        storage_path=str(tmp_path),
    )

    assert result["overall"]["state"] == "critical"
    assert result["scada"]["state"] == "stale"
    assert result["nwp"]["state"] == "stale"
    assert result["reporting"]["dead_count"] == 1
    assert {issue["domain"] for issue in result["overall"]["issues"]} >= {
        "scada",
        "nwp",
        "reporting",
    }
