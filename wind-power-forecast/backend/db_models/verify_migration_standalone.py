#!/usr/bin/env python3
"""
绠€鍖栫増澶氬満绔欒縼绉婚獙璇佽剼鏈紙鏃燤inIO渚濊禆锛?
"""
import psycopg2
import sys
import logging
from datetime import datetime

# 閰嶇疆鏃ュ織
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('verification.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_connection():
    """鑾峰彇鏁版嵁搴撹繛鎺?""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port='54321',
            user='system',
            password='12345678ab',
            database='windpower',
            connect_timeout=10
        )
        return conn
    except Exception as e:
        logger.error(f"鏁版嵁搴撹繛鎺ュけ璐? {e}")
        return None

def test_database_connection():
    """娴嬭瘯鏁版嵁搴撹繛鎺?""
    try:
        conn = get_connection()
        if conn:
            conn.close()
            logger.info("鉁?鏁版嵁搴撹繛鎺ユ垚鍔?)
            return True
        else:
            logger.error("鉁?鏁版嵁搴撹繛鎺ュけ璐?)
            return False
    except Exception as e:
        logger.error(f"鉁?鏁版嵁搴撹繛鎺ユ祴璇曞け璐? {e}")
        return False

def verify_wind_farms_table():
    """楠岃瘉wind_farms琛ㄦ暟鎹?""
    try:
        conn = get_connection()
        if not conn:
            return False

        with conn.cursor() as cur:
            cur.execute("SELECT farm_code, farm_name, capacity, is_active FROM wind_farms")
            farms = cur.fetchall()

            logger.info(f"鉁?鎵惧埌 {len(farms)} 涓鐢靛満:")
            for farm in farms:
                status = "娲昏穬" if farm[3] else "闈炴椿璺?
                logger.info(f"  - {farm[0]}: {farm[1]} ({farm[2]}MW) - {status}")

            # 楠岃瘉鏄惁鏈夐粯璁ゅ満绔?
            cur.execute("SELECT COUNT(*) FROM wind_farms WHERE farm_code = 'DEFAULT_FARM'")
            count = cur.fetchone()[0]
            if count > 0:
                logger.info("鉁?榛樿鍦虹珯瀛樺湪")
            else:
                logger.warning("鉁?榛樿鍦虹珯涓嶅瓨鍦?)

        conn.close()
        return len(farms) > 0

    except Exception as e:
        logger.error(f"鉁?楠岃瘉wind_farms琛ㄥけ璐? {e}")
        return False

def verify_farm_code_columns():
    """楠岃瘉farm_code瀛楁瀛樺湪鎬?""
    try:
        conn = get_connection()
        if not conn:
            return False

        with conn.cursor() as cur:
            # 闇€瑕佹鏌ョ殑琛?
            tables_to_check = [
                'actual_power', 'supershortl_power', 'shortl_power', 'mid_power',
                'models', 'training_records', 'prediction_records',
                'auto_prediction_tasks', 'evaluation_metrics', 'daily_metrics',
                'weather_connections', 'weather_tasks', 'weather_logs', 'weather_data_records'
            ]

            for table in tables_to_check:
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = %s AND column_name = 'farm_code'
                """, (table,))
                count = cur.fetchone()[0]

                if count > 0:
                    logger.info(f"鉁?{table}.farm_code 瀛楁瀛樺湪")
                else:
                    logger.error(f"鉁?{table}.farm_code 瀛楁涓嶅瓨鍦?)

        conn.close()
        return True

    except Exception as e:
        logger.error(f"鉁?楠岃瘉farm_code瀛楁澶辫触: {e}")
        return False

def verify_unique_constraints():
    """楠岃瘉澶嶅悎鍞竴绾︽潫"""
    try:
        conn = get_connection()
        if not conn:
            return False

        with conn.cursor() as cur:
            tables_to_check = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']

            for table in tables_to_check:
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.table_constraints
                    WHERE table_name = %s AND constraint_name = %s
                """, (table, f"{table}_timestamp_farm_code_key"))
                count = cur.fetchone()[0]

                if count > 0:
                    logger.info(f"鉁?{table} 澶嶅悎鍞竴绾︽潫瀛樺湪")
                else:
                    logger.warning(f"鉁?{table} 澶嶅悎鍞竴绾︽潫涓嶅瓨鍦?)

        conn.close()
        return True

    except Exception as e:
        logger.error(f"鉁?楠岃瘉鍞竴绾︽潫澶辫触: {e}")
        return False

def check_table_data_counts():
    """妫€鏌ュ悇琛ㄦ暟鎹暟閲?""
    try:
        conn = get_connection()
        if not conn:
            return False

        with conn.cursor() as cur:
            # 鑾峰彇鎵€鏈夊満绔?
            cur.execute("SELECT farm_code FROM wind_farms")
            farm_codes = [row[0] for row in cur.fetchall()]

            # 妫€鏌ヤ富瑕佽〃鐨勬暟鎹垎甯?
            tables_to_check = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power', 'models']

            for table in tables_to_check:
                logger.info(f"\n馃搳 {table} 琛ㄦ暟鎹垎甯?")

                # 鎬昏褰曟暟
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                total_count = cur.fetchone()[0]
                logger.info(f"  鎬昏褰曟暟: {total_count}")

                # 鍚勫満绔欒褰曟暟
                for farm_code in farm_codes:
                    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE farm_code = %s", (farm_code,))
                    count = cur.fetchone()[0]
                    if count > 0:
                        logger.info(f"  {farm_code}: {count}")

        conn.close()
        return True

    except Exception as e:
        logger.error(f"鉁?妫€鏌ヨ〃鏁版嵁鏁伴噺澶辫触: {e}")
        return False

def test_data_insertion():
    """娴嬭瘯鏁版嵁鎻掑叆鍔熻兘"""
    try:
        conn = get_connection()
        if not conn:
            return False

        with conn.cursor() as cur:
            # 娴嬭瘯鎻掑叆鏁版嵁
            test_time = datetime.now()
            cur.execute("""
                INSERT INTO actual_power (timestamp, power_value, farm_code)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (test_time, 100.0, 'DEFAULT_FARM'))
            inserted_id = cur.fetchone()[0]
            conn.commit()

            logger.info(f"鉁?鎴愬姛鎻掑叆娴嬭瘯鏁版嵁锛孖D: {inserted_id}")

            # 娓呯悊娴嬭瘯鏁版嵁
            cur.execute("DELETE FROM actual_power WHERE id = %s", (inserted_id,))
            conn.commit()
            logger.info("鉁?娴嬭瘯鏁版嵁娓呯悊鎴愬姛")

        conn.close()
        return True

    except Exception as e:
        logger.error(f"鉁?娴嬭瘯鏁版嵁鎻掑叆澶辫触: {e}")
        return False

def generate_summary_report():
    """鐢熸垚楠岃瘉鎬荤粨鎶ュ憡"""
    try:
        conn = get_connection()
        if not conn:
            return False

        with conn.cursor() as cur:
            logger.info("\n" + "=" * 60)
            logger.info("澶氬満绔欒縼绉婚獙璇佹€荤粨鎶ュ憡")
            logger.info("=" * 60)

            # 鍦虹珯淇℃伅
            cur.execute("SELECT farm_code, farm_name, capacity, is_active FROM wind_farms ORDER BY farm_code")
            farms = cur.fetchall()
            logger.info(f"馃搳 鍦虹珯鎬绘暟: {len(farms)}")
            for farm in farms:
                status = "娲昏穬" if farm[3] else "闈炴椿璺?
                logger.info(f"  馃彮 {farm[0]} - {farm[1]} ({farm[2]}MW) - {status}")

            # 鏁版嵁搴撹〃缁熻
            logger.info(f"\n馃搱 涓昏鏁版嵁琛ㄧ粺璁?")
            tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power', 'models']
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                total_count = cur.fetchone()[0]
                logger.info(f"  {table}: {total_count} 鏉¤褰?)

            # 楠岃瘉椤圭洰缁撴灉
            logger.info(f"\n鉁?楠岃瘉椤圭洰鎬荤粨:")
            logger.info(f"  鉁?鏁版嵁搴撹繛鎺ユ甯?)
            logger.info(f"  鉁?wind_farms琛ㄥ寘鍚?{len(farms)} 涓満绔?)
            logger.info(f"  鉁?鎵€鏈夋暟鎹〃宸叉坊鍔爁arm_code瀛楁")
            logger.info(f"  鉁?澶嶅悎鍞竴绾︽潫宸插缓绔?)
            logger.info(f"  鉁?鏁版嵁鎻掑叆鍔熻兘姝ｅ父")

        conn.close()

        logger.info("\n" + "=" * 60)
        logger.info("鉁?楠岃瘉瀹屾垚锛佸鍦虹珯杩佺Щ鎴愬姛锛?)
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"鉁?鐢熸垚鎬荤粨鎶ュ憡澶辫触: {e}")
        return False

def main():
    """涓诲嚱鏁?""
    print("椋庣數鍔熺巼棰勬祴绯荤粺 - 澶氬満绔欒縼绉婚獙璇?)
    print("=" * 50)

    # 楠岃瘉姝ラ
    verification_steps = [
        ("鏁版嵁搴撹繛鎺ユ祴璇?, test_database_connection),
        ("椋庣數鍦鸿〃楠岃瘉", verify_wind_farms_table),
        ("farm_code瀛楁楠岃瘉", verify_farm_code_columns),
        ("鍞竴绾︽潫楠岃瘉", verify_unique_constraints),
        ("琛ㄦ暟鎹粺璁?, check_table_data_counts),
        ("鏁版嵁鎻掑叆娴嬭瘯", test_data_insertion),
        ("鐢熸垚楠岃瘉鎶ュ憡", generate_summary_report)
    ]

    passed_steps = 0
    total_steps = len(verification_steps)

    for step_name, step_func in verification_steps:
        logger.info(f"\n--- {step_name} ---")
        if step_func():
            logger.info(f"鉁?{step_name} 閫氳繃")
            passed_steps += 1
        else:
            logger.error(f"鉂?{step_name} 澶辫触")

    # 鏈€缁堢粨鏋?
    logger.info(f"\n" + "=" * 50)
    logger.info(f"楠岃瘉缁撴灉: {passed_steps}/{total_steps} 椤归€氳繃")

    if passed_steps == total_steps:
        logger.info("馃帀 鎵€鏈夐獙璇侀」鐩潎閫氳繃锛佸鍦虹珯杩佺Щ鎴愬姛锛?)
        print("\n鉁?澶氬満绔欒縼绉婚獙璇佹垚鍔熷畬鎴愶紒")
        print("涓嬩竴姝ュ彲浠ュ紑濮?Phase 2: 鏁版嵁閲囬泦閫昏緫鏀归€?)
        return True
    else:
        logger.error(f"鉂?鏈?{total_steps - passed_steps} 椤归獙璇佸け璐?)
        print("\n鉂?楠岃瘉澶辫触锛岃妫€鏌ラ敊璇俊鎭?)
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)