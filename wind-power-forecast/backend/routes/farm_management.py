import json

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.authorization import permission_required
from db_session import db_session
from db_models.report_config import WindFarm
from db_models.farm_profile import FarmProfileConfig
from datetime import datetime
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 创建场站管理蓝图
farm_management_bp = Blueprint('farm_management', __name__)

PROFILE_FIELDS = {
    'commissioning_date',
    'province',
    'region',
    'longitude',
    'latitude',
    'altitude',
    'turbine_count',
    'hub_height',
    'met_tower_count',
    'power_curve_file_name',
    'power_curve_url',
    'supershort_model',
    'short_model',
    'lower_power_limit',
    'curtailment_threshold',
    'point_act_power',
    'point_wind_speed',
    'point_avail_count',
    'scada_status',
    'nwp_status',
    'current_actual_power',
}


def _apply_not_deleted_filter(query):
    """
    兼容不同库结构：
    - 新库可能有 deleted_at（软删除）
    - 旧库没有 deleted_at
    """
    if hasattr(WindFarm, 'deleted_at'):
        return query.filter(WindFarm.deleted_at == None)
    return query


def _read_profile_payload(profile):
    if not profile or not getattr(profile, 'payload', None):
        return {}
    try:
        payload = json.loads(profile.payload)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.warning('failed to parse farm profile payload for %s', getattr(profile, 'farm_code', None))
        return {}


def _serialize_farm(farm, profile_payload=None):
    return {
        'farm_code': farm.farm_code,
        'farm_name': farm.farm_name,
        'capacity': float(farm.capacity) if farm.capacity else 0.0,
        'location': farm.location,
        'is_active': farm.is_active,
        'created_at': farm.created_at.isoformat() if farm.created_at else None,
        'updated_at': farm.updated_at.isoformat() if farm.updated_at else None,
        **(profile_payload or {}),
    }


def _extract_profile_payload(data):
    return {key: data.get(key) for key in PROFILE_FIELDS if key in data}


def _upsert_farm_profile(session, farm_code, payload):
    if not farm_code:
        return
    profile = session.query(FarmProfileConfig).filter(FarmProfileConfig.farm_code == farm_code).first()
    serialized_payload = json.dumps(payload or {}, ensure_ascii=False)
    if profile:
        profile.payload = serialized_payload
        profile.updated_at = datetime.utcnow()
        return
    session.add(FarmProfileConfig(farm_code=farm_code, payload=serialized_payload))

@farm_management_bp.route('/api/farms', methods=['GET'])  # legacy path compatibility
@farm_management_bp.route('/farms', methods=['GET'])
@jwt_required()
@permission_required('view_all_data')
def get_farms():
    """获取所有风电场列表"""
    try:
        with db_session() as session:
            farms = _apply_not_deleted_filter(session.query(WindFarm)).all()
            farm_codes = [farm.farm_code for farm in farms if farm.farm_code]
            profiles = session.query(FarmProfileConfig).filter(FarmProfileConfig.farm_code.in_(farm_codes)).all() if farm_codes else []
            profile_map = {profile.farm_code: _read_profile_payload(profile) for profile in profiles}

            return jsonify([
                _serialize_farm(farm, profile_map.get(farm.farm_code))
                for farm in farms
            ])

    except Exception as e:
        logger.error(f"获取风电场列表失败: {e}")
        return jsonify({'message': '获取风电场列表失败'}), 500

@farm_management_bp.route('/api/farms/<farm_code>', methods=['GET'])  # legacy path compatibility
@farm_management_bp.route('/farms/<farm_code>', methods=['GET'])
@jwt_required()
@permission_required('view_all_data')
def get_farm_by_code(farm_code):
    """根据场站编码获取单场站信息"""
    try:
        normalized_code = (farm_code or '').strip()
        if not normalized_code:
            return jsonify({'message': '缺少场站编码'}), 400

        with db_session() as session:
            farm_query = _apply_not_deleted_filter(
                session.query(WindFarm).filter(WindFarm.farm_code == normalized_code)
            )
            farm = farm_query.first()

            if not farm:
                return jsonify({'message': '风电场不存在'}), 404

            profile = session.query(FarmProfileConfig).filter(FarmProfileConfig.farm_code == normalized_code).first()
            return jsonify(_serialize_farm(farm, _read_profile_payload(profile)))
    except Exception as e:
        logger.error(f"获取风电场详情失败: {e}")
        return jsonify({'message': '获取风电场详情失败'}), 500

