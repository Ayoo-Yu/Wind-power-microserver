from flask import Blueprint, request, jsonify
from datetime import datetime
from models import ActualPower, SupershortlPower, ShortlPower, MidPower
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
        
        if not start or not end:
            return jsonify({"error": "必须提供开始和结束时间"}), 400

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        
        with db_session() as db:
            result = {}

            if '实测值' in types:
                actual = db.query(ActualPower).filter(
                    ActualPower.timestamp.between(start_dt, end_dt)
                ).all()
                result['实测值'] = [
                    {"timestamp": a.timestamp.isoformat(), "power": a.wp_true} 
                    for a in actual
                ]

            if '超短期预测' in types:
                supershort = db.query(SupershortlPower).filter(
                    SupershortlPower.timestamp.between(start_dt, end_dt)
                ).all()
                result['超短期预测'] = [
                    {"timestamp": s.timestamp.isoformat(), "power": s.wp_pred} 
                    for s in supershort
                ]

            if '短期预测' in types:
                short = db.query(ShortlPower).filter(
                    ShortlPower.timestamp.between(start_dt, end_dt)
                ).all()
                result['短期预测'] = [
                    {"timestamp": s.timestamp.isoformat(), "power": s.wp_pred} 
                    for s in short
                ]

            if '中期预测' in types:
                mid = db.query(MidPower).filter(
                    MidPower.timestamp.between(start_dt, end_dt)
                ).all()
                result['中期预测'] = [
                    {"timestamp": m.timestamp.isoformat(), "power": m.wp_pred} 
                    for m in mid
                ]

            return jsonify(result)

    except ValueError as e:
        return jsonify({"error": "时间格式错误，请使用ISO 8601格式"}), 400
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500 