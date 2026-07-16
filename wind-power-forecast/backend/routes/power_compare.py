import math
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from sqlalchemy import func, text

from db_models import ActualPower, MidPower, ShortlPower, SupershortlPower
from db_models.operational_data import AvailableCapacityData, TurbinePowerData
from db_models.report_config import WindFarm
from db_session import db_session
from db_models.ecmwf_grid_model import ecmwf_grid_table_name


bp = Blueprint('power_compare', __name__, url_prefix='/power-compare')

_BEIJING_OFFSET = timedelta(hours=8)


def _fetch_wind_speed_ecmwf(db, farm_code, start_dt, end_dt, lead_days):
    if not farm_code:
        return []

    table = ecmwf_grid_table_name(farm_code)
    start_utc = start_dt - _BEIJING_OFFSET
    end_utc = end_dt - _BEIJING_OFFSET
    try:
        rows = db.execute(text(f"""
            SELECT forecast_time,
                   AVG((features->>'ws200')::float) AS ws200
            FROM {table}
            WHERE forecast_time BETWEEN :s AND :e
              AND forecast_source = (
                  date_trunc('day', forecast_time + interval '8 hours')
                  - interval '1 day' * :ld
                  + interval '18 hours'
              )
              AND features ? 'ws200'
            GROUP BY forecast_time
            ORDER BY forecast_time
        """), {"s": start_utc, "e": end_utc, "ld": lead_days}).fetchall()
        raw = {r[0]: round(float(r[1]), 4) for r in rows if r[1] is not None}
        if not raw:
            return []

        result = []
        ts = min(raw)
        last = max(raw)
        while ts <= last:
            if ts in raw:
                result.append({"timestamp": (ts + _BEIJING_OFFSET).isoformat(), "wind_speed": raw[ts]})
            else:
                prev_ts, prev_val = None, None
                nxt_ts, nxt_val = None, None
                for k, v in raw.items():
                    if k < ts and (prev_ts is None or k > prev_ts):
                        prev_ts, prev_val = k, v
                    if k > ts and (nxt_ts is None or k < nxt_ts):
                        nxt_ts, nxt_val = k, v
                if prev_ts is not None and nxt_ts is not None:
                    ratio = (ts - prev_ts).total_seconds() / (nxt_ts - prev_ts).total_seconds()
                    interp = prev_val + (nxt_val - prev_val) * ratio
                    result.append({"timestamp": (ts + _BEIJING_OFFSET).isoformat(), "wind_speed": round(interp, 4)})
                elif prev_ts is not None:
                    result.append({"timestamp": (ts + _BEIJING_OFFSET).isoformat(), "wind_speed": prev_val})
                elif nxt_ts is not None:
                    result.append({"timestamp": (ts + _BEIJING_OFFSET).isoformat(), "wind_speed": nxt_val})
            ts += timedelta(hours=1)
        return result
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "ECMWF ws200 query failed for %s lead=%d", table, lead_days, exc_info=True
        )
        return []


def _calc_basic_metrics(actual_values, predicted_values):
    valid_pairs = []
    for actual, predicted in zip(actual_values, predicted_values):
        if actual is None or predicted is None:
            continue
        valid_pairs.append((float(actual), float(predicted)))

    if not valid_pairs:
        return {'points': 0, 'mae': None, 'rmse': None, 'mse': None}

    errors = [pred - actual for actual, pred in valid_pairs]
    abs_errors = [abs(err) for err in errors]
    sq_errors = [err * err for err in errors]
    count = len(valid_pairs)
    mse = sum(sq_errors) / count
    return {
        'points': count,
        'mae': sum(abs_errors) / count,
        'rmse': mse ** 0.5,
        'mse': mse
    }


def _series_from_rows(rows, value_attr='power'):
    return [
        {"timestamp": row.timestamp.isoformat(), "power": getattr(row, value_attr)}
        for row in rows
        if getattr(row, value_attr) is not None
    ]