@farm_management_bp.route('/api/farms', methods=['POST'])  # legacy path compatibility
@farm_management_bp.route('/farms', methods=['POST'])
@jwt_required()
@permission_required('configure_system')
def create_farm():
    """创建新的风电场"""
    try:
        data = request.get_json() or {}
        current_user_id = get_jwt_identity()

        # 验证必填字段
        required_fields = ['farm_code', 'farm_name', 'capacity']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'缺少必填字段: {field}'}), 400

        with db_session() as session:
            # 检查场站代码是否已存在
            existing_query = _apply_not_deleted_filter(
                session.query(WindFarm).filter(WindFarm.farm_code == data['farm_code'])
            )
            existing = existing_query.first()

            if existing:
                return jsonify({'message': '场站代码已存在'}), 400

            # 创建新场站
            farm = WindFarm(
                farm_code=data['farm_code'],
                farm_name=data['farm_name'],
                capacity=float(data['capacity']),
                location=data.get('location', ''),
                is_active=data.get('is_active', True),
                created_by=current_user_id
            )

            session.add(farm)
            _upsert_farm_profile(session, data['farm_code'], _extract_profile_payload(data))
            session.commit()

            return jsonify({
                'message': '风电场创建成功',
                'farm_code': farm.farm_code,
                'farm_name': farm.farm_name
            }), 201

    except Exception as e:
        logger.error(f"创建风电场失败: {e}")
        return jsonify({'message': '创建风电场失败'}), 500

@farm_management_bp.route('/api/farms/<farm_code>', methods=['PUT'])  # legacy path compatibility
@farm_management_bp.route('/farms/<farm_code>', methods=['PUT'])
@jwt_required()
@permission_required('configure_system')
def update_farm(farm_code):
    """更新风电场信息"""
    try:
        data = request.get_json() or {}

        with db_session() as session:
            farm_query = _apply_not_deleted_filter(
                session.query(WindFarm).filter(WindFarm.farm_code == farm_code)
            )
            farm = farm_query.first()

            if not farm:
                return jsonify({'message': '风电场不存在'}), 404

            # 更新字段
            update_fields = ['farm_name', 'capacity', 'location', 'is_active']
            is_active_changed = False
            new_active = None
            for field in update_fields:
                if field in data:
                    val = float(data[field]) if field == 'capacity' else data[field]
                    if field == 'is_active' and getattr(farm, field) != val:
                        is_active_changed = True
                        new_active = bool(val)
                    setattr(farm, field, val)

            farm.updated_at = datetime.utcnow()

            # Sync prediction_tasks.enabled when is_active changes
            if is_active_changed:
                from db_models.prediction_task import PredictionTask
                session.query(PredictionTask).filter(
                    PredictionTask.farm_code == farm_code
                ).update({"enabled": new_active, "updated_at": datetime.utcnow()})

            _upsert_farm_profile(session, farm_code, _extract_profile_payload(data))
            session.commit()

            return jsonify({'message': '风电场信息更新成功'})

    except Exception as e:
        logger.error(f"更新风电场失败: {e}")
        return jsonify({'message': '更新风电场失败'}), 500

@farm_management_bp.route('/api/farms/<farm_code>', methods=['DELETE'])  # legacy path compatibility
@farm_management_bp.route('/farms/<farm_code>', methods=['DELETE'])
@jwt_required()
@permission_required('configure_system')
def delete_farm(farm_code):
    """删除风电场（软删除）"""
    try:
        with db_session() as session:
            farm_query = _apply_not_deleted_filter(
                session.query(WindFarm).filter(WindFarm.farm_code == farm_code)
            )
            farm = farm_query.first()

            if not farm:
                return jsonify({'message': '风电场不存在'}), 404

            # 兼容旧库：无 deleted_at 时改为停用
            if hasattr(farm, 'deleted_at'):
                farm.deleted_at = datetime.utcnow()
            else:
                farm.is_active = False
            profile = session.query(FarmProfileConfig).filter(FarmProfileConfig.farm_code == farm_code).first()
            if profile:
                session.delete(profile)
            session.commit()

            return jsonify({'message': '风电场删除成功'})

    except Exception as e:
        logger.error(f"删除风电场失败: {e}")
        return jsonify({'message': '删除风电场失败'}), 500

