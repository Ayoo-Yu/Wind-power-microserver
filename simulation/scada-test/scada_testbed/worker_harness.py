"""使用真实 scada_worker.py 启动多场站采集进程。"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .engine import load_json, validate_catalog


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
LOGGER = logging.getLogger("scada-testbed.worker-harness")


class WorkerHarness:
    def __init__(self) -> None:
        catalog = load_json(
            os.environ.get("SCADA_CATALOG_PATH", "/app/config/point-catalog.json")
        )
        validate_catalog(catalog)
        self.catalog = catalog
        self.worker_path = Path(
            os.environ.get("SCADA_WORKER_PATH", "/app/production/scada_worker.py")
        )
        self.server_host = os.environ.get("SCADA_WORKER_SERVER_HOST", "fault-proxy")
        self.server_port = int(os.environ.get("SCADA_WORKER_SERVER_PORT", "2405"))
        self.backend_url = os.environ.get(
            "SCADA_WORKER_BACKEND_URL", "http://mock-ingress:8090"
        ).rstrip("/")
        self.fetch_interval = int(os.environ.get("SCADA_WORKER_FETCH_INTERVAL", "2"))
        self.processes: dict[str, subprocess.Popen] = {}
        self.running = True

    def _config(self, farm: dict[str, Any], index: int) -> dict[str, Any]:
        point = farm["points"]["active_power_mw"]
        return {
            "connection_id": index + 1,
            "farm_code": farm["farm_code"],
            "name": f"{farm['name']} SCADA 测试连接",
            "protocol": "c104",
            "server_ip": self.server_host,
            "server_port": self.server_port,
            "casdu_address": int(self.catalog["common_address"]),
            "originator_address": int(self.catalog.get("originator_address", 0)),
            "ioa_points": {str(point["ioa"]): point["type"]},
            "upload_target_ioa": int(point["ioa"]),
            "fetch_interval": self.fetch_interval,
            "backend_url": self.backend_url,
            "capacity": float(farm["capacity_mw"]),
            "farm_index": index,
            "timestamp_policy": "receive_time",
        }

    def _start(self, farm: dict[str, Any], index: int) -> None:
        config = self._config(farm, index)
        process = subprocess.Popen(
            [sys.executable, str(self.worker_path), "--config", json.dumps(config)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        self.processes[farm["farm_code"]] = process
        LOGGER.info("启动真实采集 Worker: %s，PID=%s", farm["farm_code"], process.pid)

    def run(self) -> None:
        if not self.worker_path.is_file():
            raise FileNotFoundError(f"找不到生产采集脚本: {self.worker_path}")
        for index, farm in enumerate(self.catalog["farms"]):
            self._start(farm, index)
        while self.running:
            for index, farm in enumerate(self.catalog["farms"]):
                code = farm["farm_code"]
                process = self.processes.get(code)
                if process and process.poll() is not None:
                    LOGGER.warning("Worker %s 已退出，返回码=%s，准备重启", code, process.returncode)
                    if self.running:
                        time.sleep(1)
                        self._start(farm, index)
            time.sleep(0.5)

    def stop(self) -> None:
        self.running = False
        for process in self.processes.values():
            if process.poll() is None:
                process.terminate()
        deadline = time.time() + 8
        for process in self.processes.values():
            remaining = max(0.1, deadline - time.time())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> None:
    harness = WorkerHarness()

    def stop(_signum: int, _frame: Any) -> None:
        harness.stop()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    try:
        harness.run()
    finally:
        harness.stop()


if __name__ == "__main__":
    main()
