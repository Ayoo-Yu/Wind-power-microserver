"""Autopredict blueprint -- Celery-based, no PM2 dependencies.

Status is read from the ``prediction_tasks`` database table instead of
polling PM2 process state.  All deprecated PM2-management endpoints
return 410 Gone so that older frontends get a clear signal.
"""

import json
import datetime
import glob
import os
import uuid
import threading
import logging
import traceback

from flask import Blueprint, request, jsonify, current_app, g
from sqlalchemy import text as _text, desc, func, case as db_case
from datetime import datetime as _dt
import re as _re

from flask_jwt_extended import get_jwt_identity, jwt_required

from database_config import Base, get_db
from db_session import db_session
from db_models import TaskHistory, PredictionTask, PredictionRun
from config import Config
from routes.auth import permission_required

# ---------------------------------------------------------------------------
# Sub-module imports (extracted helpers)
# ---------------------------------------------------------------------------
from routes._farm_helpers import (  # noqa: F401
    active_farm_codes_cache,
    active_farms_cache,
    normalize_farm_code,
    canonicalize_farm_code,
    get_active_farm_codes,
    get_active_farms,
    is_valid_farm_code,
    resolve_farm_code,
)
from routes._prediction_helpers import (  # noqa: F401
    action_lock,
    inflight_actions,
    build_action_key,
    try_acquire_action_lock,
    release_action_lock,
    record_task_history,
)

logger = logging.getLogger(__name__)

_TIME_PATTERN = _re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')

# Prediction types that the system recognises.
_VALID_PREDICTION_TYPES = ('short', 'medium', 'supershort')


def _get_celery_tasks():
    """Lazy import to avoid requiring celery when Flask starts without workers."""
    from celery_app.tasks import train_model, run_prediction, run_supershort_predict
    return train_model, run_prediction, run_supershort_predict


# ---------------------------------------------------------------------------
# Script / log directory setup (mirrors original layout)
# ---------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))

if os.path.exists('/app'):
    base_dir = '/app'
else:
    base_dir = os.path.abspath(os.path.join(current_dir, '../..'))

scripts = {
    'short': Config.SCRIPT_PATHS.get('short'),
    'medium': Config.SCRIPT_PATHS.get('medium'),
    'supershort': Config.SCRIPT_PATHS.get('supershort') or Config.SCRIPT_PATHS.get('supershort_train'),
}

# Check scripts exist and log.
for name, path in scripts.items():
    if path and os.path.exists(path):
        logger.info("Script found: %s -> %s", name, path)
    else:
        logger.info("Script not found: %s -> %s", name, path)
        possible_locations = [
            os.path.join(base_dir, 'auto_scripts', 'scripts', name, f'scheduler_{name}.py'),
            os.path.join(base_dir, 'scripts', name, f'scheduler_{name}.py'),
            os.path.join(base_dir, 'scripts', f'scheduler_{name}.py'),
        ]
        for loc in possible_locations:
            if os.path.exists(loc):
                logger.info("Found alternative script: %s", loc)
                scripts[name] = loc
                break

log_dirs = Config.LOG_DIRS

# Ensure all log directories exist.
for type_dirs in log_dirs.values():
    for dir_path in type_dirs.values():
        os.makedirs(dir_path, exist_ok=True)


# ---------------------------------------------------------------------------
# Utility helpers (kept from original)
# ---------------------------------------------------------------------------

def get_script_name(prediction_type: str) -> str:
    """Return the base name of the script for *prediction_type* (no extension)."""
    script_path = scripts.get(prediction_type, '')
    return os.path.splitext(os.path.basename(script_path))[0]


def build_process_name(farm_code: str, prediction_type: str) -> str:
    """Build a human-readable identifier for a farm/prediction-type pair."""
    return f"{farm_code}_{get_script_name(prediction_type)}"


def api_success(data=None, message="ok", status_code=200, legacy=None):
    payload = {
        "code": 0,
        "message": message,
        "data": data,
    }
    if isinstance(legacy, dict):
        payload.update(legacy)
    return jsonify(payload), status_code


def api_error(message, code=1500, status_code=400, details=None, legacy=None):
    payload = {
        "code": code,
        "message": message,
        "data": None,
        "error": message,
    }
    if details is not None:
        payload["details"] = details
    if isinstance(legacy, dict):
        payload.update(legacy)
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
autopredict_bp = Blueprint('autopredict', __name__)


# ---------------------------------------------------------------------------
# Farms
# ---------------------------------------------------------------------------