@farm_management_bp.route('/api/farms/<farm_code>/toggle', methods=['POST'])  # legacy path compatibility
@farm_management_bp.route('/farms/<farm_code>/toggle', methods=['POST'])
@jwt_required()
@permission_required('configure_system')
def toggle_farm(farm_code):
    """启用/停用风电场"""
    try:
        with db_session() as session:
            farm_query = _apply_not_deleted_filter(
                session.query(WindFarm).filter(WindFarm.farm_code == farm_code)
            )
            farm = farm_query.first()

            if not farm:
                return jsonify({'message': '风电场不存在'}), 404

            farm.is_active = not farm.is_active
            farm.updated_at = datetime.utcnow()

            # Sync prediction_tasks.enabled
            from db_models.prediction_task import PredictionTask
            session.query(PredictionTask).filter(
                PredictionTask.farm_code == farm_code
            ).update({"enabled": farm.is_active, "updated_at": datetime.utcnow()})

            session.commit()

            status = "启用" if farm.is_active else "停用"
            return jsonify({
                'message': f'风电场已{status}',
                'is_active': farm.is_active
            })

    except Exception as e:
        logger.error(f"切换风电场状态失败: {e}")
        return jsonify({'message': '切换风电场状态失败'}), 500

@farm_management_bp.route('/api/farms/<farm_code>/stats', methods=['GET'])  # legacy path compatibility
@farm_management_bp.route('/farms/<farm_code>/stats', methods=['GET'])
@farm_management_bp.route('/api/farms/<farm_code>/statistics', methods=['GET'])  # compatibility alias
@farm_management_bp.route('/farms/<farm_code>/statistics', methods=['GET'])  # compatibility alias
@jwt_required()
@permission_required('view_all_data')
def get_farm_stats(farm_code):
    """获取风电场统计信息"""
    try:
        with db_session() as session:
            # 验证场站存在
            farm_query = _apply_not_deleted_filter(
                session.query(WindFarm).filter(WindFarm.farm_code == farm_code)
            )
            farm = farm_query.first()

            if not farm:
                return jsonify({'message': '风电场不存在'}), 404

            # 统计各类数据表的记录数
            stats = {
                'farm_code': farm_code,
                'farm_name': farm.farm_name,
                'capacity': float(farm.capacity) if farm.capacity else 0.0,
                'is_active': farm.is_active
            }

            # 统计运营数据
            from db_models.operational_data import (
                WindSpeedData, TurbinePowerData, WeatherData,
                InstalledCapacityData, AvailableCapacityData,
                TheoreticalPowerData, AvailablePowerData
            )

            operational_tables = {
                'wind_speed_data': WindSpeedData,
                'turbine_power_data': TurbinePowerData,
                'weather_data': WeatherData,
                'installed_capacity_data': InstalledCapacityData,
                'available_capacity_data': AvailableCapacityData,
                'theoretical_power_data': TheoreticalPowerData,
                'available_power_data': AvailablePowerData
            }

            for table_name, model in operational_tables.items():
                count = session.query(model).filter(model.farm_code == farm_code).count()
                stats[table_name] = count

            # 统计功率预测数据
            from db_models.power import ActualPower, SupershortlPower, ShortlPower, MidPower

            power_tables = {
                'actual_power': ActualPower,
                'supershortl_power': SupershortlPower,
                'shortl_power': ShortlPower,
                'mid_power': MidPower
            }

            for table_name, model in power_tables.items():
                count = session.query(model).filter(model.farm_code == farm_code).count()
                stats[table_name] = count

            return jsonify(stats)

    except Exception as e:
        logger.error(f"获取风电场统计失败: {e}")
        return jsonify({'message': '获取风电场统计失败'}), 500