def _query_actual_series(db, farm_code, start_dt, end_dt):
    query = db.query(ActualPower.timestamp, ActualPower.wp_true.label("power"))
    if farm_code:
        query = query.filter(ActualPower.farm_code == farm_code)
    rows = query.filter(
        ActualPower.timestamp.between(start_dt, end_dt),
        ActualPower.wp_true.isnot(None)
    ).order_by(ActualPower.timestamp).all()
    series = _series_from_rows(rows)
    if series:
        return series

    turbine_query = db.query(
        TurbinePowerData.timestamp,
        func.sum(TurbinePowerData.active_power).label("power")
    )
    if farm_code:
        turbine_query = turbine_query.filter(TurbinePowerData.farm_code == farm_code)
    rows = turbine_query.filter(
        TurbinePowerData.timestamp.between(start_dt, end_dt),
        TurbinePowerData.active_power.isnot(None)
    ).group_by(TurbinePowerData.timestamp).order_by(TurbinePowerData.timestamp).all()
    return _series_from_rows(rows)


def _query_prediction_series(db, farm_code, prediction_type, start_dt, end_dt):
    if prediction_type == 'short':
        pred_rows = db.query(ShortlPower.timestamp, ShortlPower.wp_pred.label("power")).filter(
            ShortlPower.farm_code == farm_code,
            ShortlPower.timestamp.between(start_dt, end_dt)
        ).order_by(ShortlPower.timestamp).all()
        return _series_from_rows(pred_rows)
    if prediction_type == 'mid':
        pred_rows = db.query(MidPower.timestamp, MidPower.wp_pred.label("power")).filter(
            MidPower.farm_code == farm_code,
            MidPower.timestamp.between(start_dt, end_dt)
        ).order_by(MidPower.timestamp).all()
        return _series_from_rows(pred_rows)
    return _query_supershort_average(
        db,
        farm_code,
        start_dt,
        end_dt,
        min_predictions_required=1,
        include_quality_info=False,
    )


def _query_supershort_average(db, farm_code, start_dt, end_dt, min_predictions_required, include_quality_info):
    max_offset_minutes = (17 - 2) * 15
    earliest_needed_dt = start_dt - timedelta(minutes=max_offset_minutes)

    query = db.query(SupershortlPower)
    if farm_code:
        query = query.filter(SupershortlPower.farm_code == farm_code)
    records = query.filter(
        SupershortlPower.timestamp.between(earliest_needed_dt, end_dt)
    ).order_by(SupershortlPower.timestamp).all()

    records_by_timestamp = {rec.timestamp: rec for rec in records}
    averaged_data = []
    current_target_dt = start_dt
    while current_target_dt <= end_dt:
        predictions = []
        sources = []
        for k in range(2, 18):
            offset_minutes = (k - 2) * 15
            source_timestamp = current_target_dt - timedelta(minutes=offset_minutes)
            source_record = records_by_timestamp.get(source_timestamp)
            if not source_record:
                continue
            column_name = f"wp_pred{k}"
            pred_value = getattr(source_record, column_name, None)
            if pred_value is not None:
                predictions.append(pred_value)
                sources.append(column_name)

        if len(predictions) >= min_predictions_required:
            data_point = {
                "timestamp": current_target_dt.isoformat(),
                "power": sum(predictions) / len(predictions)
            }
            if include_quality_info:
                data_point["prediction_count"] = len(predictions)
                data_point["prediction_sources"] = sources
                data_point["data_completeness"] = len(predictions) / 16.0
            averaged_data.append(data_point)
        current_target_dt += timedelta(minutes=15)
    return averaged_data


