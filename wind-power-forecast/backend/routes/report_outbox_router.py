"""可靠上报队列运维接口。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from db_models import ReportOutbox
from db_session import db_session
from utils.authorization import permission_required
from services.report_outbox_service import retry_dead_letter


report_outbox_bp = Blueprint(
    "report_outbox",
    __name__,
    url_prefix="/api/v1/report-outbox",
)


def _serialize(row: ReportOutbox, *, include_payload: bool = False) -> dict:
    result = {
        "id": row.id,
        "idempotency_key": row.idempotency_key,
        "config_id": row.config_id,
        "farm_code": row.farm_code,
        "report_type": row.report_type,
        "target_url": row.target_url,
        "payload_sha256": row.payload_sha256,
        "data_count": row.data_count,
        "data_completeness_rate": row.data_completeness_rate,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "max_attempts": row.max_attempts,
        "next_attempt_at": row.next_attempt_at.isoformat() if row.next_attempt_at else None,
        "locked_at": row.locked_at.isoformat() if row.locked_at else None,
        "last_response_code": row.last_response_code,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
    }
    if include_payload:
        result["payload"] = json.loads(row.payload_json)
        result["last_response_body"] = row.last_response_body
    return result


@report_outbox_bp.get("/summary")
@jwt_required()
@permission_required("manage_reports")
def outbox_summary():
    with db_session() as session:
        counts = dict(
            session.query(ReportOutbox.status, func.count(ReportOutbox.id))
            .group_by(ReportOutbox.status)
            .all()
        )
        oldest = (
            session.query(ReportOutbox)
            .filter(ReportOutbox.status.in_(("pending", "retry", "processing")))
            .order_by(ReportOutbox.created_at)
            .first()
        )
        lag_seconds = None
        if oldest and oldest.created_at:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            lag_seconds = max(0, int((now - oldest.created_at).total_seconds()))
        return jsonify(
            {
                "status": "ok",
                "counts": {
                    name: int(counts.get(name, 0))
                    for name in ("pending", "processing", "retry", "sent", "dead")
                },
                "oldest_active_age_seconds": lag_seconds,
            }
        )


@report_outbox_bp.get("/items")
@jwt_required()
@permission_required("manage_reports")
def list_outbox_items():
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))
    offset = max(0, request.args.get("offset", 0, type=int))
    with db_session() as session:
        query = session.query(ReportOutbox)
        status = request.args.get("status")
        farm_code = request.args.get("farm_code")
        report_type = request.args.get("report_type")
        if status:
            query = query.filter(ReportOutbox.status == status)
        if farm_code:
            query = query.filter(ReportOutbox.farm_code == farm_code)
        if report_type:
            query = query.filter(ReportOutbox.report_type == report_type)
        total = query.count()
        rows = query.order_by(ReportOutbox.created_at.desc()).offset(offset).limit(limit).all()
        return jsonify(
            {
                "status": "ok",
                "total": total,
                "items": [_serialize(row) for row in rows],
            }
        )


@report_outbox_bp.get("/items/<int:outbox_id>")
@jwt_required()
@permission_required("manage_reports")
def get_outbox_item(outbox_id: int):
    with db_session() as session:
        row = session.query(ReportOutbox).filter_by(id=outbox_id).first()
        if not row:
            return jsonify({"status": "error", "message": "上报任务不存在"}), 404
        return jsonify({"status": "ok", "item": _serialize(row, include_payload=True)})


@report_outbox_bp.post("/items/<int:outbox_id>/retry")
@jwt_required()
@permission_required("manage_reports")
def retry_outbox_item(outbox_id: int):
    with db_session() as session:
        if not retry_dead_letter(session, outbox_id):
            return jsonify(
                {"status": "error", "message": "仅可重新投递死信任务"}
            ), 409
        return jsonify({"status": "ok", "message": "任务已重新进入重试队列"})
