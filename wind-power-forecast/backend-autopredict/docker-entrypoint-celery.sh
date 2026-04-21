#!/bin/bash
set -e

mkdir -p /app/utils
touch /app/utils/__init__.py

mkdir -p /app/backend
if [ ! -L "/app/backend/env" ]; then
    ln -sf /opt/conda/envs/wind-power-env /app/backend/env
fi

cat > check_db.py << 'EOL'
import psycopg2, os, sys
try:
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'kingbase'),
        port=os.environ.get('DB_PORT', '54321'),
        user=os.environ.get('DB_USER', 'system'),
        password=os.environ.get('DB_PASSWORD', ''),
        dbname=os.environ.get('DB_NAME', 'windpower'),
        connect_timeout=3
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
EOL

echo "Waiting for database..."
for i in $(seq 1 30); do
    if python check_db.py; then
        echo "Database ready"
        break
    fi
    echo "Waiting for database... $i/30"
    sleep 2
done

exec "$@"
