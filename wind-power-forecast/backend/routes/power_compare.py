from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from models import ActualPower, SupershortlPower, ShortlPower, MidPower, TrainPreShort, TrainPreMiddle
from sqlalchemy import func
from database_config import get_db
from sqlalchemy.orm import Session
from db_session import db_session
from db_models.report_config import WindFarm

bp = Blueprint('power_compare', __name__, url_prefix='/power-compare')


def _calc_basic_metrics(actual_values, predicted_values):
    valid_pairs = []
    for actual, predicted in zip(actual_values, predicted_values):
        if actual is None or predicted is None:
            continue
        valid_pairs.append((float(actual), float(predicted)))

    if not valid_pairs:
        return {
            'points': 0,
            'mae': None,
            'rmse': None,
            'mse': None
        }

    errors = [pred - actual for actual, pred in valid_pairs]
    abs_errors = [abs(err) for err in errors]
    sq_errors = [err * err for err in errors]
    count = len(valid_pairs)
    mse = sum(sq_errors) / count
    rmse = mse ** 0.5
    mae = sum(abs_errors) / count
    return {
        'points': count,
        'mae': mae,
        'rmse': rmse,
        'mse': mse
    }


def _query_prediction_series(db, farm_code, prediction_type, start_dt, end_dt):
    if prediction_type == 'short':
        pred_rows = db.query(ShortlPower.timestamp, ShortlPower.wp_pred).filter(
            ShortlPower.farm_code == farm_code,
            ShortlPower.timestamp.between(start_dt, end_dt)
        ).order_by(ShortlPower.timestamp).all()
        return [{"timestamp": row.timestamp.isoformat(), "power": row.wp_pred} for row in pred_rows if row.wp_pred is not None]
    if prediction_type == 'mid':
        pred_rows = db.query(MidPower.timestamp, MidPower.wp_pred).filter(
            MidPower.farm_code == farm_code,
            MidPower.timestamp.between(start_dt, end_dt)
        ).order_by(MidPower.timestamp).all()
        return [{"timestamp": row.timestamp.isoformat(), "power": row.wp_pred} for row in pred_rows if row.wp_pred is not None]
    pred_rows = db.query(SupershortlPower.timestamp, SupershortlPower.wp_pred2).filter(
        SupershortlPower.farm_code == farm_code,
        SupershortlPower.timestamp.between(start_dt, end_dt)
    ).order_by(SupershortlPower.timestamp).all()
    return [{"timestamp": row.timestamp.isoformat(), "power": row.wp_pred2} for row in pred_rows if row.wp_pred2 is not None]

