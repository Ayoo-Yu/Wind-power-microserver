from flask import Blueprint, request, jsonify, current_app
from db_session import db_session
from models import Turbine, Condition, Reading
from sqlalchemy.exc import IntegrityError
import pandas as pd
import io

physical_simulation_bp = Blueprint('physical_simulation', __name__, url_prefix='/physical_simulation')

def read_csv_with_fallback(file_stream):
    """
    Tries to read a CSV file stream with UTF-8, falls back to GBK on failure.
    """
    try:
        # Read the whole stream into a buffer first
        file_content = file_stream.read()
        # Try decoding with UTF-8
        return pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
    except UnicodeDecodeError:
        current_app.logger.info("UTF-8 decoding failed, falling back to GBK.")
        # If it fails, rewind and try with GBK
        return pd.read_csv(io.BytesIO(file_content), encoding='gbk')

@physical_simulation_bp.route('/turbines/batch', methods=['POST'])
def batch_add_turbines():
    """
    Batch add or update turbines from a CSV file.
    This performs an 'upsert' operation based on the composite key (farm_name, turbine_number).
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading"}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Invalid file type, only .csv is allowed"}), 400

    try:
        df = read_csv_with_fallback(file.stream)
        required_columns = ['farm_name', 'turbine_number', 'longitude', 'latitude']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            return jsonify({"error": f"Missing required columns in CSV: {', '.join(missing)}"}), 400
        
        records_to_upsert = df.to_dict(orient='records')

        with db_session() as session:
            # 先根据 CSV 统计每个场站在本次导入中应当保留的风机编号集合
            farm_to_turbines = {}
            for rec in records_to_upsert:
                farm_name = rec.get('farm_name')
                turbine_number = rec.get('turbine_number')
                if not farm_name or turbine_number is None:
                    continue
                farm_key = str(farm_name).strip()
                num_key = str(turbine_number).strip()
                if not farm_key or not num_key:
                    continue
                farm_to_turbines.setdefault(farm_key, set()).add(num_key)

            # 对于 CSV 中出现的每个场站：删除该场站下所有“不在 CSV 集合内”的风机及其读数，实现“先删旧再重建”
            for farm_name, turbine_numbers in farm_to_turbines.items():
                if not turbine_numbers:
                    continue
                turbines_to_delete = session.query(Turbine).filter(
                    Turbine.farm_name == farm_name,
                    ~Turbine.turbine_number.in_(list(turbine_numbers)),
                ).all()

                for turbine in turbines_to_delete:
                    # 先删除该风机下的读数，再删除风机本身，避免外键约束冲突
                    session.query(Reading).filter(Reading.turbine_id == turbine.turbine_id).delete(synchronize_session=False)
                    session.delete(turbine)

            # 使用应用层逻辑处理 upsert：存在则更新，不存在则插入
            for record in records_to_upsert:
                # 查找现有记录
                existing = session.query(Turbine).filter_by(
                    farm_name=record['farm_name'],
                    turbine_number=record['turbine_number']
                ).first()

                if existing:
                    # 更新现有记录
                    for key, value in record.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    # 插入新记录
                    session.add(Turbine(**record))
                    session.flush()
            session.commit()

    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred while processing the CSV: {e}")
        return jsonify({"error": "An unexpected error occurred during processing.", "details": str(e)}), 500

    return jsonify({"message": f"Successfully upserted {len(records_to_upsert)} turbines from {file.filename}."}), 201

@physical_simulation_bp.route('/conditions/batch', methods=['POST'])
def batch_add_conditions():
    """
    Batch add or update conditions from a CSV file.
    This performs an 'upsert' operation based on the composite key (farm_name, wind_speed, wind_direction).
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading"}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Invalid file type, only .csv is allowed"}), 400
        
    try:
        df = read_csv_with_fallback(file.stream)
        required_columns = ['farm_name', 'wind_speed', 'wind_direction']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            return jsonify({"error": f"Missing required columns in CSV: {', '.join(missing)}"}), 400
        # condition_id 是数据库自增主键，如果 CSV 中携带该列，可能与已有主键冲突
        # 这里显式丢弃 CSV 里的 condition_id，让数据库自行分配主键，避免 UniqueViolation
        if 'condition_id' in df.columns:
            df = df.drop(columns=['condition_id'])

        records_to_upsert = df.to_dict(orient='records')
    
        with db_session() as session:
            # Fallback logic for databases that don't support ON CONFLICT well or for simplicity
            for record in records_to_upsert:
                existing = session.query(Condition).filter_by(
                    farm_name=record['farm_name'],
                    wind_speed=record['wind_speed'],
                    wind_direction=record['wind_direction']
                ).first()

                if existing:
                    # Update is_interpolated if provided
                    if 'is_interpolated' in record:
                        existing.is_interpolated = record['is_interpolated']
                else:
                    # Insert new
                    session.add(Condition(**record))
                    session.flush()
            session.commit()
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred while processing the CSV: {e}")
        return jsonify({"error": "An unexpected error occurred during processing.", "details": str(e)}), 500

    return jsonify({"message": f"Successfully upserted {len(records_to_upsert)} conditions from {file.filename}."}), 201

