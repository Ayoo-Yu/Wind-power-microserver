"""冻结预测运行实际可见的数据来源、质量和模型版本。"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta

from db_models.data_lineage import (
    IngestionBatch,
    PredictionInputSnapshot,
    SourceObservation,
)
from db_models.model_version import ModelVersion
from services.scada_contract import REQUIRED_SCADA_METRICS


PREDICTION_INPUT_CONTRACT_VERSION = "prediction-input-v1"


def _canonical_hash(value: dict) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _latest_observations(session, farm_code: str) -> dict[str, SourceObservation | None]:
    result = {}
    for metric in REQUIRED_SCADA_METRICS:
        result[metric] = (
            session.query(SourceObservation)
            .filter(
                SourceObservation.farm_code == farm_code,
                SourceObservation.metric == metric,
                SourceObservation.quality == "good",
            )
            .order_by(
                SourceObservation.event_time.desc(),
                SourceObservation.id.desc(),
            )
            .first()
        )
    return result


def _active_model(session, farm_code: str, task_type: str) -> ModelVersion | None:
    return (
        session.query(ModelVersion)
        .filter(
            ModelVersion.farm_code == farm_code,
            ModelVersion.task_type == task_type,
            ModelVersion.is_active.is_(True),
            ModelVersion.lifecycle_status == "approved",
        )
        .order_by(ModelVersion.val_accuracy.desc(), ModelVersion.trained_at.desc())
        .first()
    )


def capture_prediction_input_snapshot(
    session,
    *,
    prediction_run_id: int,
    farm_code: str,
    task_type: str,
    now: datetime | None = None,
    scada_stale_after_seconds: int | None = None,
    nwp_stale_after_seconds: int | None = None,
) -> PredictionInputSnapshot:
    """为一次预测运行创建不可变输入快照，重复调用返回同一记录。"""

    existing = session.query(PredictionInputSnapshot).filter(
        PredictionInputSnapshot.prediction_run_id == prediction_run_id
    ).first()
    if existing is not None:
        return existing

    captured_at = now or datetime.now()
    scada_stale_after_seconds = int(
        scada_stale_after_seconds
        if scada_stale_after_seconds is not None
        else os.environ.get("SCADA_DATA_STALE_AFTER_SECONDS", "1200")
    )
    nwp_stale_after_seconds = int(
        nwp_stale_after_seconds
        if nwp_stale_after_seconds is not None
        else os.environ.get("NWP_DATA_STALE_AFTER_SECONDS", "21600")
    )

    observations = _latest_observations(session, farm_code)
    scada_manifest = {}
    available_scada = 0
    timeline = []
    for metric, observation in observations.items():
        fresh = bool(
            observation is not None
            and observation.received_at is not None
            and observation.received_at
            >= captured_at - timedelta(seconds=scada_stale_after_seconds)
        )
        if fresh:
            available_scada += 1
            timeline.append(observation.event_time)
        scada_manifest[metric] = {
            "observation_id": observation.id if observation else None,
            "event_time": observation.event_time.isoformat() if observation else None,
            "received_at": observation.received_at.isoformat() if observation else None,
            "quality": observation.quality if observation else "missing",
            "fresh": fresh,
        }

    nwp_batch = (
        session.query(IngestionBatch)
        .filter(
            IngestionBatch.farm_code == farm_code,
            IngestionBatch.source_type == "nwp",
            IngestionBatch.status == "completed",
        )
        .order_by(IngestionBatch.event_time.desc(), IngestionBatch.id.desc())
        .first()
    )
    nwp_fresh = bool(
        nwp_batch is not None
        and nwp_batch.completed_at is not None
        and nwp_batch.completed_at
        >= captured_at - timedelta(seconds=nwp_stale_after_seconds)
        and nwp_batch.accepted_count > 0
    )
    if nwp_fresh:
        timeline.append(nwp_batch.event_time)

    model = _active_model(session, farm_code, task_type)
    required_count = len(REQUIRED_SCADA_METRICS) + 1
    available_count = available_scada + int(nwp_fresh)
    missing_rate = round((required_count - available_count) / required_count, 6)
    if model is None:
        status = "blocked"
    elif missing_rate == 0:
        status = "ready"
    else:
        status = "degraded"

    source_identity = {
        "contract_version": PREDICTION_INPUT_CONTRACT_VERSION,
        "farm_code": farm_code,
        "task_type": task_type,
        "scada": scada_manifest,
        "nwp": {
            "batch_id": nwp_batch.id if nwp_batch else None,
            "message_id": nwp_batch.message_id if nwp_batch else None,
            "event_time": nwp_batch.event_time.isoformat() if nwp_batch else None,
            "payload_sha256": nwp_batch.payload_sha256 if nwp_batch else None,
            "record_count": nwp_batch.accepted_count if nwp_batch else 0,
            "quality": nwp_batch.quality_status if nwp_batch else "missing",
            "fresh": nwp_fresh,
        },
        "model": {
            "version_id": model.id if model else None,
            "artifact_sha256": model.artifact_sha256 if model else None,
            "feature_contract_version": (
                model.feature_contract_version if model else None
            ),
        },
    }
    dataset_version = _canonical_hash(source_identity)
    input_manifest = {
        **source_identity,
        "prediction_run_id": prediction_run_id,
        "captured_at": captured_at.isoformat(),
        "status": status,
        "missing_rate": missing_rate,
    }
    manifest_sha256 = _canonical_hash(input_manifest)
    snapshot = PredictionInputSnapshot(
        prediction_run_id=prediction_run_id,
        farm_code=farm_code,
        task_type=task_type,
        captured_at=captured_at,
        contract_version=PREDICTION_INPUT_CONTRACT_VERSION,
        dataset_version=dataset_version,
        model_version_id=model.id if model else None,
        data_start=min(timeline) if timeline else None,
        data_end=max(timeline) if timeline else None,
        scada_observation_count=available_scada,
        nwp_record_count=nwp_batch.accepted_count if nwp_batch else 0,
        missing_rate=missing_rate,
        status=status,
        quality_summary={
            "required_scada_metrics": len(REQUIRED_SCADA_METRICS),
            "fresh_scada_metrics": available_scada,
            "nwp_fresh": nwp_fresh,
            "model_approved": model is not None,
        },
        input_manifest=input_manifest,
        manifest_sha256=manifest_sha256,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def snapshot_to_dict(snapshot: PredictionInputSnapshot) -> dict:
    return {
        "id": snapshot.id,
        "prediction_run_id": snapshot.prediction_run_id,
        "farm_code": snapshot.farm_code,
        "task_type": snapshot.task_type,
        "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
        "contract_version": snapshot.contract_version,
        "dataset_version": snapshot.dataset_version,
        "model_version_id": snapshot.model_version_id,
        "data_start": snapshot.data_start.isoformat() if snapshot.data_start else None,
        "data_end": snapshot.data_end.isoformat() if snapshot.data_end else None,
        "scada_observation_count": snapshot.scada_observation_count,
        "nwp_record_count": snapshot.nwp_record_count,
        "missing_rate": snapshot.missing_rate,
        "status": snapshot.status,
        "quality_summary": snapshot.quality_summary,
        "input_manifest": snapshot.input_manifest,
        "manifest_sha256": snapshot.manifest_sha256,
    }
