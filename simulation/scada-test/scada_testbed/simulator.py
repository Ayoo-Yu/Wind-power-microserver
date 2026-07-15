"""可控制场景的 IEC 60870-5-104 仿真服务器。"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import c104

from .engine import ConfigurationError, ScenarioEngine, load_json


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
LOGGER = logging.getLogger("scada-testbed.simulator")


class SimulatorService:
    def __init__(self) -> None:
        catalog_path = os.environ.get(
            "SCADA_CATALOG_PATH", "/app/config/point-catalog.json"
        )
        scenarios_path = os.environ.get(
            "SCADA_SCENARIOS_PATH", "/app/config/scenarios.json"
        )
        self.catalog = load_json(catalog_path)
        self.engine = ScenarioEngine(self.catalog, load_json(scenarios_path))
        requested = os.environ.get("SCADA_SCENARIO", "").strip()
        if requested:
            self.engine.select(requested)

        self.port = int(os.environ.get("SCADA_PORT", "2404"))
        self.control_port = int(os.environ.get("SCADA_CONTROL_PORT", "8080"))
        self.update_interval = max(
            0.2, float(os.environ.get("SCADA_UPDATE_INTERVAL_SECONDS", "2"))
        )
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._http_server: ThreadingHTTPServer | None = None
        self._server = c104.Server(
            ip="0.0.0.0",
            port=self.port,
            tick_rate_ms=100,
            max_connections=0,
        )
        self._points: dict[tuple[str, str], c104.Point] = {}
        self._last_transmit_count = 0
        self._last_error = ""
        self._started_at = time.time()
        self._build_station()

    def _build_station(self) -> None:
        station = self._server.add_station(
            common_address=int(self.catalog["common_address"])
        )
        if station is None:
            raise RuntimeError("无法创建 C104 station")
        for farm in self.catalog["farms"]:
            for metric, definition in farm["points"].items():
                point_type = getattr(c104.Type, definition["type"], None)
                if point_type is None:
                    raise ConfigurationError(
                        f"C104 库不支持 Type ID: {definition['type']}"
                    )
                point = station.add_point(
                    io_address=int(definition["ioa"]),
                    type=point_type,
                )
                if point is None:
                    raise RuntimeError(f"无法创建 IOA {definition['ioa']}")
                self._points[(farm["farm_code"], metric)] = point

        def on_connect(server: c104.Server, ip: str) -> bool:
            LOGGER.info("C104 客户端连接: %s", ip)
            return True

        on_connect.__annotations__ = {
            "server": c104.Server,
            "ip": str,
            "return": bool,
        }
        self._server.on_connect(callable=on_connect)

    @staticmethod
    def _quality(name: str) -> c104.Quality:
        if name == "Good":
            return c104.Quality(0)
        quality = getattr(c104.Quality, name, None)
        if quality is None:
            raise ConfigurationError(f"不支持的质量码: {name}")
        return quality

    def _apply_frame(self, *, transmit: bool) -> dict[str, Any]:
        with self._lock:
            frame = self.engine.tick()
            quality = self._quality(frame.quality)
            transmitted = 0
            for farm_code, metrics in frame.farms.items():
                for metric, value in metrics.items():
                    point = self._points[(farm_code, metric)]
                    point.value = float(value)
                    point.quality = quality
                    if transmit and frame.transmit and self._server.is_running:
                        if point.transmit(cause=c104.Cot.SPONTANEOUS):
                            transmitted += 1
            self._last_transmit_count = transmitted
            return frame.to_dict()

    def select_scenario(self, name: str) -> dict[str, Any]:
        with self._lock:
            self.engine.select(name)
            return self._apply_frame(transmit=True)

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self.engine.reset()
            return self._apply_frame(transmit=True)

    def set_paused(self, paused: bool) -> dict[str, Any]:
        self.engine.set_paused(paused)
        return self.state()

    def state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "service": "wind-power-scada-testbed",
                "version": "1.0.0",
                "catalog_id": self.catalog["catalog_id"],
                "common_address": self.catalog["common_address"],
                "timestamp_semantics": self.catalog["timestamp_semantics"],
                "server": {
                    "running": bool(self._server.is_running),
                    "port": self.port,
                    "open_connections": int(self._server.open_connection_count),
                    "active_connections": int(self._server.active_connection_count),
                },
                "engine": self.engine.snapshot(),
                "last_transmit_count": self._last_transmit_count,
                "last_error": self._last_error,
                "uptime_seconds": round(time.time() - self._started_at, 3),
            }

    def live(self) -> bool:
        return not self._stop.is_set()

    def ready(self) -> bool:
        snapshot = self.engine.snapshot()
        return bool(self._server.is_running and snapshot["frame"] is not None)

    def start(self) -> None:
        self._apply_frame(transmit=False)
        self._server.start()
        self._start_http_server()
        LOGGER.info(
            "SCADA 测试仿真器已启动，C104=%s，控制接口=%s，场景=%s",
            self.port,
            self.control_port,
            self.engine.scenario,
        )

    def _start_http_server(self) -> None:
        handler = make_handler(self)
        self._http_server = ThreadingHTTPServer(("0.0.0.0", self.control_port), handler)
        self._http_server.daemon_threads = True
        thread = threading.Thread(
            target=self._http_server.serve_forever,
            name="scada-control-api",
            daemon=True,
        )
        thread.start()

    def run(self) -> None:
        self.start()
        while not self._stop.wait(self.update_interval):
            try:
                self._apply_frame(transmit=True)
            except Exception as exc:
                self._last_error = str(exc)
                LOGGER.exception("场景更新失败")

    def stop(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        if self._http_server:
            self._http_server.shutdown()
            self._http_server.server_close()
        if self._server.is_running:
            self._server.stop()
        LOGGER.info("SCADA 测试仿真器已停止")


def make_handler(service: SimulatorService) -> type[BaseHTTPRequestHandler]:
    class ControlHandler(BaseHTTPRequestHandler):
        server_version = "WindPowerScadaTestbed/1.0"

        def log_message(self, format_string: str, *args: Any) -> None:
            LOGGER.debug("HTTP %s", format_string % args)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            if length > 65536:
                raise ValueError("请求体过大")
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("请求体必须是 JSON 对象")
            return raw

        def do_GET(self) -> None:
            if self.path == "/live":
                self._json(HTTPStatus.OK, {"live": service.live()})
            elif self.path == "/ready":
                ready = service.ready()
                self._json(
                    HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ready": ready},
                )
            elif self.path == "/state":
                self._json(HTTPStatus.OK, service.state())
            elif self.path == "/catalog":
                self._json(HTTPStatus.OK, service.catalog)
            elif self.path == "/scenarios":
                self._json(
                    HTTPStatus.OK,
                    {
                        "active": service.engine.scenario,
                        "scenarios": service.engine.available_scenarios(),
                    },
                )
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "endpoint_not_found"})

        def do_POST(self) -> None:
            try:
                body = self._body()
                if self.path == "/scenario":
                    name = str(body.get("name", "")).strip()
                    if not name:
                        raise ValueError("name 不能为空")
                    frame = service.select_scenario(name)
                    self._json(HTTPStatus.OK, {"ok": True, "frame": frame})
                elif self.path == "/reset":
                    frame = service.reset()
                    self._json(HTTPStatus.OK, {"ok": True, "frame": frame})
                elif self.path == "/control":
                    if "paused" not in body:
                        raise ValueError("paused 字段不能为空")
                    state = service.set_paused(bool(body["paused"]))
                    self._json(HTTPStatus.OK, {"ok": True, "state": state})
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "endpoint_not_found"})
            except (ConfigurationError, ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:
                LOGGER.exception("控制请求处理失败")
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    return ControlHandler


def main() -> None:
    service = SimulatorService()

    def handle_signal(signum: int, _frame: Any) -> None:
        LOGGER.info("收到退出信号: %s", signum)
        service.stop()

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)
    try:
        service.run()
    finally:
        service.stop()


if __name__ == "__main__":
    main()
