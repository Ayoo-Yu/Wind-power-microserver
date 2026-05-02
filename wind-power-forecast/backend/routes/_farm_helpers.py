"""Farm code helpers for the autopredict module."""

import logging
import threading

from sqlalchemy import text
from db_session import db_session

logger = logging.getLogger(__name__)

_cache_lock = threading.Lock()
active_farm_codes_cache = []
active_farms_cache = []


# ---------------------------------------------------------------------------
# Farm code normalization
# ---------------------------------------------------------------------------

def normalize_farm_code(farm_code):
    if farm_code is None:
        return None
    if not isinstance(farm_code, str):
        farm_code = str(farm_code)
    cleaned = farm_code.strip()
    return cleaned or None


def canonicalize_farm_code(farm_code, active_farm_codes=None):
    normalized_code = normalize_farm_code(farm_code)
    if not normalized_code:
        return None

    reference_codes = active_farm_codes if active_farm_codes is not None else get_active_farm_codes()
    lookup = {code.lower(): code for code in reference_codes}
    return lookup.get(normalized_code.lower(), normalized_code)


# ---------------------------------------------------------------------------
# Active farm queries
# ---------------------------------------------------------------------------

def get_active_farm_codes():
    """
    从 wind_farms 表读取有效场站编码。
    回退策略：
    1) 查询失败时优先返回最近一次成功缓存；
    2) 若无缓存则返回空列表。
    """
    global active_farm_codes_cache
    try:
        with db_session() as db:
            has_deleted_at = db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM information_schema.columns
                    WHERE table_name = 'wind_farms'
                      AND column_name = 'deleted_at'
                    """
                )
            ).scalar()

            if has_deleted_at:
                query_sql = """
                    SELECT farm_code
                    FROM wind_farms
                    WHERE COALESCE(is_active, TRUE) = TRUE
                      AND deleted_at IS NULL
                    ORDER BY farm_code
                """
            else:
                query_sql = """
                    SELECT farm_code
                    FROM wind_farms
                    WHERE COALESCE(is_active, TRUE) = TRUE
                    ORDER BY farm_code
                """

            rows = db.execute(text(query_sql)).fetchall()

        farm_codes = []
        seen_codes = set()
        for row in rows:
            if not row:
                continue
            code = normalize_farm_code(row[0])
            if not code:
                continue
            key = code.lower()
            if key in seen_codes:
                continue
            seen_codes.add(key)
            farm_codes.append(code)
        if farm_codes:
            with _cache_lock:
                active_farm_codes_cache = farm_codes
            return farm_codes

        with _cache_lock:
            if active_farm_codes_cache:
                return active_farm_codes_cache
        return farm_codes
    except Exception as e:
        with _cache_lock:
            if active_farm_codes_cache:
                logger.warning("读取场站列表失败，使用缓存场站: %s", e)
                return active_farm_codes_cache
        logger.warning("读取场站列表失败: %s", e)
        return []


def get_active_farms():
    """
    从 wind_farms 表读取有效场站（编码+名称）。
    回退策略：
    1) 查询失败时优先返回最近一次成功缓存；
    2) 若无缓存则返回空列表。
    """
    global active_farms_cache
    try:
        with db_session() as db:
            has_deleted_at = db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM information_schema.columns
                    WHERE table_name = 'wind_farms'
                      AND column_name = 'deleted_at'
                    """
                )
            ).scalar()

            if has_deleted_at:
                query_sql = """
                    SELECT farm_code, farm_name, capacity
                    FROM wind_farms
                    WHERE COALESCE(is_active, TRUE) = TRUE
                      AND deleted_at IS NULL
                    ORDER BY farm_code
                """
            else:
                query_sql = """
                    SELECT farm_code, farm_name, capacity
                    FROM wind_farms
                    WHERE COALESCE(is_active, TRUE) = TRUE
                    ORDER BY farm_code
                """

            rows = db.execute(text(query_sql)).fetchall()

        farms = []
        seen_codes = set()
        for row in rows:
            if not row:
                continue
            code = normalize_farm_code(row[0])
            if not code:
                continue
            key = code.lower()
            if key in seen_codes:
                continue
            seen_codes.add(key)
            farm_name = row[1].strip() if isinstance(row[1], str) and row[1].strip() else code
            farms.append({
                'farm_code': code,
                'farm_name': farm_name,
                'capacity': float(row[2]) if row[2] is not None else None
            })
        if farms:
            with _cache_lock:
                active_farms_cache = farms
            return farms

        with _cache_lock:
            if active_farms_cache:
                return active_farms_cache
        return []
    except Exception as e:
        with _cache_lock:
            if active_farms_cache:
                logger.warning("读取场站详情失败，使用缓存场站: %s", e)
                return active_farms_cache
        logger.warning("读取场站详情失败: %s", e)
        return []


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def is_valid_farm_code(farm_code):
    normalized_code = normalize_farm_code(farm_code)
    if not normalized_code:
        return False
    active_code_lookup = {code.lower(): code for code in get_active_farm_codes()}
    return normalized_code.lower() in active_code_lookup


def resolve_farm_code(raw_farm_code):
    """
    解析请求中的 farm_code：
    - 为空时使用首个有效场站
    - 非空时原样返回
    """
    active_farms = get_active_farm_codes()
    normalized_code = normalize_farm_code(raw_farm_code)

    if normalized_code:
        return canonicalize_farm_code(normalized_code, active_farms)

    return active_farms[0] if active_farms else ''
