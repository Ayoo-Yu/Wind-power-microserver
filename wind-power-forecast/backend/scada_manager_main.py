"""SCADA 独立管理服务入口。"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from services.scada_manager import ScadaManager


LOGGER = logging.getLogger("scada-manager")


def _as_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def validate_runtime_config() -> None:
    deployment_mode = os.environ.get("DEPLOYMENT_MODE", "development").strip().lower()
    realtime_enabled = _as_bool(os.environ.get("SCADA_REALTIME_ENABLED", "false"))
    if not realtime_enabled:
        return
    if deployment_mode not in {"development", "test"}:
        if not os.environ.get("SCADA_WORKER_SECRET", "").strip():
            raise RuntimeError("现场模式启用 SCADA 时必须配置 SCADA_WORKER_SECRET")
        if not os.environ.get("SCADA_BACKEND_URL", "").strip():
            raise RuntimeError("现场模式启用 SCADA 时必须配置 SCADA_BACKEND_URL")


def make_health_handler(manager: ScadaManager) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def do_GET(self) -> None:
            snapshot = manager.snapshot()
            if self.path == "/live":
                status = 200
                body = {"live": True, **snapshot}
            elif self.path in {"/ready", "/state"}:
                status = 200 if snapshot["ready"] else 503
                body = snapshot
            else:
                status = 404
                body = {"error": "endpoint_not_found"}
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    )
    validate_runtime_config()
    manager = ScadaManager()
    realtime_enabled = _as_bool(os.environ.get("SCADA_REALTIME_ENABLED", "false"))
    if realtime_enabled:
        recovered = manager.recover_on_startup()
        LOGGER.info("SCADA 管理服务已恢复 %s 个连接", recovered)
    else:
        manager.disable_on_startup()
        manager.start_monitor()
        LOGGER.info("SCADA 实时接入关闭，管理服务保持待命")

    server = ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("SCADA_MANAGER_HEALTH_PORT", "9102"))),
        make_health_handler(manager),
    )
    server.daemon_threads = True
    stopped = threading.Event()

    def stop(_signum: int, _frame: Any) -> None:
        stopped.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        manager.stop_all()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