@autopredict_bp.route('/farms', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/farms', methods=['GET'])
def get_autopredict_farms():
    farms = get_active_farms()
    return api_success(data=farms, message='获取场站列表成功', legacy=farms)


# ---------------------------------------------------------------------------
# Status -- DB-backed, no PM2
# ---------------------------------------------------------------------------

def _task_to_status_dict(task: PredictionTask) -> dict:
    """Serialise a PredictionTask row into the status dict expected by the API."""
    return {
        'enabled': task.enabled,
        'train_status': task.last_train_status,
        'predict_status': task.last_predict_status,
        'last_train_at': task.last_train_at.isoformat() if task.last_train_at else None,
        'last_predict_at': task.last_predict_at.isoformat() if task.last_predict_at else None,
        'last_error': task.last_error,
    }


def _check_model_status(farm_code: str, task_type: str) -> dict:
    """Check whether model and calibrator files exist on disk for a given farm/type.

    Returns dict with model_exists, model_date, calib_exists, calib_date.
    Note: DB stores 'medium' but filesystem uses 'mid' (same mapping as forecast_service).
    """
    from services.model_manager import ModelManager
    from services.calibration_manager import CalibrationManager

    # Map task_type to the directory name used on disk
    forecast_type = 'mid' if task_type == 'medium' else task_type

    result = {
        'model_exists': False,
        'model_date': None,
        'calib_exists': False,
        'calib_date': None,
    }

    try:
        if task_type == 'supershort':
            from services.ultrashort_model_manager import UltrashortModelManager
            usmm = UltrashortModelManager()
            meta = usmm.load_meta(farm_code)
            if meta:
                result['model_exists'] = True
                result['model_date'] = meta.get('train_date')
            model_dir = usmm._base(farm_code)
            if os.path.isdir(model_dir):
                meta_path = os.path.join(model_dir, 'meta.json')
                if os.path.exists(meta_path) and not result['model_date']:
                    result['model_date'] = datetime.datetime.fromtimestamp(
                        os.path.getmtime(meta_path)
                    ).strftime('%Y-%m-%d %H:%M')
        else:
            mm = ModelManager()
            loaded = mm.load(farm_code, forecast_type)
            if loaded:
                result['model_exists'] = True
                meta = loaded.get('meta', {})
                result['model_date'] = meta.get('train_date')
            model_dir = mm._dir(farm_code, forecast_type)
            if os.path.isdir(model_dir) and not result['model_date']:
                meta_path = os.path.join(model_dir, 'meta.json')
                if os.path.exists(meta_path):
                    result['model_date'] = datetime.datetime.fromtimestamp(
                        os.path.getmtime(meta_path)
                    ).strftime('%Y-%m-%d %H:%M')

        calib = CalibrationManager()
        if task_type == 'supershort':
            calib_data = calib.load_shifts(farm_code)
            if calib_data:
                result['calib_exists'] = True
                # Get the latest last_updated from any shift
                dates = [v.get('last_updated', '') for v in calib_data.values()]
                result['calib_date'] = max(dates) if dates else None
        else:
            calib_data = calib.load(farm_code, forecast_type)
            if calib_data:
                result['calib_exists'] = True
                result['calib_date'] = calib_data.get('last_updated')
    except Exception:
        pass

    return result


@autopredict_bp.route('/status', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/status', methods=['GET'])
def get_status():
    """Return prediction task status for a single farm, read from DB."""
    try:
        raw_farm_code = request.args.get('farm_code')
        farm_code = resolve_farm_code(raw_farm_code)
        prediction_type = request.args.get('type')

        with db_session() as session:
            query = session.query(PredictionTask).filter_by(farm_code=farm_code)
            if prediction_type:
                query = query.filter_by(task_type=prediction_type)
            tasks = query.all()

            current_status = {}
            for t in tasks:
                current_status[t.task_type] = _task_to_status_dict(t)

        # If a specific type was requested, return just that type.
        if prediction_type:
            if prediction_type in current_status:
                legacy_data = {
                    prediction_type: current_status[prediction_type],
                    'farm_code': farm_code,
                }
                return api_success(data=legacy_data, message="ok", legacy=legacy_data)
            else:
                return api_error('无效的预测类型', code=1001, status_code=400)

        current_status['farm_code'] = farm_code
        return api_success(data=current_status, message="ok", legacy=current_status)
    except Exception as e:
        error_msg = f"获取状态时出错: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        logger.error(error_msg)
        return api_error('获取状态时出错', code=1500, status_code=500, details=error_msg)


@autopredict_bp.route('/status_all', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/status_all', methods=['GET'])
def get_status_all():
    """Return prediction task status for all farms."""
    try:
        with db_session() as session:
            tasks = session.query(PredictionTask).all()

            farm_map = {}
            for t in tasks:
                if t.farm_code not in farm_map:
                    farm_map[t.farm_code] = {
                        "farm_code": t.farm_code,
                        "farm_name": _get_farm_name(session, t.farm_code),
                        "status": {},
                    }
                farm_map[t.farm_code]["status"][t.task_type] = _task_to_status_dict(t)

            items = list(farm_map.values())
            return api_success(data={"items": items, "count": len(items)})
    except Exception as e:
        return api_error(f"获取多场站状态失败: {str(e)}")


def _get_farm_name(session, farm_code: str) -> str:
    row = session.execute(
        _text("SELECT farm_name FROM wind_farms WHERE farm_code = :code"),
        {"code": farm_code},
    ).fetchone()
    return row[0] if row else farm_code


@autopredict_bp.route('/overview', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/overview', methods=['GET'])
def get_fleet_overview():
    """Fleet overview with running task counts, model/calibrator status, and real execution times."""
    try:
        farms = get_active_farms()
        items = []
        with db_session() as session:
            for farm in farms:
                farm_code = farm.get('farm_code')
                farm_name = farm.get('farm_name') or farm_code
                if not farm_code:
                    continue

                tasks = session.query(PredictionTask).filter_by(farm_code=farm_code).all()
                status = {}
                model_info = {}
                running_count = 0
                for t in tasks:
                    status[t.task_type] = _task_to_status_dict(t)
                    if t.enabled:
                        running_count += 1

                    model_info[t.task_type] = _check_model_status(farm_code, t.task_type)

                # Query real last execution time from prediction_runs
                last_runs = {}
                for task_type in ('supershort', 'short', 'medium'):
                    latest = (
                        session.query(PredictionRun)
                        .join(PredictionTask, PredictionRun.task_id == PredictionTask.id)
                        .filter(PredictionTask.farm_code == farm_code)
                        .filter(PredictionTask.task_type == task_type)
                        .filter(PredictionRun.status.in_(['success', 'failed']))
                        .order_by(desc(PredictionRun.finished_at))
                        .first()
                    )
                    if latest:
                        last_runs[task_type] = {
                            'finished_at': latest.finished_at.isoformat() if latest.finished_at else None,
                            'duration_sec': latest.duration_sec,
                            'status': latest.status,
                            'action': latest.action,
                        }

                items.append({
                    'farm_code': farm_code,
                    'farm_name': farm_name,
                    'status': status,
                    'model_info': model_info,
                    'last_runs': last_runs,
                    'running_count': running_count,
                })

        payload = {
            'items': items,
            'count': len(items),
        }
        return api_success(data=payload, message='获取多场站总览成功', legacy=payload)
    except Exception as e:
        error_msg = f"获取多场站总览失败: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        logger.error(error_msg)
        return api_error('获取多场站总览失败', code=1500, status_code=500, details=error_msg)


# ---------------------------------------------------------------------------
# Batch control helpers
# ---------------------------------------------------------------------------

def _execute_batch_items(action, target_farm_codes, target_types):
    """Execute a batch action via the internal Flask test client."""
    results = []
    success_count = 0
    failed_count = 0
    endpoint = f'/api/{action}'
    with current_app.test_client() as client:
        for farm_code in target_farm_codes:
            for prediction_type in target_types:
                resp = client.post(endpoint, json={'type': prediction_type, 'farm_code': farm_code})
                body = resp.get_json(silent=True) or {}
                item_success = 200 <= resp.status_code < 300
                if item_success:
                    success_count += 1
                else:
                    failed_count += 1
                results.append({
                    'farm_code': farm_code,
                    'type': prediction_type,
                    'status_code': resp.status_code,
                    'success': item_success,
                    'code': body.get('code'),
                    'message': body.get('message') or body.get('error') or '',
                })
    return results, success_count, failed_count


@autopredict_bp.route('/control_all', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/control_all', methods=['POST'])
def control_all_prediction():
    """
    Batch-control a single prediction type across multiple farms.

    Request body:
      {"action": "start|stop", "type": "supershort|short|medium",
       "farm_codes": ["farm_a", "farm_b"]}
    """
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    prediction_type = data.get('type')
    farm_codes = data.get('farm_codes')

    if action not in ('start', 'stop'):
        return api_error('无效的操作类型，仅支持 start/stop', code=1001, status_code=400)
    if prediction_type not in _VALID_PREDICTION_TYPES:
        return api_error('无效的预测类型', code=1001, status_code=400)
    if farm_codes and not isinstance(farm_codes, list):
        return api_error('farm_codes 必须是数组', code=1001, status_code=400)
    if isinstance(farm_codes, list) and not all(isinstance(c, str) and c.strip() for c in farm_codes):
        return api_error('farm_codes 包含无效值', code=1001, status_code=400)

    try:
        with db_session() as session:
            query = session.query(PredictionTask).filter_by(task_type=prediction_type)
            if farm_codes and isinstance(farm_codes, list):
                valid_codes = [c.strip() for c in farm_codes]
                query = query.filter(PredictionTask.farm_code.in_(valid_codes))

            tasks = query.all()
            enabled = action == 'start'
            items = []
            for t in tasks:
                t.enabled = enabled
                t.updated_at = _dt.now()
                items.append({
                    "farm_code": t.farm_code,
                    "type": prediction_type,
                    "success": True,
                    "message": f"{prediction_type} {'已启用' if enabled else '已停止'} (场站: {t.farm_code})",
                })

        return api_success(
            data={"items": items, "summary": {"total": len(items), "success": len(items), "failed": 0}},
            message=f"批量{action}完成: 成功 {len(items)}/{len(items)}",
        )
    except Exception as e:
        return api_error(f"批量操作失败: {str(e)}")


@autopredict_bp.route('/control_matrix', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/control_matrix', methods=['POST'])
def control_matrix_prediction():
    """
    Batch-control multiple farms * multiple prediction types (matrix).

    Request body:
      {"action": "start|stop|delete",
       "types": ["supershort", "short", "medium"],
       "farm_codes": ["farm_a", "farm_b"]}
    """
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    raw_types = data.get('types')
    raw_farm_codes = data.get('farm_codes')

    if action not in ('start', 'stop', 'delete'):
        return api_error('无效的批量操作类型', code=1001, status_code=400)

    if not isinstance(raw_types, list):
        return api_error('types 必须是数组', code=1001, status_code=400)

    target_types = []
    for item in raw_types:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned and cleaned in _VALID_PREDICTION_TYPES and cleaned not in target_types:
                target_types.append(cleaned)

    if not target_types:
        return api_error('缺少有效预测类型', code=1001, status_code=400)

    active_farm_codes = get_active_farm_codes()
    if not active_farm_codes:
        return api_error('未找到有效场站，无法执行批量操作', code=1004, status_code=400)

    if raw_farm_codes is None:
        target_farm_codes = active_farm_codes
    elif not isinstance(raw_farm_codes, list):
        return api_error('farm_codes 必须是数组', code=1001, status_code=400)
    else:
        target_farm_codes = []
        for code in raw_farm_codes:
            if isinstance(code, str):
                canonical_code = canonicalize_farm_code(code, active_farm_codes)
                if canonical_code and canonical_code not in target_farm_codes:
                    target_farm_codes.append(canonical_code)

    if not target_farm_codes:
        return api_error('缺少可执行的场站列表', code=1001, status_code=400)

    active_code_lookup = {code.lower(): code for code in active_farm_codes}
    invalid_codes = [code for code in target_farm_codes if code.lower() not in active_code_lookup]
    if invalid_codes:
        return api_error(
            f"无效的场站代码: {', '.join(invalid_codes)}",
            code=1001,
            status_code=400,
        )

    results, success_count, failed_count = _execute_batch_items(
        action=action,
        target_farm_codes=target_farm_codes,
        target_types=target_types,
    )

    total = len(target_farm_codes) * len(target_types)
    summary = {
        'total': total,
        'success': success_count,
        'failed': failed_count,
    }
    payload = {
        'action': action,
        'types': target_types,
        'farm_codes': target_farm_codes,
        'summary': summary,
        'items': results,
    }
    http_status = 200 if failed_count == 0 else 207
    return api_success(
        data=payload,
        message=f"矩阵批量{action}完成: 成功 {success_count}/{total}",
        status_code=http_status,
        legacy=payload,
    )


# ---------------------------------------------------------------------------
# Start / Stop -- DB-backed toggle of PredictionTask.enabled
# ---------------------------------------------------------------------------

@autopredict_bp.route('/start', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/start', methods=['POST'])
def start_prediction():
    data = request.get_json(silent=True) or {}
    prediction_type = data.get('type')
    farm_code = resolve_farm_code(data.get('farm_code') or '')

    if prediction_type not in _VALID_PREDICTION_TYPES:
        return api_error('无效的预测类型', code=1001, status_code=400)

    try:
        with db_session() as session:
            task = session.query(PredictionTask).filter_by(
                farm_code=farm_code, task_type=prediction_type,
            ).first()
            if not task:
                return api_error(f'未找到任务配置: {farm_code} {prediction_type}', code=1004, status_code=404)
            task.enabled = True
            task.updated_at = _dt.now()

        return api_success(
            data={"farm_code": farm_code, "type": prediction_type, "enabled": True},
            message=f'{prediction_type} 预测任务已启用 (场站: {farm_code})',
        )
    except Exception as e:
        return api_error(f"启动失败: {str(e)}")


@autopredict_bp.route('/stop', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/stop', methods=['POST'])
def stop_prediction():
    data = request.get_json(silent=True) or {}
    prediction_type = data.get('type')
    farm_code = resolve_farm_code(data.get('farm_code') or '')

    if prediction_type not in _VALID_PREDICTION_TYPES:
        return api_error('无效的预测类型', code=1001, status_code=400)

    try:
        with db_session() as session:
            task = session.query(PredictionTask).filter_by(
                farm_code=farm_code, task_type=prediction_type,
            ).first()
            if not task:
                return api_error(f'未找到任务配置: {farm_code} {prediction_type}', code=1004, status_code=404)
            task.enabled = False
            task.updated_at = _dt.now()

        return api_success(
            data={"farm_code": farm_code, "type": prediction_type, "enabled": False},
            message=f'{prediction_type} 预测任务已停止 (场站: {farm_code})',
        )
    except Exception as e:
        return api_error(f"停止失败: {str(e)}")


# ---------------------------------------------------------------------------
# Deprecated endpoints (410 Gone)
# ---------------------------------------------------------------------------

@autopredict_bp.route('/schedule', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/schedule', methods=['POST'])
def schedule_restart():
    return api_error('此端点已弃用，任务管理已迁移到 Celery', code=1010, status_code=410)


@autopredict_bp.route('/delete', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/delete', methods=['POST'])
def delete_prediction():
    return api_error('此端点已弃用，任务管理已迁移到 Celery', code=1010, status_code=410)


@autopredict_bp.route('/save', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/save', methods=['POST'])
def save_pm2_config():
    return api_error('此端点已弃用，任务管理已迁移到 Celery', code=1010, status_code=410)


@autopredict_bp.route('/clearsave', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/clearsave', methods=['POST'])
def clear_pm2_save():
    return api_error('此端点已弃用，任务管理已迁移到 Celery', code=1010, status_code=410)


@autopredict_bp.route('/resurrect', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/resurrect', methods=['POST'])
def resurrect():
    return api_error('此端点已弃用，任务管理已迁移到 Celery', code=1010, status_code=410)


# ---------------------------------------------------------------------------
# Script info -- Celery worker status instead of PM2
# ---------------------------------------------------------------------------

@autopredict_bp.route('/script_info', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/script_info', methods=['GET'])
def get_script_info():
    """Return Celery worker / task info for a given prediction type and farm."""
    prediction_type = request.args.get('type')
    raw_farm_code = request.args.get('farm_code')

    if raw_farm_code and not is_valid_farm_code(raw_farm_code):
        return api_error(f'无效的场站代码: {raw_farm_code}', code=1001, status_code=400)
    farm_code = resolve_farm_code(raw_farm_code)

    if not prediction_type or prediction_type not in _VALID_PREDICTION_TYPES:
        return api_error('无效的预测类型', code=1001, status_code=400)

    try:
        process_name = build_process_name(farm_code, prediction_type)
        logger.debug("Querying task info: %s", process_name)

        with db_session() as session:
            task = session.query(PredictionTask).filter_by(
                farm_code=farm_code, task_type=prediction_type,
            ).first()

        if not task:
            record_task_history(prediction_type, 'script_info', 'failed', '任务配置不存在')
            return api_error(
                f'任务 {process_name} 未找到',
                code=1004,
                status_code=404,
                details={'process_name': process_name},
            )

        # Try to get Celery worker status.
        worker_info = _get_celery_worker_status()

        info_lines = [
            f"任务名称: {process_name}",
            f"场站: {farm_code}",
            f"类型: {prediction_type}",
            f"启用: {'是' if task.enabled else '否'}",
            f"最近训练状态: {task.last_train_status or 'N/A'}",
            f"最近预测状态: {task.last_predict_status or 'N/A'}",
            f"最近训练时间: {task.last_train_at.isoformat() if task.last_train_at else 'N/A'}",
            f"最近预测时间: {task.last_predict_at.isoformat() if task.last_predict_at else 'N/A'}",
            f"最近错误: {task.last_error or 'N/A'}",
            f"训练调度: {task.train_schedule or 'N/A'}",
            f"预测调度: {task.predict_schedule or 'N/A'}",
            "",
            "Celery Worker 状态:",
        ]
        for name, status in worker_info.items():
            info_lines.append(f"  {name}: {status}")

        record_task_history(prediction_type, 'script_info', 'success', '查询任务详情成功')
        legacy_data = {
            'info': '\n'.join(info_lines),
            'process_name': process_name,
        }
        return api_success(data=legacy_data, message='查询任务详情成功', legacy=legacy_data)

    except Exception as e:
        error_msg = f"获取脚本详情出错: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        logger.error(error_msg)
        record_task_history(prediction_type, 'script_info', 'failed', error_msg)
        return api_error('查询脚本详情失败', code=1500, status_code=500, details=error_msg)


def _get_celery_worker_status() -> dict:
    """Best-effort query of Celery worker status via inspect."""
    try:
        from celery_app.celery_app import celery_app as app
        inspect = app.control.inspect(timeout=3)
        stats = inspect.stats() or {}
        result = {}
        for name, info in stats.items():
            result[name] = 'online'
        if not result:
            result['no_workers'] = 'no workers responding'
        return result
    except Exception as e:
        logger.debug("Celery inspect failed: %s", e)
        return {'celery': f'unavailable ({e})'}


def _build_db_log_text(prediction_type: str, log_type: str, date_str: str) -> str | None:
    """Build a readable log text from recent PredictionRun records.

    Used as fallback when no log files exist on disk (Celery tasks don't write files).
    """
    action_map = {'train': 'train', 'predict': 'predict', 'main': 'train'}
    action = action_map.get(log_type, 'train')

    with db_session() as session:
        query = (
            session.query(PredictionRun, PredictionTask)
            .join(PredictionTask, PredictionRun.task_id == PredictionTask.id)
            .filter(PredictionTask.task_type == prediction_type)
            .filter(PredictionRun.action == action)
            .order_by(desc(PredictionRun.created_at))
        )
        rows = query.limit(5).all()

        if not rows:
            return None

        lines = [
            f"[数据库执行记录] 预测类型: {prediction_type}  操作: {action}",
            f"查询日期: {date_str}  (最近 {len(rows)} 条记录)",
            "=" * 60,
        ]

        for run, task in rows:
            started = run.started_at.strftime('%Y-%m-%d %H:%M:%S') if run.started_at else '-'
            finished = run.finished_at.strftime('%Y-%m-%d %H:%M:%S') if run.finished_at else '-'
            duration = f"{run.duration_sec}s" if run.duration_sec else '-'
            lines.append("")
            lines.append(f"--- 执行记录 #{run.id} ---")
            lines.append(f"场站: {task.farm_code}  类型: {task.task_type}  操作: {run.action}")
            lines.append(f"状态: {run.status}  耗时: {duration}")
            lines.append(f"开始: {started}  结束: {finished}")

            if run.error_message:
                lines.append(f"错误: {run.error_message}")

            if run.result_json:
                try:
                    result = json.loads(run.result_json)
                    lines.append("")
                    lines.append("执行结果详情:")
                    if result.get('meta'):
                        meta = result['meta']
                        lines.append(f"  训练样本: {meta.get('n_samples', '-')}")
                        lines.append(f"  验证样本: {meta.get('n_val_samples', '-')}")
                        lines.append(f"  测试样本: {meta.get('n_test_samples', '-')}")
                        lines.append(f"  特征数: {meta.get('n_features', '-')}")
                        if meta.get('cal_accuracy'):
                            ca = meta['cal_accuracy']
                            lines.append(f"  准确率: {ca.get('accuracy_percent', 0):.1f}%")
                            lines.append(f"  RMSE: {ca.get('weighted_rmse', 0):.2f}")
                            lines.append(f"  MAE: {ca.get('mae', 0):.2f}")
                            lines.append(f"  R²: {ca.get('r2', 0):.3f}")
                    if result.get('n_rows'):
                        lines.append(f"  数据行数: {result['n_rows']}")
                    if result.get('n_shifts'):
                        lines.append(f"  Shift数: {result['n_shifts']}")
                    if result.get('n_predictions') is not None:
                        lines.append(f"  预测点数: {result['n_predictions']}")
                    if result.get('target_date'):
                        lines.append(f"  目标日期: {result['target_date']}")
                    if result.get('alpha') is not None:
                        lines.append(f"  校准 alpha: {result['alpha']:.4f}")
                        lines.append(f"  校准 beta: {result['beta']:.3f}")
                        lines.append(f"  校准点数: {result.get('n_points', '-')}")
                    if result.get('model_dir'):
                        lines.append(f"  模型路径: {result['model_dir']}")
                    if result.get('calib_dir'):
                        lines.append(f"  参数路径: {result['calib_dir']}")
                except Exception:
                    lines.append(f"  (结果JSON解析失败)")

        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Logs -- file-based, no PM2
# ---------------------------------------------------------------------------

@autopredict_bp.route('/logs', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/logs', methods=['GET'])
def get_logs():
    prediction_type = request.args.get('type')
    log_type = request.args.get('logType', 'train')
    date_str = request.args.get('date', datetime.datetime.now().strftime('%Y%m%d'))
    lines = request.args.get('lines', 500, type=int)

    if not prediction_type or prediction_type not in _VALID_PREDICTION_TYPES:
        return api_error('无效的预测类型', code=1001, status_code=400)

    try:
        # All log types are now file-based (PM2 main log removed).
        if log_type == 'main':
            # Map 'main' to the train log directory as a sensible fallback.
            log_type = 'train'

        log_dir = log_dirs.get(prediction_type, {}).get(log_type)
        if not log_dir:
            return api_error(f'无效的日志类型: {log_type}', code=1001, status_code=400)

        log_files = []
        if prediction_type == 'supershort':
            if log_type == 'train':
                log_files = glob.glob(os.path.join(log_dir, f"{date_str}_train_supershort.log"))
            elif log_type == 'predict':
                log_files = glob.glob(os.path.join(log_dir, f"{date_str}_predict_supershort.log"))
        elif log_type == 'train':
            log_files = glob.glob(os.path.join(log_dir, f"{date_str}*.log"))
        elif log_type == 'predict':
            log_files = glob.glob(os.path.join(log_dir, f"{date_str}*.log"))

        if not log_files:
            # Fallback: query recent PredictionRun result from DB
            db_log = _build_db_log_text(prediction_type, log_type, date_str)
            if db_log:
                record_task_history(prediction_type, 'logs', 'success', f'从数据库获取{log_type}执行记录')
                return api_success(data={'logs': db_log}, message='获取执行记录成功', legacy={'logs': db_log})

            record_task_history(prediction_type, 'logs', 'failed', f'未找到{date_str}的{log_type}类型日志文件')
            log_text = f'未找到{date_str}的{log_type}日志文件，也无对应执行记录'
            return api_success(
                data={'logs': log_text},
                message='日志文件不存在',
                legacy={'logs': log_text},
            )

        latest_log = max(log_files, key=os.path.getmtime)
        try:
            with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                log_content = ''.join(all_lines[-lines:]) if len(all_lines) > lines else ''.join(all_lines)

            file_info = (
                f"文件: {os.path.basename(latest_log)}\n"
                f"日期: {datetime.datetime.fromtimestamp(os.path.getmtime(latest_log)).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            log_content = file_info + log_content

            record_task_history(prediction_type, 'logs', 'success', f'获取{log_type}日志 ({lines} 行)')
            return api_success(data={'logs': log_content}, message='获取日志成功', legacy={'logs': log_content})
        except Exception as e:
            error_msg = f'读取日志文件失败: {str(e)}'
            record_task_history(prediction_type, 'logs', 'failed', error_msg)
            return api_error('读取日志文件失败', code=1500, status_code=500, details=error_msg)
    except Exception as e:
        error_msg = f'获取日志失败: {str(e)}'
        record_task_history(prediction_type, 'logs', 'failed', error_msg)
        return api_error('获取日志失败', code=1500, status_code=500, details=error_msg)


# ---------------------------------------------------------------------------
# Task status (flag-file based -- kept from original, no PM2)
# ---------------------------------------------------------------------------

@autopredict_bp.route('/task_status', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/task_status', methods=['GET'])
def get_task_status():
    prediction_type = request.args.get('type')
    date_str = request.args.get('date', datetime.datetime.now().strftime('%Y%m%d'))
    param_opt_day = request.args.get('param_opt_day', None)
    if param_opt_day is not None:
        param_opt_day = int(param_opt_day)
    else:
        param_opt_day_map = {
            'short': 4,
            'medium': 3,
            'supershort': 6,
        }
        param_opt_day = param_opt_day_map.get(prediction_type, 5)

    if not prediction_type or prediction_type not in _VALID_PREDICTION_TYPES:
        return api_error('无效的预测类型', code=1001, status_code=400)

    status = {
        'training': False,
        'prediction': False,
        'paramOpt': False,
        'trainingTime': '',
        'predictionTime': '',
        'paramOptTime': '',
        'predictionCount': 0,
        'predictionCompleted': False,
    }

    try:
        try:
            selected_date = datetime.datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            return api_error('日期格式无效，请使用YYYYMMDD格式', code=1001, status_code=400)

        is_today = selected_date.date() == datetime.datetime.now().date()

        # --- Training flag ---
        train_flag_path = os.path.join(log_dirs[prediction_type]['train'], f"{date_str}_train_done.flag")
        if os.path.exists(train_flag_path):
            status['training'] = True
            status['trainingTime'] = datetime.datetime.fromtimestamp(
                os.path.getmtime(train_flag_path),
            ).strftime('%Y-%m-%d %H:%M:%S')

        # --- Param optimisation flag ---
        selected_weekday = selected_date.weekday()
        days_diff = 0
        if selected_weekday >= param_opt_day:
            days_diff = selected_weekday - param_opt_day
        else:
            days_diff = selected_weekday + 7 - param_opt_day

        param_opt_date = selected_date - datetime.timedelta(days=days_diff)
        param_opt_date_str = param_opt_date.strftime('%Y%m%d')

        param_log_dir = log_dirs[prediction_type].get('param')
        if param_log_dir:
            param_flag_path = os.path.join(param_log_dir, f"{param_opt_date_str}_param_opt_done.flag")
            if not os.path.exists(param_flag_path):
                param_opt_monday = param_opt_date - datetime.timedelta(days=param_opt_date.weekday())
                monday_str = param_opt_monday.strftime('%Y%m%d')
                param_flag_path = os.path.join(param_log_dir, f"{monday_str}_param_opt_done.flag")
            if os.path.exists(param_flag_path):
                status['paramOpt'] = True
                status['paramOptTime'] = datetime.datetime.fromtimestamp(
                    os.path.getmtime(param_flag_path),
                ).strftime('%Y-%m-%d %H:%M:%S')

        # --- Prediction status ---
        if prediction_type == 'supershort':
            predict_log_dir = log_dirs[prediction_type]['predict']
            date_logs = glob.glob(os.path.join(predict_log_dir, f"{date_str}*.log"))

            predict_flag_dir = os.path.join(log_dirs[prediction_type]['base'], 'auto_predict')
            predict_done_flags = []
            if os.path.exists(predict_flag_dir):
                predict_done_flags = glob.glob(os.path.join(predict_flag_dir, f"predict_{date_str}*.flag"))
                status['predictionCount'] = len(predict_done_flags)
            else:
                status['predictionCount'] = 0

            status['prediction'] = status['predictionCount'] >= 96

            if status['predictionCount'] > 0:
                latest_flag = max(predict_done_flags, key=os.path.getmtime)
                status['predictionTime'] = datetime.datetime.fromtimestamp(
                    os.path.getmtime(latest_flag),
                ).strftime('%Y-%m-%d %H:%M:%S')
            elif date_logs:
                latest_log = max(date_logs, key=os.path.getmtime)
                status['predictionTime'] = datetime.datetime.fromtimestamp(
                    os.path.getmtime(latest_log),
                ).strftime('%Y-%m-%d %H:%M:%S')

            # For "running" status on today, check the DB task.
            if is_today:
                with db_session() as session:
                    task = session.query(PredictionTask).filter_by(
                        farm_code=resolve_farm_code(''), task_type=prediction_type,
                    ).first()
                if task and task.enabled and status['predictionCount'] < 96:
                    status['prediction'] = True
        else:
            predict_flag_dir = log_dirs[prediction_type].get('train')
            if not predict_flag_dir:
                logger.error("未找到 %s 类型的训练日志目录配置", prediction_type)
                status['prediction'] = False
                status['predictionCompleted'] = False
            else:
                predict_flag_path = os.path.join(predict_flag_dir, f"{date_str}_predict_done.flag")
                flag_exists = os.path.exists(predict_flag_path)

                if flag_exists:
                    status['prediction'] = True
                    status['predictionCompleted'] = True
                    status['predictionTime'] = datetime.datetime.fromtimestamp(
                        os.path.getmtime(predict_flag_path),
                    ).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    status['prediction'] = False
                    status['predictionCompleted'] = False

                if is_today and not status['predictionCompleted']:
                    with db_session() as session:
                        task = session.query(PredictionTask).filter_by(
                            farm_code=resolve_farm_code(''), task_type=prediction_type,
                        ).first()
                    if task and task.enabled:
                        status['prediction'] = True

        legacy_data = {'status': status}
        return api_success(data=legacy_data, message='获取任务状态成功', legacy=legacy_data)
    except Exception as e:
        return api_error('获取任务状态失败', code=1500, status_code=500, details=str(e))


# ---------------------------------------------------------------------------
# Trigger -- dispatch Celery tasks
# ---------------------------------------------------------------------------

@autopredict_bp.route('/trigger', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/trigger', methods=['POST'])
@jwt_required()
def trigger_prediction():
    data = request.get_json(silent=True) or {}
    farm_code = resolve_farm_code(data.get('farm_code') or '')
    action = data.get('action', 'predict')
    prediction_type = data.get('type', 'supershort')

    if action not in ('train', 'predict'):
        return api_error('action 仅支持 train/predict', code=1001, status_code=400)
    if prediction_type not in _VALID_PREDICTION_TYPES:
        return api_error('type 仅支持 short/medium/supershort', code=1001, status_code=400)

    try:
        train_model, run_prediction, run_supershort_predict = _get_celery_tasks()
    except ImportError:
        return api_error('Celery 未安装，无法触发任务', code=1500, status_code=503)

    if prediction_type == 'supershort' and action == 'predict':
        result = run_supershort_predict.delay(farm_code)
    elif action == 'train':
        result = train_model.delay(farm_code, prediction_type)
    else:
        result = run_prediction.delay(farm_code, prediction_type)

    return api_success(
        data={"celery_task_id": result.id, "farm_code": farm_code, "type": prediction_type, "action": action},
        message=f"已触发 {action} 任务 ({prediction_type}, 场站: {farm_code})",
    )


# ---------------------------------------------------------------------------
# Runs -- query PredictionRun table
# ---------------------------------------------------------------------------

@autopredict_bp.route('/runs', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/runs', methods=['GET'])
def get_runs():
    farm_code = request.args.get('farm_code')
    task_type = request.args.get('type')
    action = request.args.get('action')
    celery_task_id = request.args.get('celery_task_id')
    limit = min(int(request.args.get('limit', 50)), 200)

    try:
        with db_session() as session:
            query = (
                session.query(PredictionRun, PredictionTask)
                .join(PredictionTask, PredictionRun.task_id == PredictionTask.id)
            )
            if farm_code:
                query = query.filter(PredictionTask.farm_code == farm_code)
            if task_type:
                query = query.filter(PredictionTask.task_type == task_type)
            if action:
                query = query.filter(PredictionRun.action == action)
            if celery_task_id:
                query = query.filter(PredictionRun.celery_task_id == celery_task_id)
            rows = query.order_by(desc(PredictionRun.created_at)).limit(limit).all()

            items = []
            for run, task in rows:
                result_data = None
                if run.result_json:
                    try:
                        import json as _json
                        result_data = _json.loads(run.result_json)
                    except Exception:
                        result_data = None
                items.append({
                    "id": run.id,
                    "farm_code": task.farm_code,
                    "task_type": task.task_type,
                    "action": run.action,
                    "status": run.status,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                    "duration_sec": run.duration_sec,
                    "error_message": run.error_message,
                    "result": result_data,
                })

            return api_success(data={"items": items, "count": len(items)})
    except Exception as e:
        return api_error(f"查询执行历史失败: {str(e)}")


# ---------------------------------------------------------------------------
# Schedule config
# ---------------------------------------------------------------------------

@autopredict_bp.route('/schedule_config', methods=['PUT'])
@autopredict_bp.route('/v1/autopredict/schedule_config', methods=['PUT'])
@jwt_required()
def update_schedule_config():
    data = request.get_json(silent=True) or {}
    farm_code = data.get('farm_code')
    task_type = data.get('type')
    train_schedule = data.get('train_schedule')
    predict_schedule = data.get('predict_schedule')

    if not farm_code or not task_type:
        return api_error('farm_code 和 type 为必填项', code=1001, status_code=400)
    if train_schedule and not _TIME_PATTERN.match(train_schedule):
        return api_error('train_schedule 格式无效，要求 HH:MM (如 03:00)', code=1001, status_code=400)
    if predict_schedule and not _TIME_PATTERN.match(predict_schedule):
        return api_error('predict_schedule 格式无效，要求 HH:MM (如 08:00)', code=1001, status_code=400)

    try:
        with db_session() as session:
            task = session.query(PredictionTask).filter_by(
                farm_code=farm_code, task_type=task_type,
            ).first()
            if not task:
                return api_error(f'未找到任务: {farm_code} {task_type}', code=1004, status_code=404)
            if train_schedule:
                task.train_schedule = train_schedule
            if predict_schedule:
                task.predict_schedule = predict_schedule
            task.updated_at = _dt.now()

        return api_success(
            data={"farm_code": farm_code, "type": task_type},
            message="调度配置已更新",
        )
    except Exception as e:
        return api_error(f"更新失败: {str(e)}")


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@autopredict_bp.route('/history', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/history', methods=['GET'])
def get_task_history():
    task_type = request.args.get('type')
    action = request.args.get('action')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        with db_session() as db:
            query = db.query(TaskHistory).order_by(TaskHistory.created_at.desc())

            if task_type:
                query = query.filter(TaskHistory.task_type == task_type)
            if action:
                query = query.filter(TaskHistory.action == action)

            total = query.count()
            history = query.offset(offset).limit(limit).all()

            result = []
            for item in history:
                result.append({
                    'id': item.id,
                    'task_id': item.task_id,
                    'task_type': item.task_type,
                    'action': item.action,
                    'status': item.status,
                    'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'details': item.details,
                    'user': item.user,
                })

            legacy_data = {
                'total': total,
                'offset': offset,
                'limit': limit,
                'data': result,
            }
            return api_success(
                data=legacy_data,
                message='获取任务历史成功',
                legacy=legacy_data,
            )

    except Exception as e:
        error_msg = f"获取任务历史记录出错: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        logger.error(error_msg)
        return api_error(
            '获取任务历史记录失败',
            code=1500,
            status_code=500,
            details=error_msg,
        )


# ---------------------------------------------------------------------------
# Model versions
# ---------------------------------------------------------------------------

@autopredict_bp.route('/model_versions', methods=['GET'])
def get_model_versions():
    """List model versions with optional filters."""
    from db_models import ModelVersion
    farm_code = request.args.get('farm_code', '')
    task_type = request.args.get('task_type', '')
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    with db_session() as session:
        query = session.query(ModelVersion)
        if farm_code:
            query = query.filter_by(farm_code=farm_code)
        if task_type:
            query = query.filter_by(task_type=task_type)
        if active_only:
            query = query.filter_by(is_active=True)
        versions = query.order_by(ModelVersion.trained_at.desc()).limit(50).all()

        result = []
        for v in versions:
            result.append({
                'id': v.id,
                'farm_code': v.farm_code,
                'task_type': v.task_type,
                'algorithm': v.algorithm,
                'val_rmse': v.val_rmse,
                'val_mae': v.val_mae,
                'val_accuracy': v.val_accuracy,
                'is_active': v.is_active,
                'lifecycle_status': v.lifecycle_status,
                'feature_contract_version': v.feature_contract_version,
                'dataset_version': v.dataset_version,
                'artifact_sha256': v.artifact_sha256,
                'approved_by': v.approved_by,
                'approved_at': v.approved_at.isoformat() if v.approved_at else None,
                'rejection_reason': v.rejection_reason,
                'training_samples': v.training_samples,
                'trained_at': v.trained_at.isoformat() if v.trained_at else None,
                'activated_at': v.activated_at.isoformat() if v.activated_at else None,
                'deactivated_at': v.deactivated_at.isoformat() if v.deactivated_at else None,
            })
    return api_success(data=result)


def _model_action_actor():
    acting_user = getattr(g, 'acting_user', None)
    if acting_user is not None and getattr(acting_user, 'username', None):
        return acting_user.username
    return str(get_jwt_identity() or 'unknown')


def _model_registry_action(version_id, action, reason=None):
    from services.model_registry import ModelRegistry

    registry = ModelRegistry()
    actor = _model_action_actor()
    try:
        if action == 'approve':
            result = registry.approve(version_id, actor)
            message = f'模型版本 {version_id} 已审批'
        elif action == 'reject':
            result = registry.reject(version_id, actor, reason)
            message = f'模型版本 {version_id} 已拒绝'
        elif action == 'rollback':
            result = registry.rollback_to(version_id, actor)
            message = f'运行模型已回滚到版本 {version_id}'
        else:
            return api_error('未知模型治理操作', code=1001, status_code=400)
        record_task_history(
            task_type='model',
            action=action,
            status='success',
            details=json.dumps(result, ensure_ascii=False),
            user=actor,
        )
        return api_success(data=result, message=message)
    except ValueError as exc:
        record_task_history(
            task_type='model',
            action=action,
            status='failed',
            details=str(exc),
            user=actor,
        )
        return api_error(str(exc), code=1001, status_code=400)


@autopredict_bp.route('/model_versions/<int:version_id>/approve', methods=['POST'])
@jwt_required()
@permission_required('manage_tasks')
def approve_model_version(version_id):
    """审批满足质量门槛且制品校验通过的候选模型。"""
    return _model_registry_action(version_id, 'approve')


@autopredict_bp.route('/model_versions/<int:version_id>/reject', methods=['POST'])
@jwt_required()
@permission_required('manage_tasks')
def reject_model_version(version_id):
    """拒绝候选模型并保留原因。"""
    data = request.get_json(silent=True) or {}
    reason = str(data.get('reason') or '').strip()
    if not reason:
        return api_error('拒绝原因不能为空', code=1001, status_code=400)
    return _model_registry_action(version_id, 'reject', reason=reason)


@autopredict_bp.route('/model_versions/<int:version_id>/rollback', methods=['POST'])
@jwt_required()
@permission_required('manage_tasks')
def rollback_model_version(version_id):
    """将运行版本切换到指定已审批模型。"""
    return _model_registry_action(version_id, 'rollback')


@autopredict_bp.route('/model_versions/<int:version_id>/deactivate', methods=['POST'])
@jwt_required()
@permission_required('manage_tasks')
def deactivate_model_version(version_id):
    """Deactivate a specific model version."""

    from services.model_registry import ModelRegistry
    registry = ModelRegistry()
    registry.deactivate(version_id)
    return api_success(message=f'模型版本 {version_id} 已停用')


@autopredict_bp.route('/model_versions/fusion_status', methods=['GET'])
def get_fusion_status():
    """Fusion status overview grouped by farm and task type."""
    from db_models import ModelVersion

    with db_session() as session:
        rows = session.query(
            ModelVersion.farm_code,
            ModelVersion.task_type,
            func.count(ModelVersion.id).label('total'),
            func.sum(db_case((ModelVersion.is_active == True, 1), else_=0)).label('active'),
        ).group_by(ModelVersion.farm_code, ModelVersion.task_type).all()

        result = []
        for row in rows:
            result.append({
                'farm_code': row.farm_code,
                'task_type': row.task_type,
                'total_models': row.total,
                'active_models': row.active,
                'fusion_enabled': row.active > 1 if row.active else False,
            })
    return jsonify({'code': 200, 'data': result})
