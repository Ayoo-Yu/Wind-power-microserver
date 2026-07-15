from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.data_lineage import (
    IngestionBatch,
    PredictionInputSnapshot,
    SourceObservation,
)
from db_models.model_version import ModelVersion
from services.prediction_lineage_service import capture_prediction_input_snapshot
from services.scada_contract import REQUIRED_SCADA_METRICS, SCADA_METRICS


def _session():
    engine = create_engine("sqlite:///:memory:")
    for table in (
        IngestionBatch.__table__,
        SourceObservation.__table__,
        PredictionInputSnapshot.__table__,
        ModelVersion.__table__,
    ):
        table.create(engine)
    return sessionmaker(bind=engine)(), engine


def test_prediction_snapshot_freezes_complete_source_and_model_lineage():
    session, engine = _session()
    now = datetime(2026, 7, 15, 10, 0)
    try:
        for index, metric in enumerate(REQUIRED_SCADA_METRICS):
            session.add(SourceObservation(
                observation_key=f"{index:064x}",
                source_type="scada",
                source_id="scada.connection.1",
                farm_code="CF",
                metric=metric,
                event_time=now - timedelta(seconds=20),
                received_at=now - timedelta(seconds=10),
                value=10.0,
                unit=SCADA_METRICS[metric]["unit"],
                quality="good",
                schema_version="scada-point-v2",
            ))
        session.add(IngestionBatch(
            message_id="nwp-CF-1",
            source_type="nwp",
            source_id="zone3.nwp",
            farm_code="CF",
            schema_version="1.0",
            event_time=now - timedelta(minutes=5),
            received_at=now - timedelta(minutes=4),
            completed_at=now - timedelta(minutes=3),
            status="completed",
            quality_status="good",
            record_count=384,
            accepted_count=384,
            rejected_count=0,
            payload_sha256="a" * 64,
            payload_filename="nwp.csv",
        ))
        session.add(ModelVersion(
            farm_code="CF",
            task_type="short",
            algorithm="lightgbm",
            val_accuracy=0.9,
            is_active=True,
            lifecycle_status="approved",
            artifact_sha256="b" * 64,
            feature_contract_version="short-mid-grid-v1",
        ))
        session.flush()

        snapshot = capture_prediction_input_snapshot(
            session,
            prediction_run_id=101,
            farm_code="CF",
            task_type="short",
            now=now,
        )

        assert snapshot.status == "ready"
        assert snapshot.missing_rate == 0
        assert snapshot.scada_observation_count == len(REQUIRED_SCADA_METRICS)
        assert snapshot.nwp_record_count == 384
        assert snapshot.model_version_id is not None
        assert snapshot.input_manifest["nwp"]["message_id"] == "nwp-CF-1"
        assert len(snapshot.dataset_version) == 64
        assert len(snapshot.manifest_sha256) == 64
        assert capture_prediction_input_snapshot(
            session,
            prediction_run_id=101,
            farm_code="CF",
            task_type="short",
            now=now,
        ).id == snapshot.id
    finally:
        session.close()
        engine.dispose()

def test_prediction_snapshot_marks_missing_inputs_and_model_as_blocked():
    session, engine = _session()
    try:
        snapshot = capture_prediction_input_snapshot(
            session,
            prediction_run_id=102,
            farm_code="CF",
            task_type="short",
            now=datetime(2026, 7, 15, 10, 0),
        )
        assert snapshot.status == "blocked"
        assert snapshot.missing_rate == 1.0
        assert snapshot.quality_summary["nwp_fresh"] is False
        assert snapshot.quality_summary["model_approved"] is False
    finally:
        session.close()
        engine.dispose()
