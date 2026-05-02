import os
import time

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from config import KINGBASE_CONFIG
from db_models import Base, Model

# Register the custom KingBase dialect.
import kingbase_dialect  # noqa: F401


print("building database URL...")
print(
    f"DB_HOST: {KINGBASE_CONFIG['host']}, "
    f"DB_PORT: {KINGBASE_CONFIG['port']}, "
    f"DB_NAME: {KINGBASE_CONFIG['database']}"
)

DATABASE_URL = URL.create(
    "postgresql+kingbase",
    username=KINGBASE_CONFIG["user"],
    password=KINGBASE_CONFIG["password"],
    host=KINGBASE_CONFIG["host"],
    port=int(KINGBASE_CONFIG["port"]),
    database=KINGBASE_CONFIG["database"],
)

SQLALCHEMY_DATABASE_URI = DATABASE_URL
SQLALCHEMY_DATABASE_URL = DATABASE_URL


def create_engine_with_retry():
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            print(f"creating database engine, attempt {attempt + 1}/{max_retries}")
            engine = create_engine(
                SQLALCHEMY_DATABASE_URI,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=300,
                pool_pre_ping=True,
                pool_use_lifo=True,
                echo_pool=True,
            )

            @event.listens_for(engine, "checkout")
            def ping_connection(dbapi_connection, connection_record, connection_proxy):
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("SELECT 1")
                except Exception:
                    connection_proxy._pool.dispose()
                    raise
                finally:
                    cursor.close()

            @event.listens_for(engine, "checkin")
            def record_checkin_time(dbapi_connection, connection_record):
                connection_record.info["last_use_time"] = time.time()

            return engine
        except Exception as exc:
            print(
                f"failed to create database engine "
                f"({attempt + 1}/{max_retries}): {exc}"
            )
            if attempt >= max_retries - 1:
                raise
            time.sleep(retry_delay)


try:
    engine = create_engine_with_retry()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as exc:
    print(f"warning: database engine unavailable: {exc}")
    engine = None
    SessionLocal = None


def cleanup_idle_connections(db_engine, idle_timeout=120):
    if not db_engine:
        return

    try:
        pool = db_engine.pool
        if not hasattr(pool, "dispose"):
            return

        checked_in = getattr(pool, "checkedin", lambda: 0)()
        checked_out = getattr(pool, "checkedout", lambda: 0)()
        print(f"connection pool status: checked_in={checked_in}, checked_out={checked_out}")

        if checked_in > 5:
            pool.dispose()
            print("[OK] cleaned idle database connections")
    except Exception as exc:
        print(f"warning: cleanup idle connections failed: {exc}")


LEGACY_POWER_TABLES = {
    "actual_power": "ix_actual_power_farm_code_farm_part",
    "supershortl_power": "ix_supershortl_power_farm_code_farm_part",
    "shortl_power": "ix_shortl_power_farm_code_farm_part",
    "mid_power": "ix_mid_power_farm_code_farm_part",
}

DEFAULT_FARM_CODE = os.environ.get("DEFAULT_FARM_CODE", "")


def upgrade_legacy_power_tables():
    if engine is None:
        return

    inspector = inspect(engine)

    with engine.begin() as connection:
        for table_name, index_name in LEGACY_POWER_TABLES.items():
            if not inspector.has_table(table_name):
                continue

            existing_columns = {
                column["name"].lower() for column in inspector.get_columns(table_name)
            }
            existing_indexes = {
                index["name"].lower() for index in inspector.get_indexes(table_name)
            }

            if "farm_code" not in existing_columns:
                connection.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN farm_code VARCHAR(50)')
                )
                connection.execute(
                    text(
                        f'UPDATE "{table_name}" '
                        "SET farm_code = :default_farm_code "
                        "WHERE farm_code IS NULL"
                    ),
                    {"default_farm_code": DEFAULT_FARM_CODE},
                )
                connection.execute(
                    text(
                        f'ALTER TABLE "{table_name}" '
                        "ALTER COLUMN farm_code SET NOT NULL"
                    )
                )
                print(f"[OK] upgraded {table_name}.farm_code to current schema")

            if index_name.lower() not in existing_indexes:
                connection.execute(
                    text(
                        f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                        f'ON "{table_name}" (farm_code)'
                    )
                )
                print(f"[OK] created index {index_name}")


def check_migrations():
    if engine is None:
        print("warning: database engine unavailable, skip migration check")
        return

    try:
        Base.metadata.create_all(engine)
        print("[OK] ensured missing database tables exist")
        upgrade_legacy_power_tables()
    except Exception as exc:
        print(f"warning: migration check failed: {exc}")


try:
    check_migrations()
except Exception as exc:
    print(f"warning: migration check failed: {exc}")


def get_db():
    if SessionLocal is None:
        raise RuntimeError("database connection unavailable")

    cleanup_idle_connections(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def cleanup_old_models(db: Session, keep_last=5):
    """Keep the latest model records and remove older database rows."""
    try:
        models = db.query(Model).order_by(Model.train_time.desc()).all()
        if len(models) <= keep_last:
            return

        for model in models[keep_last:]:
            print(f"deleting old model record: {model.model_name}")
            db.delete(model)

        db.commit()
        print(f"[OK] cleaned old model records, kept latest {keep_last}")
    except Exception as exc:
        print(f"warning: cleanup old models failed: {exc}")
        db.rollback()
