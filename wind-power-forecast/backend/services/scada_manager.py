"""
SCADA Connection Manager - manages worker subprocesses for each SCADA connection.
Each connection runs as an isolated subprocess (scada_worker.py).
"""
import json
import logging
import subprocess
import sys
import threading
import time
import os
from datetime import datetime
from typing import Optional

from db_session import db_session
from db_models.scada_connection import ScadaConnection
from db_models.report_config import WindFarm

logger = logging.getLogger(__name__)

_manager_instance: Optional['ScadaManager'] = None
_manager_lock = threading.Lock()
_start_lock = threading.Lock()


class ScadaManager:
    """Manages SCADA connection worker subprocesses."""

    def __init__(self):
        self._processes: dict[int, subprocess.Popen] = {}  # conn_id -> Popen
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._worker_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'scada_worker.py'
        )
        self._backend_url = self._detect_backend_url()
        self._worker_secret = os.environ.get('SCADA_WORKER_SECRET', '')

    def _detect_backend_url(self) -> str:
        """Detect the backend URL for workers to POST data to."""
        host = os.environ.get('APP_HOST', '127.0.0.1')
        if host == '0.0.0.0':
            host = '127.0.0.1'
        port = os.environ.get('APP_PORT', '5000')
        return f'http://{host}:{port}'

    def _get_worker_python(self) -> str:
        """Get the Python executable for worker subprocesses."""
        return sys.executable

    def _build_worker_config(self, conn: ScadaConnection, farm: Optional[WindFarm]) -> dict:
        """Build config dict to pass to worker subprocess."""
        config = {
            'connection_id': conn.id,
            'farm_code': conn.farm_code,
            'name': conn.name,
            'protocol': conn.protocol or 'c104',
            'server_ip': conn.server_ip,
            'server_port': conn.server_port,
            'casdu_address': conn.casdu_address or 1,
            'originator_address': conn.originator_address or 0,
            'ioa_points': json.loads(conn.ioa_points) if conn.ioa_points else {},
            'upload_target_ioa': conn.upload_target_ioa,
            'fetch_interval': conn.fetch_interval or 60,
            'backend_url': self._backend_url,
            'worker_secret': self._worker_secret,
            'capacity': farm.capacity if farm and farm.capacity else 200,
        }
        # Assign farm_index based on alphabetical order for simulation consistency
        with db_session() as db:
            farms = db.query(WindFarm).filter(WindFarm.is_active.is_(True)).order_by(WindFarm.farm_code).all()
            for i, f in enumerate(farms):
                if f.farm_code == conn.farm_code:
                    config['farm_index'] = i
                    break
            else:
                config['farm_index'] = 0
        return config

    def start_connection(self, conn_id: int):
        """Start a worker subprocess for the given connection (thread-safe)."""
        with _start_lock:
            if conn_id in self._processes:
                proc = self._processes[conn_id]
                if proc.poll() is None:
                    raise RuntimeError(f'Connection {conn_id} already has a running worker')

            with db_session() as db:
                conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
                if not conn:
                    raise ValueError(f'Connection {conn_id} not found')

                farm = db.query(WindFarm).filter(WindFarm.farm_code == conn.farm_code).first()
                config = self._build_worker_config(conn, farm)

            config_json = json.dumps(config, ensure_ascii=False)
            python = self._get_worker_python()

            popen_kwargs = {
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
            }
            if sys.platform == 'win32':
                popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                [python, self._worker_script, '--config', config_json],
                **popen_kwargs,
            )

            self._processes[conn_id] = proc
            self._update_db_status(conn_id, 'running', 'Worker started')

            logger.info(f"Started worker for connection {conn_id} (PID={proc.pid}, farm={config['farm_code']})")

            if not self._running:
                self._start_monitor()

    def stop_connection(self, conn_id: int):
        """Stop a worker subprocess."""
        proc = self._processes.pop(conn_id, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            logger.info(f"Stopped worker for connection {conn_id}")

        self._update_db_status(conn_id, 'stopped', 'Manually stopped')

    def restart_connection(self, conn_id: int):
        """Restart a worker subprocess."""
        self.stop_connection(conn_id)
        time.sleep(1)
        self.start_connection(conn_id)

    def start_all_enabled(self):
        """Start all enabled connections that are not already running."""
        with db_session() as db:
            connections = db.query(ScadaConnection).filter(
                ScadaConnection.is_enabled.is_(True)
            ).all()

            for conn in connections:
                if conn.id not in self._processes:
                    try:
                        self.start_connection(conn.id)
                    except Exception as e:
                        logger.error(f"Failed to auto-start connection {conn.id}: {e}")

    def recover_on_startup(self):
        """Auto-restart workers for connections that were running before backend restart.

        Called once at backend startup. Resets stale 'running' statuses, then
        re-spawns workers for all enabled connections that were previously active.
        """
        recovered = 0
        with db_session() as db:
            # Find connections that were running before crash (status still says 'running')
            stale = db.query(ScadaConnection).filter(
                ScadaConnection.status == 'running'
            ).all()

            for conn in stale:
                conn.status = 'stopped'
                conn.status_message = 'Backend restarted, pending recovery'
                logger.info(f"Resetting stale connection {conn.id} ({conn.farm_code})")

            db.commit()

            # Now start all enabled connections
            enabled = db.query(ScadaConnection).filter(
                ScadaConnection.is_enabled.is_(True)
            ).all()

        for conn in enabled:
            try:
                self.start_connection(conn.id)
                recovered += 1
                logger.info(f"Recovered connection {conn.id} ({conn.farm_code})")
            except Exception as e:
                logger.error(f"Failed to recover connection {conn.id}: {e}")

        if recovered:
            logger.info(f"SCADA auto-recovery: started {recovered} worker(s)")
        return recovered

    def stop_all(self):
        """Stop all running workers."""
        conn_ids = list(self._processes.keys())
        for conn_id in conn_ids:
            try:
                self.stop_connection(conn_id)
            except Exception as e:
                logger.error(f"Error stopping connection {conn_id}: {e}")
        self._running = False

    def _start_monitor(self):
        """Start the health monitor thread."""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self):
        """Periodically check worker health and restart dead workers."""
        while self._running:
            try:
                # Collect dead connections with their exit codes
                dead_connections: list[tuple[int, int]] = []
                for conn_id, proc in list(self._processes.items()):
                    if proc.poll() is not None:
                        dead_connections.append((conn_id, proc.poll()))

                for conn_id, exit_code in dead_connections:
                    del self._processes[conn_id]
                    with db_session() as db:
                        conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
                        if conn and conn.is_enabled and conn.status == 'running':
                            logger.info(f"Auto-restarting connection {conn_id}")
                            try:
                                self.start_connection(conn_id)
                            except Exception as e:
                                logger.error(f"Auto-restart failed for {conn_id}: {e}")
                        elif conn:
                            self._update_db_status(conn_id, 'error', f'Worker exited (code {exit_code})')

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            time.sleep(30)

    def _update_db_status(self, conn_id: int, status: str, message: str = ''):
        try:
            with db_session() as db:
                conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
                if conn:
                    conn.status = status
                    conn.status_message = message
                    conn.updated_at = datetime.now()
                    if status == 'running':
                        conn.last_error = None
                    elif status == 'error':
                        conn.last_error = message
                    db.commit()
        except Exception as e:
            logger.error(f"Failed to update status for connection {conn_id}: {e}")

    def update_worker_status(self, conn_id: int, status: str, message: str = '',
                             power_value=None):
        """Called by the worker-status endpoint to update connection status."""
        try:
            with db_session() as db:
                conn = db.query(ScadaConnection).filter(ScadaConnection.id == conn_id).first()
                if conn:
                    conn.status = status
                    conn.status_message = message
                    conn.updated_at = datetime.now()
                    if power_value is not None:
                        conn.last_power_value = power_value
                        conn.last_data_at = datetime.now()
                    if status == 'error':
                        conn.last_error = message
                    db.commit()
        except Exception as e:
            logger.error(f"Failed to update worker status for {conn_id}: {e}")


def get_scada_manager() -> ScadaManager:
    """Get or create the singleton ScadaManager instance."""
    global _manager_instance
    with _manager_lock:
        if _manager_instance is None:
            _manager_instance = ScadaManager()
        return _manager_instance