@bp.route('/regulatory_metrics', methods=['POST'])
def get_regulatory_metrics():
    """按版本化南网口径返回单站或多站日评估。"""

    from services.regulatory_evaluation_service import (
        POLICY,
        SUPPORTED_FORECAST_TYPES,
        evaluate_regulatory_period,
    )

    payload = request.get_json(silent=True) or {}
    start = payload.get('start')
    end = payload.get('end')
    if not start or not end:
        return jsonify({"code": 1001, "message": "missing start/end"}), 400
    try:
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()
    except (TypeError, ValueError):
        return jsonify({"code": 1001, "message": "invalid datetime format"}), 400
    if end_date < start_date:
        return jsonify({"code": 1001, "message": "end must not be before start"}), 400
    if (end_date - start_date).days > 30:
        return jsonify({"code": 1001, "message": "date range must not exceed 31 days"}), 400

    raw_types = payload.get('prediction_types') or list(SUPPORTED_FORECAST_TYPES)
    if not isinstance(raw_types, list):
        return jsonify({"code": 1001, "message": "prediction_types must be a list"}), 400
    prediction_types = []
    for item in raw_types:
        value = 'mid' if str(item).strip().lower() == 'medium' else str(item).strip().lower()
        if value not in SUPPORTED_FORECAST_TYPES:
            return jsonify({"code": 1001, "message": f"invalid prediction_type: {item}"}), 400
        if value not in prediction_types:
            prediction_types.append(value)

    farm_codes = payload.get('farm_codes') or []
    if payload.get('farm_code'):
        farm_codes = [payload.get('farm_code')]
    if farm_codes and not isinstance(farm_codes, list):
        return jsonify({"code": 1001, "message": "farm_codes must be a list"}), 400
    selected_codes = []
    for code in farm_codes:
        value = str(code).strip()
        if value and value not in selected_codes:
            selected_codes.append(value)
    with db_session() as db:
        query = db.query(WindFarm)
        if hasattr(WindFarm, 'deleted_at'):
            query = query.filter(WindFarm.deleted_at.is_(None))
        if hasattr(WindFarm, 'is_active'):
            query = query.filter(WindFarm.is_active.is_(True))
        if selected_codes:
            query = query.filter(WindFarm.farm_code.in_(selected_codes))
        farms = query.order_by(WindFarm.farm_code).all()

        items = []
        for farm in farms:
            capacity = float(farm.capacity or 0)
            if not math.isfinite(capacity) or capacity <= 0:
                items.append({
                    "farm_code": farm.farm_code,
                    "farm_name": farm.farm_name or farm.farm_code,
                    "capacity_mw": capacity,
                    "status": "blocked",
                    "message": "场站装机容量未配置",
                    "metrics": {},
                })
                continue
            result = evaluate_regulatory_period(
                db,
                farm_code=farm.farm_code,
                capacity_mw=capacity,
                start_date=start_date,
                end_date=end_date,
                forecast_types=prediction_types,
                persist=False,
            )
            result["farm_name"] = farm.farm_name or farm.farm_code
            result["status"] = "ok"
            items.append(result)

    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "policy": POLICY,
            "items": items,
            "count": len(items),
            "persisted": False,
        },
    })


