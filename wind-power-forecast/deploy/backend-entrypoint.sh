#!/bin/bash
set -e

export PYTHONPATH="/app:${PYTHONPATH:-}"

mkdir -p /app/backend/utils /app/backend/data
touch /app/backend/utils/__init__.py

cat > /tmp/check_db.py <<'PY'
import os
import sys
import psycopg2

try:
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "kingbase"),
        port=os.environ.get("DB_PORT", "54321"),
        user=os.environ.get("DB_USER", "system"),
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ.get("DB_NAME", "windpower"),
        connect_timeout=3,
    )
    conn.close()
    print("Database connection ok")
    sys.exit(0)
except Exception as exc:
    print(f"Database connection failed: {exc}")
    sys.exit(1)
PY

echo "Waiting for database..."
for i in $(seq 1 30); do
    if python /tmp/check_db.py; then
        echo "Database is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "Database did not become ready in time." >&2
        exit 1
    fi
    echo "Waiting for database... $i/30"
    sleep 2
done

SCHEMA_ACTION="${DB_SCHEMA_ACTION:-prepare}"
case "${SCHEMA_ACTION}" in
    prepare)
        python manage_db.py prepare
        ;;
    upgrade)
        python manage_db.py upgrade
        ;;
    check)
        python manage_db.py check
        ;;
    skip)
        echo "Database schema check skipped by configuration."
        ;;
    *)
        echo "Unsupported DB_SCHEMA_ACTION: ${SCHEMA_ACTION}" >&2
        exit 2
        ;;
esac

echo "Initializing users and permissions..."
python -m init_users
python -m fix_admin_permissions
python -m fix_user_permissions

python - <<'PY'
from pathlib import Path

for path in Path("/app").rglob("*.py"):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        continue

    if " | None" not in text or "from __future__ import annotations" in text:
        continue

    lines = text.splitlines()
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if len(lines) > insert_at and "coding" in lines[insert_at]:
        insert_at += 1

    lines.insert(insert_at, "from __future__ import annotations")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

cat > /app/wsgi_app.py <<'PY'
import gevent.monkey
gevent.monkey.patch_all()

from app import app as application

app = application
PY

CORES="$(grep -c ^processor /proc/cpuinfo || echo 1)"
WORKERS="${GUNICORN_WORKERS:-3}"
echo "Detected $CORES CPU cores; starting $WORKERS gunicorn workers."

exec gunicorn \
  --workers "$WORKERS" \
  --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  --worker-connections 2000 \
  --timeout 600 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 200 \
  --log-level info \
  --bind 0.0.0.0:5000 \
  --preload \
  wsgi_app:app
