import os
import time
import threading

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DisconnectionError

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

# Module-level state — guarded by _lock for thread safety.
_engine = None
_SessionLocal = None
_lock = threading.Lock()


def _build_engine():
    """Create a SQLAlchemy engine with connection pool settings."""
    return create_engine(
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


def _init_engine(eng):
    """Attach event listeners to an engine."""
    @event.listens_for(eng, "checkout")
    def ping_connection(dbapi_connection, connection_record, connection_proxy):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SELECT 1")
        except Exception:
            connection_proxy._pool.dispose()
            raise
        finally:
            cursor.close()

    @event.listens_for(eng, "checkin")
    def record_checkin_time(dbapi_connection, connection_record):
        connection_record.info["last_use_time"] = time.time()


def ensure_engine():
    """Return the current engine, attempting reconnection if it is None.

    Thread-safe.  Returns None when the database is unreachable.
    """
    global _engine, _SessionLocal
    with _lock:
        if _engine is not None:
            return _engine
        try:
            eng = _build_engine()
            _init_engine(eng)
            # Verify the connection actually works.
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            _engine = eng
            _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
            print("[OK] database engine (re)connected")
            return _engine
        except Exception as exc:
            print(f"warning: database (re)connection failed: {exc}")
            return None


def invalidate_engine():
    """Mark the current engine as dead so the next call to ensure_engine()
    will attempt a fresh connection."""
    global _engine, _SessionLocal
    with _lock:
        if _engine is not None:
            try:
                _engine.dispose()
            except Exception:
                pass
        _engine = None
        _SessionLocal = None


# Legacy aliases used throughout the codebase.
engine = None
SessionLocal = None


def _sync_legacy_refs():
    """Keep the module-level engine / SessionLocal in sync for legacy code."""
    global engine, SessionLocal
    engine = _engine
    SessionLocal = _SessionLocal


# Try initial connection at import time (non-fatal if it fails).
try:
    eng = ensure_engine()
except Exception:
    eng = None
_sync_legacy_refs()


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


def get_db():
    eng = ensure_engine()
    _sync_legacy_refs()
    if eng is None:
        raise RuntimeError("database connection unavailable")

    cleanup_idle_connections(eng)
    session = _SessionLocal()
    try:
        yield session
    except (OperationalError, DisconnectionError):
        session.rollback()
        invalidate_engine()
        _sync_legacy_refs()
        raise
    finally:
        session.close()


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