@physical_simulation_bp.route('/readings/batch', methods=['POST'])
def batch_add_readings():
    """Batch add or update readings from a CSV file."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading"}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Invalid file type, only .csv is allowed"}), 400

    try:
        df = read_csv_with_fallback(file.stream)
        required_columns = ['condition_id', 'turbine_id', 'turbine_wind_speed']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            return jsonify({"error": f"Missing required columns in CSV: {', '.join(missing)}"}), 400
            
        readings_to_upsert = df.to_dict(orient='records')

        with db_session() as session:
            # 使用应用层逻辑处理upsert，避免重复数据问题
            for record in readings_to_upsert:
                # 查找现有记录
                existing = session.query(Reading).filter_by(
                    condition_id=record['condition_id'],
                    turbine_id=record['turbine_id']
                ).first()
                
                if existing:
                    # 更新现有记录
                    for key, value in record.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    # 插入新记录
                    session.add(Reading(**record))
                    session.flush()
            session.commit()
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred while processing the CSV: {e}")
        return jsonify({"error": "An unexpected error occurred during processing.", "details": str(e)}), 500

    return jsonify({"message": f"Successfully upserted {len(readings_to_upsert)} readings from {file.filename}."}), 201

@physical_simulation_bp.route('/turbines', methods=['GET'])
def get_turbines():
    """Get a list of turbines, optionally filtered by farm_name."""
    farm_name = request.args.get('farm_name')
    with db_session() as session:
        query = session.query(Turbine)
        if farm_name:
            query = query.filter(Turbine.farm_name == farm_name)
        
        turbines = query.all()
        # Using pandas to convert to json to handle decimal types correctly
        df = pd.DataFrame([t.__dict__ for t in turbines])
        if '_sa_instance_state' in df.columns:
            df.drop('_sa_instance_state', axis=1, inplace=True)
        return df.to_json(orient='records'), 200

@physical_simulation_bp.route('/conditions', methods=['GET'])
def get_conditions():
    """Get a list of conditions, optionally filtered by farm_name."""
    farm_name = request.args.get('farm_name')
    with db_session() as session:
        query = session.query(Condition)
        if farm_name:
            query = query.filter(Condition.farm_name == farm_name)
        
        conditions = query.all()
        df = pd.DataFrame([c.__dict__ for c in conditions])
        if '_sa_instance_state' in df.columns:
            df.drop('_sa_instance_state', axis=1, inplace=True)
        return df.to_json(orient='records', date_format='iso'), 200

@physical_simulation_bp.route('/readings', methods=['GET'])
def get_readings():
    """Get a list of readings, can be filtered by condition_id or turbine_id."""
    condition_id = request.args.get('condition_id', type=int)
    turbine_id = request.args.get('turbine_id', type=int)
    
    with db_session() as session:
        query = session.query(Reading)
        if condition_id:
            query = query.filter(Reading.condition_id == condition_id)
        if turbine_id:
            query = query.filter(Reading.turbine_id == turbine_id)
            
        readings = query.all()
        df = pd.DataFrame([r.__dict__ for r in readings])

        if '_sa_instance_state' in df.columns:
            df.drop('_sa_instance_state', axis=1, inplace=True)
        return df.to_json(orient='records'), 200 