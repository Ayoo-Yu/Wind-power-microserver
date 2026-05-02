#!/usr/bin/env python3
"""
鏃燤inIO渚濊禆鐨勫鍦虹珯杩佺Щ鑴氭湰
"""
import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text

# 娣诲姞椤圭洰璺緞
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 閰嶇疆鏃ュ織
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_url():
    """鑾峰彇鏁版嵁搴撹繛鎺RL锛堜笉渚濊禆external object storage锛?""
    from config import KINGBASE_CONFIG
    return f"postgresql+psycopg2://{KINGBASE_CONFIG['user']}:{KINGBASE_CONFIG['password']}@{KINGBASE_CONFIG['host']}:{KINGBASE_CONFIG['port']}/{KINGBASE_CONFIG['database']}"

def create_default_farm(engine):
    """鍒涘缓榛樿鍦虹珯"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM wind_farms WHERE farm_code = :farm_code"),
                {"farm_code": "DEFAULT_FARM"}
            ).fetchone()

            if not result:
                conn.execute(
                    text("""
                        INSERT INTO wind_farms (farm_code, farm_name, capacity, location, is_active)
                        VALUES (:farm_code, :farm_name, :capacity, :location, :is_active)
                    """),
                    {
                        "farm_code": "DEFAULT_FARM",
                        "farm_name": "榛樿椋庣數鍦?,
                        "capacity": 100.0,
                        "location": "榛樿浣嶇疆",
                        "is_active": True
                    }
                )
                conn.commit()
                logger.info("鉁?鍒涘缓榛樿鍦虹珯: DEFAULT_FARM")
            else:
                logger.info("鉁?榛樿鍦虹珯宸插瓨鍦?)

            return True
    except Exception as e:
        logger.error(f"鍒涘缓榛樿鍦虹珯澶辫触: {e}")
        return False

def add_farm_code_columns(engine):
    """涓洪渶瑕佺殑琛ㄦ坊鍔爁arm_code瀛楁"""
    try:
        with engine.connect() as conn:
            tables = [
                'actual_power',
                'supershortl_power',
                'shortl_power',
                'mid_power',
                'models',
                'training_records',
                'prediction_records',
                'auto_prediction_tasks',
                'evaluation_metrics',
                'daily_metrics',
                'weather_connections',
                'weather_tasks',
                'weather_logs',
                'weather_data_records'
            ]

            for table in tables:
                try:
                    # 妫€鏌ュ瓧娈垫槸鍚﹀瓨鍦?
                    result = conn.execute(
                        text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = :table AND column_name = 'farm_code'
                        """),
                        {"table": table}
                    ).fetchone()

                    if not result:
                        # 娣诲姞瀛楁
                        conn.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM'")
                        )

                        # 鍒涘缓绱㈠紩
                        conn.execute(
                            text(f"CREATE INDEX IF NOT EXISTS idx_{table}_farm_code ON {table}(farm_code)")
                        )
                        logger.info(f"鉁?{table} 娣诲姞farm_code瀛楁鍜岀储寮?)
                    else:
                        logger.info(f"鉁?{table}.farm_code瀛楁宸插瓨鍦?)

                except Exception as e:
                    logger.warning(f"澶勭悊{table}鏃跺嚭閿? {e}")

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"娣诲姞farm_code瀛楁澶辫触: {e}")
        return False

def update_constraints(engine):
    """鏇存柊绾︽潫"""
    try:
        with engine.connect() as conn:
            # 绉婚櫎鍘熸湁unique绾︽潫
            tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']
            for table in tables:
                try:
                    conn.execute(
                        text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_timestamp_key")
                    )
                    logger.info(f"鉁?绉婚櫎{table}鍘熸湁unique绾︽潫")
                except Exception as e:
                    logger.warning(f"绉婚櫎{table}绾︽潫鏃跺嚭閿? {e}")

            # 娣诲姞澶嶅悎unique绾︽潫
            for table in tables:
                try:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD CONSTRAINT {table}_timestamp_farm_code_key UNIQUE (timestamp, farm_code)")
                    )
                    logger.info(f"鉁?娣诲姞{table}澶嶅悎unique绾︽潫")
                except Exception as e:
                    logger.warning(f"娣诲姞{table}澶嶅悎绾︽潫鏃跺嚭閿? {e}")

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"鏇存柊绾︽潫澶辫触: {e}")
        return False

def verify_migration(engine):
    """楠岃瘉杩佺Щ缁撴灉"""
    try:
        with engine.connect() as conn:
            # 妫€鏌ラ粯璁ゅ満绔?
            result = conn.execute(
                text("SELECT COUNT(*) FROM wind_farms WHERE farm_code = 'DEFAULT_FARM'")
            ).fetchone()
            logger.info(f"鉁?榛樿鍦虹珯璁板綍鏁? {result[0]}")

            # 妫€鏌ュ瓧娈?
            tables_check = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']
            for table in tables_check:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'farm_code'")
                ).fetchone()
                logger.info(f"鉁?{table}.farm_code瀛楁瀛樺湪: {result[0]}")

            logger.info("鉁?杩佺Щ楠岃瘉瀹屾垚")
            return True

    except Exception as e:
        logger.error(f"楠岃瘉杩佺Щ澶辫触: {e}")
        return False

def main():
    """涓诲嚱鏁?""
    print("椋庣數鍔熺巼棰勬祴绯荤粺 - 澶氬満绔欒縼绉伙紙鏃燤inIO锛?)
    print("=" * 50)

    try:
        # 鍒涘缓鏁版嵁搴撳紩鎿?
        db_url = get_database_url()
        print(f"鏁版嵁搴揢RL: {db_url}")
        engine = create_engine(db_url)
        logger.info("鉁?鏁版嵁搴撳紩鎿庡垱寤烘垚鍔?)

        # 鎵ц杩佺Щ姝ラ
        steps = [
            ("鍒涘缓榛樿鍦虹珯", create_default_farm),
            ("娣诲姞farm_code瀛楁", add_farm_code_columns),
            ("鏇存柊绾︽潫", update_constraints),
            ("楠岃瘉杩佺Щ", verify_migration)
        ]

        for step_name, step_func in steps:
            logger.info(f"\n--- {step_name} ---")
            if not step_func(engine):
                logger.error(f"鉁?{step_name}澶辫触")
                return False

        logger.info("\n" + "=" * 50)
        logger.info("馃帀 澶氬満绔欒縼绉绘垚鍔熷畬鎴愶紒")
        logger.info("=" * 50)

        return True

    except Exception as e:
        logger.error(f"杩佺Щ澶辫触: {e}")
        return False

if __name__ == "__main__":
    if main():
        print("\n鉁?杩佺Щ鎴愬姛瀹屾垚锛?)
        print("\n涓嬩竴姝ワ細")
        print("1. 閲嶅惎搴旂敤绋嬪簭浠ヤ娇鐢ㄦ柊鐨勬暟鎹ā鍨?)
        print("2. 娴嬭瘯澶氬満绔欏姛鑳?)
        print("3. 寮€濮嬬浜岄樁娈碉細鏁版嵁閲囬泦閫昏緫鏀归€?)
    else:
        print("\n鉂?杩佺Щ澶辫触锛岃妫€鏌ユ棩蹇?)
        sys.exit(1)