@bp.route('/data', methods=['POST'])
def get_power_data():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "缺少请求体"}), 400

    try:
        start = data.get('start')
        end = data.get('end')
        types = data.get('types', [])
        if not isinstance(types, list):
            types = []
        type_set = {str(item).strip() for item in types if str(item).strip()}

        farm_code = data.get('farm_code')
        if isinstance(farm_code, str):
            farm_code = farm_code.strip() or None
        elif farm_code is not None:
            farm_code = str(farm_code).strip() or None

        supershort_horizon = data.get('supershort_horizon', 'average')
        min_predictions_required = int(data.get('min_predictions_required', 1) or 1)
        include_quality_info = bool(data.get('include_quality_info', False))

        if not start or not end:
            return jsonify({"error": "必须提供开始和结束时间"}), 400

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        with db_session() as db:
            result = {}

            if '实测值' in type_set:
                result['实测值'] = _query_actual_series(db, farm_code, start_dt, end_dt)

            if '超短期预测' in type_set:
                valid_horizons = [f"wp_pred{i}" for i in range(2, 18)]
                if supershort_horizon == 'average':
                    result['超短期预测'] = _query_supershort_average(
                        db, farm_code, start_dt, end_dt, min_predictions_required, include_quality_info
                    )
                elif supershort_horizon in valid_horizons:
                    query = db.query(
                        SupershortlPower.timestamp,
                        getattr(SupershortlPower, supershort_horizon).label("power")
                    )
                    if farm_code:
                        query = query.filter(SupershortlPower.farm_code == farm_code)
                    rows = query.filter(
                        SupershortlPower.timestamp.between(start_dt, end_dt)
                    ).order_by(SupershortlPower.timestamp).all()
                    result['超短期预测'] = _series_from_rows(rows)
                else:
                    result['超短期预测'] = []

            if '短期预测' in type_set:
                result['短期预测'] = _query_prediction_series(db, farm_code, 'short', start_dt, end_dt)

            if '中期预测' in type_set:
                result['中期预测'] = _query_prediction_series(db, farm_code, 'mid', start_dt, end_dt)

            if '短期风速预测' in type_set:
                ws = _fetch_wind_speed_ecmwf(db, farm_code, start_dt, end_dt, lead_days=2)
                if ws:
                    result['短期风速预测'] = ws

            if '中期风速预测' in type_set:
                ws = _fetch_wind_speed_ecmwf(db, farm_code, start_dt, end_dt, lead_days=4)
                if ws:
                    result['中期风速预测'] = ws

            if '可用容量' in type_set:
                cap_query = db.query(AvailableCapacityData)
                if farm_code:
                    cap_query = cap_query.filter(AvailableCapacityData.farm_code == farm_code)
                cap_rows = cap_query.filter(
                    AvailableCapacityData.timestamp.between(start_dt, end_dt)
                ).order_by(AvailableCapacityData.timestamp).all()

                if cap_rows:
                    result['可用容量'] = [
                        {"timestamp": c.timestamp.isoformat(), "available_capacity": c.available_capacity}
                        for c in cap_rows if c.available_capacity is not None
                    ]
                else:
                    farm_row = None
                    if farm_code:
                        farm_row = db.query(WindFarm).filter(WindFarm.farm_code == farm_code).first()
                    if farm_row and farm_row.capacity:
                        actual_base = db.query(ActualPower.timestamp)
                        if farm_code:
                            actual_base = actual_base.filter(ActualPower.farm_code == farm_code)
                        actual_base = actual_base.filter(
                            ActualPower.timestamp.between(start_dt, end_dt)
                        ).order_by(ActualPower.timestamp).all()
                        result['可用容量'] = [
                            {"timestamp": a.timestamp.isoformat(), "available_capacity": farm_row.capacity}
                            for a in actual_base
                        ]

            return jsonify(result)

    except ValueError:
        return jsonify({"error": "时间格式错误，请使用 ISO 8601 格式"}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@bp.route('/fleet_metrics', methods=['POST'])
def get_fleet_metrics():
    payload = request.get_json(silent=True) or {}
    start = payload.get('start')
    end = payload.get('end')
    farm_codes = payload.get('farm_codes') or []
    prediction_type = str(payload.get('prediction_type') or 'short').strip().lower()

    if not start or not end:
        return jsonify({"code": 1001, "message": "missing start/end"}), 400
    if prediction_type not in ('short', 'mid', 'supershort'):
        return jsonify({"code": 1001, "message": "invalid prediction_type"}), 400

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        return jsonify({"code": 1001, "message": "invalid datetime format"}), 400

    with db_session() as db:
        active_farms = db.query(WindFarm).filter(
            *([WindFarm.deleted_at == None] if hasattr(WindFarm, 'deleted_at') else []),
            *([WindFarm.is_active == True] if hasattr(WindFarm, 'is_active') else [])
        ).all()
        active_map = {farm.farm_code: farm for farm in active_farms}

        if isinstance(farm_codes, list) and farm_codes:
            selected_codes = []
            for code in farm_codes:
                if isinstance(code, str):
                    cleaned = code.strip()
                    if cleaned and cleaned not in selected_codes:
                        selected_codes.append(cleaned)
            target_codes = [code for code in selected_codes if code in active_map]
        else:
            target_codes = list(active_map.keys())

        if not target_codes:
            return jsonify({
                "code": 0,
                "message": "ok",
                "data": {"items": [], "count": 0, "prediction_type": prediction_type}
            }), 200

        result_items = []
        for farm_code in target_codes:
            farm = active_map.get(farm_code)
            actual_series = _query_actual_series(db, farm_code, start_dt, end_dt)
            actual_map = {
                datetime.fromisoformat(item['timestamp']): item['power']
                for item in actual_series
            }

            pred_series = _query_prediction_series(db, farm_code, prediction_type, start_dt, end_dt)
            pred_map = {
                datetime.fromisoformat(item['timestamp']): item['power']
                for item in pred_series
            }

            aligned_timestamps = sorted(set(actual_map.keys()) & set(pred_map.keys()))
            actual_values = [actual_map[ts] for ts in aligned_timestamps]
            predicted_values = [pred_map[ts] for ts in aligned_timestamps]
            metrics = _calc_basic_metrics(actual_values, predicted_values)

            result_items.append({
                "farm_code": farm_code,
                "farm_name": farm.farm_name if farm else farm_code,
                "actual_points": len(actual_map),
                "predicted_points": len(pred_map),
                **metrics
            })

        result_items.sort(key=lambda x: (x['rmse'] is None, x['rmse'] if x['rmse'] is not None else float('inf')))
        return jsonify({
            "code": 0,
            "message": "ok",
            "data": {
                "items": result_items,
                "count": len(result_items),
                "prediction_type": prediction_type
            }
        }), 200


@bp.route('/fleet_series', methods=['POST'])
def get_fleet_series():
    payload = request.get_json(silent=True) or {}
    start = payload.get('start')
    end = payload.get('end')
    farm_codes = payload.get('farm_codes') or []
    prediction_type = str(payload.get('prediction_type') or 'short').strip().lower()
    include_actual = payload.get('include_actual', True)

    if not start or not end:
        return jsonify({"code": 1001, "message": "missing start/end"}), 400
    if prediction_type not in ('short', 'mid', 'supershort'):
        return jsonify({"code": 1001, "message": "invalid prediction_type"}), 400

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        return jsonify({"code": 1001, "message": "invalid datetime format"}), 400

    with db_session() as db:
        active_farms = db.query(WindFarm).filter(
            *([WindFarm.deleted_at == None] if hasattr(WindFarm, 'deleted_at') else []),
            *([WindFarm.is_active == True] if hasattr(WindFarm, 'is_active') else [])
        ).all()
        active_map = {farm.farm_code: farm for farm in active_farms}

        if isinstance(farm_codes, list) and farm_codes:
            selected_codes = []
            for code in farm_codes:
                if isinstance(code, str):
                    cleaned = code.strip()
                    if cleaned and cleaned not in selected_codes:
                        selected_codes.append(cleaned)
            target_codes = [code for code in selected_codes if code in active_map]
        else:
            target_codes = list(active_map.keys())

        items = []
        for farm_code in target_codes:
            farm = active_map.get(farm_code)
            predicted = _query_prediction_series(db, farm_code, prediction_type, start_dt, end_dt)
            actual = _query_actual_series(db, farm_code, start_dt, end_dt) if include_actual else []
            items.append({
                "farm_code": farm_code,
                "farm_name": farm.farm_name if farm else farm_code,
                "predicted": predicted,
                "actual": actual
            })

        return jsonify({
            "code": 0,
            "message": "ok",
            "data": {
                "items": items,
                "count": len(items),
                "prediction_type": prediction_type,
                "include_actual": bool(include_actual)
            }
        }), 200
