import json
import logging
import os
import ipaddress

from flask import Blueprint, request, jsonify, current_app
from db_session import db_session
from db_models.scada_connection import ScadaConnection
from db_models.report_config import WindFarm
from db_models.power import ActualPower
from datetime import datetime
from services.scada_health_service import build_scada_health_snapshot
from services.scada_ingest_service import ScadaIngestError, ingest_scada_sample

logger = logging.getLogger(__name__)

scada_connection_bp = Blueprint('scada_connection', __name__)

WORKER_SECRET = os.environ.get('SCADA_WORKER_SECRET', '')
ALLOWED_PROTOCOLS = ('c104', 'http_poll')
ALLOWED_WORKER_STATUSES = {'stopped', 'running', 'error', 'connecting'}


def _parse_ioa_points(raw):
    """Safely parse ioa_points JSON."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _connection_to_dict(conn: ScadaConnection, health: dict | None = None) -> dict:
    result = {
        'id': conn.id,
        'farm_code': conn.farm_code,
        'name': conn.name,
        'protocol': conn.protocol or 'c104',
        'server_ip': conn.server_ip,
        'server_port': conn.server_port,
        'casdu_address': conn.casdu_address,
        'originator_address': conn.originator_address,
        'ioa_points': _parse_ioa_points(conn.ioa_points),
        'upload_target_ioa': conn.upload_target_ioa,
        'fetch_interval': conn.fetch_interval,
        'poll_url': conn.poll_url,
        'is_enabled': conn.is_enabled,
        'status': conn.status,
        'status_message': conn.status_message,
        'last_data_at': conn.last_data_at.isoformat() if conn.last_data_at else None,
        'last_power_value': conn.last_power_value,
        'last_error': conn.last_error,
        'created_at': conn.created_at.isoformat() if conn.created_at else None,
        'updated_at': conn.updated_at.isoformat() if conn.updated_at else None,
    }
    if health is not None:
        result['health'] = health
    return result


def _validate_connection_data(data: dict) -> tuple[dict | None, str | None]:
    if not data.get('farm_code'):
        return None, 'farm_code is required'
    if not data.get('name'):
        return None, 'name is required'
    if not data.get('server_ip'):
        return None, 'server_ip is required'

    protocol = data.get('protocol', 'c104')
    if protocol not in ALLOWED_PROTOCOLS:
        return None, f'protocol must be one of {ALLOWED_PROTOCOLS}'

    server_port = data.get('server_port', 2404)
    try:
        server_port = int(server_port)
        if not (1 <= server_port <= 65535):
            return None, 'server_port must be between 1 and 65535'
    except (ValueError, TypeError):
        return None, 'server_port must be a valid integer'

    try:
        fetch_interval = int(data.get('fetch_interval', 60))
        if not 1 <= fetch_interval <= 3600:
            return None, 'fetch_interval must be between 1 and 3600 seconds'
    except (ValueError, TypeError):
        return None, 'fetch_interval must be a valid integer'

    return {
        'farm_code': data['farm_code'].strip(),
        'name': data['name'].strip(),
        'protocol': protocol,
        'server_ip': data['server_ip'].strip(),
        'server_port': server_port,
        'casdu_address': int(data.get('casdu_address', 1)),
        'originator_address': int(data.get('originator_address', 0)),
        'ioa_points': data.get('ioa_points', {}),
        'upload_target_ioa': data.get('upload_target_ioa'),
        'fetch_interval': fetch_interval,
        'poll_url': data.get('poll_url'),
        'is_enabled': data.get('is_enabled', True),
    }, None


def _safe_int(value, field_name):
    """Convert value to int with error handling."""
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f'{field_name} must be a valid integer')


@scada_connection_bp.route('/scada/connections', methods=['GET'])
def list_connections():
    with db_session() as db:
        connections = db.query(ScadaConnection).order_by(ScadaConnection.id).all()
        snapshot = build_scada_health_snapshot(db, current_app.config)
        health_by_id = {
            item['connection_id']: item for item in snapshot['connections']
        }
        return jsonify({
            'success': True,
            'data': [
                _connection_to_dict(c, health_by_id.get(c.id)) for c in connections
            ],
            'health_summary': {
                key: snapshot[key]
                for key in ('availability', 'reason', 'generated_at', 'counts')
            },
        })


@scada_connection_bp.route('/scada/connections/<int:conn_id>', methods=['GET'])
def get_connection(conn_id: int):
    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404
        snapshot = build_scada_health_snapshot(db, current_app.config)
        health = next(
            (item for item in snapshot['connections'] if item['connection_id'] == conn_id),
            None,
        )
        return jsonify({'success': True, 'data': _connection_to_dict(conn, health)})


@scada_connection_bp.route('/scada/connections', methods=['POST'])
def create_connection():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400
    if (
        data.get('protocol', 'c104') == 'http_poll'
        and not current_app.config.get('SCADA_ALLOW_SYNTHETIC_HTTP_POLL', False)
    ):
        return jsonify({
            'success': False,
            'error': 'HTTP 轮询模式会生成研发模拟数据，当前部署禁止创建该连接',
        }), 400

    validated, error = _validate_connection_data(data)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    with db_session() as db:
        existing = db.query(ScadaConnection).filter(
            ScadaConnection.farm_code == validated['farm_code']
        ).first()
        if existing:
            return jsonify({'success': False, 'error': f"Connection for farm '{validated['farm_code']}' already exists"}), 409

        conn = ScadaConnection(
            farm_code=validated['farm_code'],
            name=validated['name'],
            protocol=validated['protocol'],
            server_ip=validated['server_ip'],
            server_port=validated['server_port'],
            casdu_address=validated['casdu_address'],
            originator_address=validated['originator_address'],
            ioa_points=json.dumps(validated['ioa_points']) if validated['ioa_points'] else None,
            upload_target_ioa=validated['upload_target_ioa'],
            fetch_interval=validated['fetch_interval'],
            poll_url=validated['poll_url'],
            is_enabled=validated['is_enabled'],
            status='stopped',
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return jsonify({'success': True, 'data': _connection_to_dict(conn)}), 201


@scada_connection_bp.route('/scada/connections/<int:conn_id>', methods=['PUT'])
def update_connection(conn_id: int):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400
    if (
        data.get('protocol') == 'http_poll'
        and not current_app.config.get('SCADA_ALLOW_SYNTHETIC_HTTP_POLL', False)
    ):
        return jsonify({
            'success': False,
            'error': 'HTTP 轮询模式会生成研发模拟数据，当前部署禁止启用该模式',
        }), 400

    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404

        if conn.status in {'running', 'connecting', 'stopping', 'restart_requested'}:
            return jsonify({'success': False, 'error': 'Cannot update a running connection. Stop it first.'}), 409

        try:
            if 'name' in data:
                conn.name = data['name'].strip()
            if 'server_ip' in data:
                conn.server_ip = data['server_ip'].strip()
            if 'server_port' in data:
                conn.server_port = _safe_int(data['server_port'], 'server_port')
                if not (1 <= conn.server_port <= 65535):
                    return jsonify({'success': False, 'error': 'server_port must be 1-65535'}), 400
            if 'casdu_address' in data:
                conn.casdu_address = _safe_int(data['casdu_address'], 'casdu_address')
            if 'originator_address' in data:
                conn.originator_address = _safe_int(data['originator_address'], 'originator_address')
            if 'ioa_points' in data:
                conn.ioa_points = json.dumps(data['ioa_points']) if data['ioa_points'] else None
            if 'upload_target_ioa' in data:
                conn.upload_target_ioa = data['upload_target_ioa']
            if 'fetch_interval' in data:
                conn.fetch_interval = _safe_int(data['fetch_interval'], 'fetch_interval')
            if 'poll_url' in data:
                conn.poll_url = data['poll_url']
            if 'is_enabled' in data:
                conn.is_enabled = bool(data['is_enabled'])
            if 'protocol' in data:
                if data['protocol'] not in ALLOWED_PROTOCOLS:
                    return jsonify({'success': False, 'error': f'protocol must be one of {ALLOWED_PROTOCOLS}'}), 400
                conn.protocol = data['protocol']
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        conn.updated_at = datetime.now()
        db.commit()
        db.refresh(conn)
        return jsonify({'success': True, 'data': _connection_to_dict(conn)})


@scada_connection_bp.route('/scada/connections/<int:conn_id>', methods=['DELETE'])
def delete_connection(conn_id: int):
    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404

        if conn.status in {'running', 'connecting', 'stopping', 'restart_requested'}:
            return jsonify({'success': False, 'error': 'Cannot delete a running connection. Stop it first.'}), 409

        db.delete(conn)
        db.commit()
        return jsonify({'success': True, 'message': 'Connection deleted'})


@scada_connection_bp.route('/scada/connections/<int:conn_id>/start', methods=['POST'])
def start_connection(conn_id: int):
    if not current_app.config.get('SCADA_REALTIME_ENABLED', False):
        return jsonify({
            'success': False,
            'error': '当前部署未启用 SCADA 实时接入，请先设置 SCADA_REALTIME_ENABLED',
        }), 409

    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404
        if (
            conn.protocol == 'http_poll'
            and not current_app.config.get('SCADA_ALLOW_SYNTHETIC_HTTP_POLL', False)
        ):
            return jsonify({
                'success': False,
                'error': '当前部署禁止启动会生成模拟数据的 HTTP 轮询连接',
            }), 409
        if conn.status in {'running', 'connecting', 'stopping', 'restart_requested'}:
            return jsonify({'success': False, 'error': 'Connection is already running'}), 409
        conn.is_enabled = True
        conn.status = 'connecting'
        conn.status_message = 'Start requested, waiting for SCADA manager reconciliation'
        conn.updated_at = datetime.now()
        db.commit()
    return jsonify({'success': True, 'message': 'Connection start requested'}), 202


@scada_connection_bp.route('/scada/connections/<int:conn_id>/stop', methods=['POST'])
def stop_connection(conn_id: int):
    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404
        conn.is_enabled = False
        conn.status = 'stopping'
        conn.status_message = 'Stop requested, waiting for SCADA manager reconciliation'
        conn.updated_at = datetime.now()
        db.commit()
    return jsonify({'success': True, 'message': 'Connection stop requested'}), 202


@scada_connection_bp.route('/scada/connections/<int:conn_id>/restart', methods=['POST'])
def restart_connection(conn_id: int):
    if not current_app.config.get('SCADA_REALTIME_ENABLED', False):
        return jsonify({
            'success': False,
            'error': '当前部署未启用 SCADA 实时接入',
        }), 409
    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404
        conn.is_enabled = True
        conn.status = 'restart_requested'
        conn.status_message = 'Restart requested, waiting for SCADA manager reconciliation'
        conn.updated_at = datetime.now()
        db.commit()
    return jsonify({'success': True, 'message': 'Connection restart requested'}), 202


@scada_connection_bp.route('/scada/connections/<int:conn_id>/test', methods=['POST'])
def test_connection(conn_id: int):
    import socket

    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404

        ip, port = conn.server_ip, conn.server_port

    # Block cloud metadata endpoint
    try:
        ip_obj = ipaddress.ip_address(ip)
        if str(ip_obj) == '169.254.169.254':
            return jsonify({'success': False, 'error': 'Address not allowed'}), 400
    except ValueError:
        pass  # hostname, not IP - allow it

    try:
        sock = socket.create_connection((ip, port), timeout=5)
        sock.close()
        return jsonify({'success': True, 'message': f'Connection to {ip}:{port} successful'})
    except socket.timeout:
        return jsonify({'success': False, 'error': f'Connection to {ip}:{port} timed out'}), 504
    except ConnectionRefusedError:
        return jsonify({'success': False, 'error': f'Connection to {ip}:{port} refused'}), 502
    except Exception as e:
        return jsonify({'success': False, 'error': f'Connection test failed: {str(e)}'}), 502


@scada_connection_bp.route('/scada/connections/<int:conn_id>/data', methods=['GET'])
def get_connection_data(conn_id: int):
    limit = request.args.get('limit', 20, type=int)

    with db_session() as db:
        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
        if not conn:
            return jsonify({'success': False, 'error': 'Connection not found'}), 404

        records = db.query(ActualPower).filter(
            ActualPower.farm_code == conn.farm_code
        ).order_by(ActualPower.timestamp.desc()).limit(limit).all()

        data = [{
            'timestamp': r.timestamp.isoformat() if r.timestamp else None,
            'wp_true': r.wp_true,
            'farm_code': r.farm_code,
        } for r in records]

        return jsonify({'success': True, 'data': data})


def _verify_worker_secret():
    """Validate the worker-to-manager shared secret."""
    expected = current_app.config.get('SCADA_WORKER_SECRET', '') or WORKER_SECRET
    if not expected:
        return True  # No secret configured, skip check
    provided = request.headers.get('X-Worker-Secret', '')
    return provided == expected


@scada_connection_bp.route('/scada/worker-status', methods=['POST'])
def worker_status():
    """Internal endpoint for worker subprocesses to report their status."""
    if not _verify_worker_secret():
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    if not data or 'connection_id' not in data:
        return jsonify({'error': 'connection_id required'}), 400

    try:
        from services.scada_manager import get_scada_manager
        manager = get_scada_manager()
        worker_state = data.get('status', 'unknown')
        if worker_state not in ALLOWED_WORKER_STATUSES:
            return jsonify({'error': 'invalid worker status'}), 400
        manager.update_worker_status(
            conn_id=data['connection_id'],
            status=worker_state,
            message=data.get('status_message', ''),
            power_value=data.get('last_power_value'),
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Failed to process worker status: {e}")
        return jsonify({'error': str(e)}), 500


@scada_connection_bp.route('/api/v1/scada/ingest', methods=['POST'])
def ingest_sample():
    """接收 Worker 样本，并在一个事务中完成审计、质检和实际功率落库。"""
    if not current_app.config.get('SCADA_REALTIME_ENABLED', False):
        return jsonify({
            'accepted': False,
            'error': 'SCADA 实时接入未启用',
        }), 503
    if not _verify_worker_secret():
        return jsonify({'accepted': False, 'error': 'Unauthorized'}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'accepted': False, 'error': '请求体必须是 JSON 对象'}), 400

    try:
        with db_session() as db:
            result = ingest_scada_sample(db, payload, current_app.config)
            response = result.to_dict()
            status_code = 201 if result.outcome == 'created' else 200
            if not result.accepted:
                status_code = 422
            return jsonify(response), status_code
    except ScadaIngestError as exc:
        return jsonify({'accepted': False, 'error': str(exc)}), exc.status_code
    except Exception as exc:
        logger.exception('SCADA 样本处理失败')
        return jsonify({'accepted': False, 'error': 'SCADA 样本处理失败'}), 500


@scada_connection_bp.route('/api/v1/scada/health', methods=['GET'])
def scada_health():
    """返回采集、预测和实际上报的运行态闭环状态。"""
    try:
        with db_session() as db:
            return jsonify(build_scada_health_snapshot(db, current_app.config))
    except Exception as exc:
        logger.exception('SCADA 健康状态查询失败')
        return jsonify({
            'availability': 'unavailable',
            'reason': 'SCADA 健康状态查询失败',
            'error': str(exc),
            'connections': [],
        }), 503


@scada_connection_bp.route('/scada/connections/farms', methods=['GET'])
def available_farms():
    """Get farms that don't yet have a SCADA connection configured."""
    with db_session() as db:
        farms = db.query(WindFarm).filter(WindFarm.is_active.is_(True)).all()
        existing_codes = {c.farm_code for c in db.query(ScadaConnection).all()}
        result = []
        for f in farms:
            result.append({
                'farm_code': f.farm_code,
                'farm_name': f.farm_name,
                'capacity': f.capacity,
                'has_connection': f.farm_code in existing_codes,
            })
        return jsonify({'success': True, 'data': result})
