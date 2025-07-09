from flask import Blueprint, request, jsonify
from datetime import datetime
from models import ActualPower, SupershortlPower, ShortlPower, MidPower, TrainPreShort, TrainPreMiddle  # Added TrainPreShort, TrainPreMiddle
from sqlalchemy import func  # Added func for average calculation
from database_config import get_db
from sqlalchemy.orm import Session
from db_session import db_session  # 导入上下文管理器

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
        supershort_horizon_requested = data.get('supershort_horizon', 'average') # Defaults to average

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
                    for a in actual
                ]

            if '超短期预测' in types:
                query = db.query(SupershortlPower.timestamp)
                
                valid_horizons = [f"wp_pred{i}" for i in range(2, 18)]

                if supershort_horizon_requested != 'average' and supershort_horizon_requested in valid_horizons:
                    # Query for a specific horizon
                    query = query.add_columns(getattr(SupershortlPower, supershort_horizon_requested).label("power"))
                else:
                    # Query for the average of all horizons
                    avg_expr = sum(getattr(SupershortlPower, col) for col in valid_horizons) / len(valid_horizons)
                    query = db.query(SupershortlPower.timestamp, avg_expr.label("power"))

                supershort_data = query.filter(
                    SupershortlPower.timestamp.between(start_dt, end_dt)
                ).order_by(SupershortlPower.timestamp).all()
                
                result['超短期预测'] = [
                    {"timestamp": s.timestamp.isoformat(), "power": s.power} 
                    for s in supershort_data
                ]


            if '短期预测' in types:
                short = db.query(ShortlPower).filter(
                    ShortlPower.timestamp.between(start_dt, end_dt)
                ).order_by(ShortlPower.timestamp).all()
                result['短期预测'] = [
                    {"timestamp": s.timestamp.isoformat(), "power": s.wp_pred} 
                    for s in short
                ]

            if '中期预测' in types:
                mid = db.query(MidPower).filter(
                    MidPower.timestamp.between(start_dt, end_dt)
                ).order_by(MidPower.timestamp).all()
                result['中期预测'] = [
                    {"timestamp": m.timestamp.isoformat(), "power": m.wp_pred} 
                    for m in mid
                ]
            
            if '短期风速预测' in types:
                # Calculate average wind speed: (ws10 + ws100 + ws200) / 3, handling NULLs
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
                    for sw in short_ws
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
                    for mw in mid_ws
                ]

            return jsonify(result)

    except ValueError as e:
        return jsonify({"error": "时间格式错误，请使用ISO 8601格式"}), 400
    except Exception as e:
        # It's good practice to log the exception here
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500 