@bp.route('/data', methods=['POST'])
def get_power_data():
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求体"}), 400
    
    try:
        start = data.get('start')
        end = data.get('end')
        types = data.get('types', [])
        farm_code = data.get('farm_code')
        if isinstance(farm_code, str):
            farm_code = farm_code.strip() or None
        elif farm_code is not None:
            farm_code = str(farm_code).strip() or None
        # New parameter for ultra-short-term horizon selection
        supershort_horizon_requested = data.get('supershort_horizon', 'average')
        # 新增参数：最小预测值数量要求
        min_predictions_required = data.get('min_predictions_required', 1)  # 默认至少需要1个预测值
        # 新增参数：是否包含数据质量信息
        include_quality_info = data.get('include_quality_info', False)

        if not start or not end:
            return jsonify({"error": "必须提供开始和结束时间"}), 400

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        
        with db_session() as db:
            result = {}

            def apply_farm_filter(query, model):
                if farm_code and hasattr(model, 'farm_code'):
                    return query.filter(model.farm_code == farm_code)
                return query

            if '实测值' in types:
                actual_query = apply_farm_filter(db.query(ActualPower), ActualPower)
                actual = actual_query.filter(
                    ActualPower.timestamp.between(start_dt, end_dt)
                ).order_by(ActualPower.timestamp).all()
                result['实测值'] = [
                    {"timestamp": a.timestamp.isoformat(), "power": a.wp_true} 
                    for a in actual if a.wp_true is not None
                ]

            if '超短期预测' in types:
                valid_horizons = [f"wp_pred{i}" for i in range(2, 18)]

                if supershort_horizon_requested == 'average':
                    # 计算正确的超短期预测均值
                    # 最大偏移量：wp_pred17需要回溯(17-2)*15=225分钟的数据
                    max_offset_minutes = (17 - 2) * 15
                    earliest_needed_dt = start_dt - timedelta(minutes=max_offset_minutes)

                    # 获取所有可能需要的SupershortlPower记录
                    potential_query = apply_farm_filter(db.query(SupershortlPower), SupershortlPower)
                    potential_records = potential_query.filter(
                        SupershortlPower.timestamp.between(earliest_needed_dt, end_dt)
                    ).order_by(SupershortlPower.timestamp).all()

                    # 按时间戳组织记录，便于快速查找
                    records_by_timestamp = {rec.timestamp: rec for rec in potential_records}
                    averaged_supershort_data = []

                    # 遍历目标时间范围内的每个15分钟间隔
                    current_target_dt = start_dt
                    while current_target_dt <= end_dt:
                        predictions_for_target = []
                        available_predictions_info = []  # 用于记录哪些预测值可用
                        
                        # 对于每个wp_pred列，找到预测当前目标时间的值
                        for k in range(2, 18):  # wp_pred2 到 wp_pred17
                            column_name = f"wp_pred{k}"
                            # 计算源时间戳：wp_pred2是当前时间，wp_pred3是15分钟前，以此类推
                            offset_minutes = (k - 2) * 15
                            source_timestamp = current_target_dt - timedelta(minutes=offset_minutes)
                            
                            # 查找对应的记录
                            source_record = records_by_timestamp.get(source_timestamp)
                            if source_record:
                                pred_value = getattr(source_record, column_name, None)
                                if pred_value is not None:
                                    predictions_for_target.append(pred_value)
                                    available_predictions_info.append(f"wp_pred{k}")
                        
                        # 如果有有效预测值，计算平均值
                        if predictions_for_target:
                            avg_power = sum(predictions_for_target) / len(predictions_for_target)
                            
                            # 可选：添加元数据信息，说明使用了多少个预测值
                            data_point = {
                                "timestamp": current_target_dt.isoformat(),
                                "power": avg_power
                            }
                            
                            # 如果启用了质量信息，添加额外的元数据
                            if include_quality_info:
                                data_point["prediction_count"] = len(predictions_for_target)
                                data_point["prediction_sources"] = available_predictions_info
                                data_point["data_completeness"] = len(predictions_for_target) / 16.0
                            
                            # 检查是否满足最小预测值数量要求
                            if len(predictions_for_target) >= min_predictions_required:
                                averaged_supershort_data.append(data_point)
                                
                                # 如果预测值数量少于期望的数量，记录警告
                                total_expected = 16  # wp_pred2 到 wp_pred17
                                if len(predictions_for_target) < total_expected:
                                    print(f"警告: 时间 {current_target_dt} 只有 {len(predictions_for_target)}/{total_expected} 个预测值可用: {available_predictions_info}")
                            else:
                                print(f"跳过: 时间 {current_target_dt} 预测值数量 {len(predictions_for_target)} 少于最小要求 {min_predictions_required}")
                        else:
                            # 可选：如果完全没有预测值，也可以记录这种情况
                            print(f"警告: 时间 {current_target_dt} 没有可用的预测值")
                        
                        # 移动到下一个15分钟间隔
                        current_target_dt += timedelta(minutes=15)
                    
                    result['超短期预测'] = averaged_supershort_data

                elif supershort_horizon_requested in valid_horizons:
                    # 查询特定的预测列
                    query = apply_farm_filter(
                        db.query(
                            SupershortlPower.timestamp,
                            getattr(SupershortlPower, supershort_horizon_requested).label("power")
                        ),
                        SupershortlPower
                    )
                    
                    supershort_data = query.filter(
                        SupershortlPower.timestamp.between(start_dt, end_dt)
                    ).order_by(SupershortlPower.timestamp).all()
                    
                    result['超短期预测'] = [
                        {"timestamp": s.timestamp.isoformat(), "power": s.power}
                        for s in supershort_data if s.power is not None
                    ]
                else:
                    # 无效的预测范围请求
                    result['超短期预测'] = []

            if '短期预测' in types:
                short_query = apply_farm_filter(db.query(ShortlPower), ShortlPower)
                short = short_query.filter(
                    ShortlPower.timestamp.between(start_dt, end_dt)
                ).order_by(ShortlPower.timestamp).all()
                result['短期预测'] = [
                    {"timestamp": s.timestamp.isoformat(), "power": s.wp_pred} 
                    for s in short if s.wp_pred is not None
                ]

            if '中期预测' in types:
                mid_query = apply_farm_filter(db.query(MidPower), MidPower)
                mid = mid_query.filter(
                    MidPower.timestamp.between(start_dt, end_dt)
                ).order_by(MidPower.timestamp).all()
                result['中期预测'] = [
                    {"timestamp": m.timestamp.isoformat(), "power": m.wp_pred} 
                    for m in mid if m.wp_pred is not None
                ]
            
            if '短期风速预测' in types:
                avg_ws_expr = (
                    (func.coalesce(TrainPreShort.col_ws200_8, 0)) 
                )
                short_ws_query = apply_farm_filter(
                    db.query(
                        TrainPreShort.Timestamp,
                        avg_ws_expr.label("avg_wind_speed")
                    ),
                    TrainPreShort
                )
                short_ws = short_ws_query.filter(
                    TrainPreShort.Timestamp.between(start_dt, end_dt)
                ).order_by(TrainPreShort.Timestamp).all()
                result['短期风速'] = [
                    {"timestamp": sw.Timestamp.isoformat(), "wind_speed": sw.avg_wind_speed}
                    for sw in short_ws if sw.avg_wind_speed is not None
                ]

            if '中期风速预测' in types:
                avg_ws_expr = (
                    (func.coalesce(TrainPreMiddle.col_ws200_8, 0)) 
                )
                mid_ws_query = apply_farm_filter(
                    db.query(
                        TrainPreMiddle.Timestamp,
                        avg_ws_expr.label("avg_wind_speed")
                    ),
                    TrainPreMiddle
                )
                mid_ws = mid_ws_query.filter(
                    TrainPreMiddle.Timestamp.between(start_dt, end_dt)
                ).order_by(TrainPreMiddle.Timestamp).all()
                result['中期风速'] = [
                    {"timestamp": mw.Timestamp.isoformat(), "wind_speed": mw.avg_wind_speed}
                    for mw in mid_ws if mw.avg_wind_speed is not None
                ]

            return jsonify(result)

    except ValueError as e:
        return jsonify({"error": "时间格式错误，请使用ISO 8601格式"}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500

@bp.route('/fleet_metrics', methods=['POST'])
def get_fleet_metrics():
    """
    Multi-station comparison metrics aggregation.
    request:
      {
        "start": "2026-03-01 00:00:00",
        "end": "2026-03-01 23:59:59",
        "farm_codes": ["farm_a", "farm_b"],
        "prediction_type": "short|mid|supershort"
      }
    """
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
            WindFarm.deleted_at == None,
            WindFarm.is_active == True
        ).all()
        active_map = {farm.farm_code: farm for farm in active_farms}

        if isinstance(farm_codes, list) and len(farm_codes) > 0:
            selected_codes = []
            for code in farm_codes:
                if isinstance(code, str):
                    cleaned = code.strip()
                    if cleaned and cleaned not in selected_codes:
                        selected_codes.append(cleaned)
            invalid_codes = [code for code in selected_codes if code not in active_map]
            if invalid_codes:
                return jsonify({
                    "code": 1001,
                    "message": f"invalid farm_codes: {', '.join(invalid_codes)}"
                }), 400
            target_codes = selected_codes
        else:
            target_codes = list(active_map.keys())

        if not target_codes:
            return jsonify({
                "code": 0,
                "message": "ok",
                "data": {
                    "items": [],
                    "count": 0,
                    "prediction_type": prediction_type
                }
            }), 200

        result_items = []
        for farm_code in target_codes:
            farm = active_map.get(farm_code)
            actual_rows = db.query(ActualPower.timestamp, ActualPower.wp_true).filter(
                ActualPower.farm_code == farm_code,
                ActualPower.timestamp.between(start_dt, end_dt)
            ).order_by(ActualPower.timestamp).all()
            actual_map = {
                row.timestamp: row.wp_true
                for row in actual_rows
                if row.wp_true is not None
            }

            pred_series = _query_prediction_series(db, farm_code, prediction_type, start_dt, end_dt)
            pred_map = {datetime.fromisoformat(item['timestamp']): item['power'] for item in pred_series}

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
    """
    Multi-station curve overlay data.
    request:
      {
        "start": "2026-03-01 00:00:00",
        "end": "2026-03-01 23:59:59",
        "farm_codes": ["farm_a", "farm_b"],
        "prediction_type": "short|mid|supershort",
        "include_actual": true
      }
    """
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
            WindFarm.deleted_at == None,
            WindFarm.is_active == True
        ).all()
        active_map = {farm.farm_code: farm for farm in active_farms}

        if isinstance(farm_codes, list) and len(farm_codes) > 0:
            selected_codes = []
            for code in farm_codes:
                if isinstance(code, str):
                    cleaned = code.strip()
                    if cleaned and cleaned not in selected_codes:
                        selected_codes.append(cleaned)
            invalid_codes = [code for code in selected_codes if code not in active_map]
            if invalid_codes:
                return jsonify({
                    "code": 1001,
                    "message": f"invalid farm_codes: {', '.join(invalid_codes)}"
                }), 400
            target_codes = selected_codes
        else:
            target_codes = list(active_map.keys())

        items = []
        for farm_code in target_codes:
            farm = active_map.get(farm_code)
            predicted = _query_prediction_series(db, farm_code, prediction_type, start_dt, end_dt)
            actual = []
            if include_actual:
                actual_rows = db.query(ActualPower.timestamp, ActualPower.wp_true).filter(
                    ActualPower.farm_code == farm_code,
                    ActualPower.timestamp.between(start_dt, end_dt)
                ).order_by(ActualPower.timestamp).all()
                actual = [
                    {"timestamp": row.timestamp.isoformat(), "power": row.wp_true}
                    for row in actual_rows if row.wp_true is not None
                ]
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
