from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from models import ActualPower, SupershortlPower, ShortlPower, MidPower, TrainPreShort, TrainPreMiddle
from sqlalchemy import func
from database_config import get_db
from sqlalchemy.orm import Session
from db_session import db_session

bp = Blueprint('power_compare', __name__, url_prefix='/power-compare')

@bp.route('/data', methods=['POST'])
def get_power_data():
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求体"}), 400
    
    try:
        start = data.get('start')
        end = data.get('end')
        types = data.get('types', [])
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

            if '实测值' in types:
                actual = db.query(ActualPower).filter(
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
                    potential_records = db.query(SupershortlPower).filter(
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
                    query = db.query(SupershortlPower.timestamp,
                                   getattr(SupershortlPower, supershort_horizon_requested).label("power"))
                    
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
                short = db.query(ShortlPower).filter(
                    ShortlPower.timestamp.between(start_dt, end_dt)
                ).order_by(ShortlPower.timestamp).all()
                result['短期预测'] = [
                    {"timestamp": s.timestamp.isoformat(), "power": s.wp_pred} 
                    for s in short if s.wp_pred is not None
                ]

            if '中期预测' in types:
                mid = db.query(MidPower).filter(
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
                short_ws = db.query(
                    TrainPreShort.Timestamp,
                    avg_ws_expr.label("avg_wind_speed")
                ).filter(
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
                mid_ws = db.query(
                    TrainPreMiddle.Timestamp,
                    avg_ws_expr.label("avg_wind_speed")
                ).filter(
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