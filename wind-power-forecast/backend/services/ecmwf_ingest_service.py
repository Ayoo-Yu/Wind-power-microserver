"""
ECMWF 气象数据摄取与查询服务

职责：
- ingest_dataframe(): 将解析后的 DataFrame 批量写入 ecmwf_meteorological_data 表
- query_prediction_data(): 查询预测输入数据，返回与模板 CSV 结构一致的 DataFrame
- get_latest_timestamp(): 获取最新数据时间戳

纯 SQLAlchemy 实现，不依赖 gevent/eventlet，backend 和 autopredict 均可使用。
"""

import logging
import datetime
import pandas as pd
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from db_models.ecmwf_model import EcmwfMeteorologicalData

logger = logging.getLogger(__name__)

# 模板列名（从 CSV 头部读取时的原始列名，如 "100u_23.8_103.2"）
# 通过模型 __table__.columns 自动提取，避免硬编码
_DATA_COLUMNS = [
    c.name for c in EcmwfMeteorologicalData.__table__.columns
    if c.name not in ('id', 'timestamp', 'farm_code', 'data_type', 'source_file', 'ingested_at')
]

# CSV列名 -> Python属性名 的映射
# e.g. "100u_23.8_103.2" -> "col_100u_23_8_103_2"
def _csv_col_to_attr(csv_col: str) -> str:
    return 'col_' + csv_col.replace('.', '_')

# Python属性名 -> DB列名 的映射（从 mapper 元数据自动构建，避免字符串操作歧义）
# e.g. "col_100u_23_8_103_2" -> "100u_23.8_103.2"  (grid point, dots in lat/lon)
# e.g. "col_ws10_1"         -> "ws10_1"             (derived wind speed, no dots)
_ATTR_TO_DB_COL = {a.key: a.columns[0].name for a in inspect(EcmwfMeteorologicalData).column_attrs}


def _attr_to_db_col(attr: str) -> str:
    """Python 属性名 → 真实 DB 列名"""
    return _ATTR_TO_DB_COL.get(attr, attr)


def ingest_dataframe(
    db: Session,
    df: pd.DataFrame,
    farm_code: str,
    data_type: str,
    source_file: str = None
) -> int:
    """将 ECMWF DataFrame 批量写入数据库（幂等 upsert）

    Args:
        db: SQLAlchemy Session
        df: 解析后的 DataFrame，列名应与模板 CSV 头部一致（如 "100u_23.8_103.2"）
        farm_code: 风场编码
        data_type: 数据类型 ('DQ', 'CDQ', 'QXYC')
        source_file: 原始 E-text 文件名

    Returns:
        摄取的行数
    """
    if df is None or df.empty:
        logger.warning("ingest_dataframe: empty DataFrame, skipping")
        return 0

    now = datetime.datetime.now()
    rows = []

    for _, row in df.iterrows():
        ts = row.get('Timestamp') or row.get('timestamp')
        if ts is None:
            continue
        if isinstance(ts, str):
            ts = pd.Timestamp(ts).to_pydatetime()

        record = {
            'timestamp': ts,
            'farm_code': farm_code,
            'data_type': data_type,
            'source_file': source_file,
            'ingested_at': now,
        }

        for col in _DATA_COLUMNS:
            if col in row.index:
                record[_csv_col_to_attr(col)] = float(row[col]) if pd.notna(row[col]) else None

        rows.append(record)

    if not rows:
        logger.warning("ingest_dataframe: no valid rows after processing")
        return 0

    # 使用 bulk upsert: INSERT ... ON CONFLICT DO UPDATE
    # 注意：不在此处 commit/rollback，由调用方管理事务生命周期
    try:
        _bulk_upsert(db, rows)
        logger.info(f"Ingested {len(rows)} rows (farm={farm_code}, type={data_type})")
        return len(rows)
    except Exception as e:
        logger.error(f"Bulk upsert failed, trying row-by-row: {e}")
        return _row_by_row_upsert(db, rows)


def _bulk_upsert(db: Session, rows: list) -> None:
    """批量 upsert 使用 raw SQL（分批执行，每批100行）"""
    if not rows:
        return

    # 构建列列表
    meta_cols = ['timestamp', 'farm_code', 'data_type', 'source_file', 'ingested_at']
    data_attrs = [k for k in rows[0].keys() if k not in meta_cols]

    all_cols = meta_cols + data_attrs

    # 构建 SQL: INSERT INTO ... VALUES ... ON CONFLICT DO UPDATE
    table = EcmwfMeteorologicalData.__tablename__

    col_str = ', '.join(f'"{_attr_to_db_col(c)}"' for c in all_cols)

    # 使用具名参数（psycopg2 需要 string key）
    param_names = [f'p{i}' for i in range(len(all_cols))]
    placeholders = ', '.join(f':{n}' for n in param_names)

    update_cols = [c for c in all_cols if c not in ('timestamp', 'farm_code', 'data_type')]
    update_str = ', '.join(
        f'"{_attr_to_db_col(c)}" = EXCLUDED."{_attr_to_db_col(c)}"'
        for c in update_cols
    )

    sql = text(f"""
        INSERT INTO "{table}" ({col_str})
        VALUES ({placeholders})
        ON CONFLICT ("timestamp", "farm_code", "data_type")
        DO UPDATE SET {update_str}
    """)

    # 转换 rows 为参数列表，分批执行
    BATCH_SIZE = 100
    for offset in range(0, len(rows), BATCH_SIZE):
        batch = rows[offset:offset + BATCH_SIZE]
        params_list = []
        for row in batch:
            values = [row.get(c) for c in all_cols]
            params_list.append(dict(zip(param_names, values)))
        db.execute(sql, params_list)


def _row_by_row_upsert(db: Session, rows: list) -> int:
    """逐行 upsert 作为备选方案，返回成功行数"""
    inserted = 0
    for row in rows:
        try:
            existing = db.query(EcmwfMeteorologicalData).filter_by(
                timestamp=row['timestamp'],
                farm_code=row['farm_code'],
                data_type=row['data_type']
            ).first()

            if existing:
                for key, val in row.items():
                    if key not in ('timestamp', 'farm_code', 'data_type'):
                        setattr(existing, key, val)
            else:
                record = EcmwfMeteorologicalData(**row)
                db.add(record)

            inserted += 1
        except Exception as e:
            logger.warning(f"Row upsert failed for ts={row.get('timestamp')}: {e}")
            db.rollback()
            continue

    logger.info(f"Row-by-row upsert: {inserted}/{len(rows)} rows")
    return inserted


def query_prediction_data(
    db: Session,
    farm_code: str,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    data_type: str = 'DQ',
    limit: int = None
) -> pd.DataFrame:
    """查询预测输入数据

    Args:
        db: SQLAlchemy Session
        farm_code: 风场编码
        start_time: 查询起始时间
        end_time: 查询结束时间
        data_type: 数据类型 ('DQ', 'CDQ', 'QXYC')
        limit: 最大返回行数 (None=不限)

    Returns:
        DataFrame，列名与 template_predict_input.csv 完全一致，按 timestamp 排序
    """
    # 构建 SELECT 列列表，按模板顺序
    select_cols = ['"timestamp"'] + [f'"{c}"' for c in _DATA_COLUMNS]
    select_str = ', '.join(select_cols)

    table = EcmwfMeteorologicalData.__tablename__

    params = {
        'farm_code': farm_code,
        'data_type': data_type,
        'start_time': start_time,
        'end_time': end_time,
    }

    if limit and int(limit) > 0:
        params['lim'] = max(1, int(limit))
        limit_clause = 'LIMIT :lim'
    else:
        limit_clause = ''

    sql = text(f"""
        SELECT {select_str}
        FROM "{table}"
        WHERE "farm_code" = :farm_code
          AND "data_type" = :data_type
          AND "timestamp" >= :start_time
          AND "timestamp" <= :end_time
        ORDER BY "timestamp" ASC
        {limit_clause}
    """)

    df = pd.read_sql(sql, db.bind, params=params)

    return df


def get_latest_timestamp(db: Session, farm_code: str, data_type: str) -> datetime.datetime:
    """获取最新数据时间戳"""
    result = db.query(EcmwfMeteorologicalData.timestamp).filter_by(
        farm_code=farm_code,
        data_type=data_type
    ).order_by(EcmwfMeteorologicalData.timestamp.desc()).first()

    return result[0] if result else None


def get_data_availability(db: Session, farm_code: str, date: datetime.date) -> dict:
    """获取指定日期的数据可用性"""
    start = datetime.datetime.combine(date, datetime.time.min)
    end = datetime.datetime.combine(date, datetime.time.max)

    table = EcmwfMeteorologicalData.__tablename__
    sql = text(f"""
        SELECT "data_type", COUNT(*) as cnt, MIN("timestamp") as min_ts, MAX("timestamp") as max_ts
        FROM "{table}"
        WHERE "farm_code" = :farm_code
          AND "timestamp" >= :start_time
          AND "timestamp" <= :end_time
        GROUP BY "data_type"
    """)

    results = db.execute(sql, {
        'farm_code': farm_code,
        'start_time': start,
        'end_time': end,
    }).fetchall()

    return {
        row[0]: {'count': row[1], 'min_timestamp': row[2], 'max_timestamp': row[3]}
        for row in results
    }
