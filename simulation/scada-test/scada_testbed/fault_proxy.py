"""面向 C104 链路的可控制 TCP 故障代理。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import signal
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
LOGGER = logging.getLogger("scada-testbed.fault-proxy")


@dataclass
class FaultSettings:
    enabled: bool = True
    latency_ms: int = 0
    jitter_ms: int = 0
    bandwidth_kbps: int = 0
    close_after_bytes: int = 0


class FaultState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.settings = FaultSettings()
        self.started_at = time.time()
        self.accepted_connections = 0
        self.failed_upstream_connections = 0
        self.bytes_upstream = 0
        self.bytes_downstream = 0
        self.active_connections: dict[str, tuple[asyncio.StreamWriter, asyncio.StreamWriter]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def configure(self, raw: dict[str, Any]) -> FaultSettings:
        allowed = {
            "enabled",
            "latency_ms",
            "jitter_ms",
            "bandwidth_kbps",
            "close_after_bytes",
        }
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"未知故障字段: {', '.join(sorted(unknown))}")
        with self._lock:
            current = asdict(self.settings)
            current.update(raw)
            enabled = current["enabled"]
            if not isinstance(enabled, bool):
                raise ValueError("enabled 必须是布尔值")
            for field_name in (
                "latency_ms",
                "jitter_ms",
                "bandwidth_kbps",
                "close_after_bytes",
            ):
                value = current[field_name]
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError(f"{field_name} 必须是非负整数")
            if current["latency_ms"] > 60000 or current["jitter_ms"] > 60000:
                raise ValueError("延迟和抖动不能超过 60000 毫秒")
            self.settings = FaultSettings(**current)
            configured = FaultSettings(**asdict(self.settings))
        if not configured.enabled:
            self.disconnect_active()
        return configured

    def reset(self) -> FaultSettings:
        with self._lock:
            self.settings = FaultSettings()
        self.disconnect_active()
        return FaultSettings()

    def snapshot_settings(self) -> FaultSettings:
        with self._lock:
            return FaultSettings(**asdict(self.settings))

    def register(
        self,
        connection_id: str,
        downstream: asyncio.StreamWriter,
        upstream: asyncio.StreamWriter,
    ) -> None:
        with self._lock:
            self.accepted_connections += 1
            self.active_connections[connection_id] = (downstream, upstream)

    def unregister(self, connection_id: str) -> None:
        with self._lock:
            self.active_connections.pop(connection_id, None)

    def add_bytes(self, direction: str, amount: int) -> None:
        with self._lock:
            if direction == "upstream":
                self.bytes_upstream += amount
            else:
                self.bytes_downstream += amount

    def disconnect_active(self) -> None:
        with self._lock:
            writers = [writer for pair in self.active_connections.values() for writer in pair]
            loop = self.loop
        if not loop or loop.is_closed():
            return
        for writer in writers:
            loop.call_soon_threadsafe(writer.close)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "service": "wind-power-scada-fault-proxy",
                "version": "1.0.0",
                "settings": asdict(self.settings),
                "metrics": {
                    "active_connections": len(self.active_connections),
                    "accepted_connections": self.accepted_connections,
                    "failed_upstream_connections": self.failed_upstream_connections,
                    "bytes_upstream": self.bytes_upstream,
                    "bytes_downstream": self.bytes_downstream,
                    "uptime_seconds": round(time.time() - self.started_at, 3),
                },
            }


class FaultProxy:
    def __init__(self) -> None:
        self.listen_host = os.environ.get("PROXY_LISTEN_HOST", "0.0.0.0")
        self.listen_port = int(os.environ.get("PROXY_LISTEN_PORT", "2405"))
        self.upstream_host = os.environ.get("PROXY_UPSTREAM_HOST", "scada-simulator")
        self.upstream_port = int(os.environ.get("PROXY_UPSTREAM_PORT", "2404"))
        self.control_port = int(os.environ.get("PROXY_CONTROL_PORT", "8081"))
        self.state = FaultState()
        self._stop = asyncio.Event()
        self._server: asyncio.AbstractServer | None = None
        self._http_server: ThreadingHTTPServer | None = None

    async def _pump(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        connection_id: str,
        direction: str,
    ) -> None:
        transferred = 0
        rng = random.Random(f"{connection_id}:{direction}")
        while True:
            data = await reader.read(65536)
            if not data:
                return
            settings = self.state.snapshot_settings()
            if not settings.enabled:
                return
            delay_ms = settings.latency_ms
            if settings.jitter_ms:
                delay_ms += rng.randint(0, settings.jitter_ms)
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000.0)
            if settings.bandwidth_kbps:
                await asyncio.sleep(len(data) / (settings.bandwidth_kbps * 1024.0))
            writer.write(data)
            await writer.drain()
            transferred += len(data)
            self.state.add_bytes(direction, len(data))
            if settings.close_after_bytes and transferred >= settings.close_after_bytes:
                return

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        connection_id = uuid.uuid4().hex
        peer = writer.get_extra_info("peername")
        if not self.state.snapshot_settings().enabled:
            writer.close()
            await writer.wait_closed()
            return
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(
                self.upstream_host, self.upstream_port
            )
        except Exception as exc:
            with self.state._lock:
                self.state.failed_upstream_connections += 1
            LOGGER.warning("上游连接失败 %s:%s: %s", self.upstream_host, self.upstream_port, exc)
            writer.close()
            await writer.wait_closed()
            return

        self.state.register(connection_id, writer, upstream_writer)
        LOGGER.info("代理连接建立: %s，客户端=%s", connection_id[:8], peer)
        try:
            tasks = {
                asyncio.create_task(
                    self._pump(
                        reader,
                        upstream_writer,
                        connection_id=connection_id,
                        direction="upstream",
                    )
                ),
                asyncio.create_task(
                    self._pump(
                        upstream_reader,
                        writer,
                        connection_id=connection_id,
                        direction="downstream",
                    )
                ),
            }
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)
        finally:
            self.state.unregister(connection_id)
            for stream in (writer, upstream_writer):
                stream.close()
            await asyncio.gather(
                writer.wait_closed(), upstream_writer.wait_closed(), return_exceptions=True
            )
            LOGGER.info("代理连接关闭: %s", connection_id[:8])

    def _start_control_api(self) -> None:
        self._http_server = ThreadingHTTPServer(
            ("0.0.0.0", self.control_port), make_handler(self.state)
        )
        self._http_server.daemon_threads = True
        threading.Thread(
            target=self._http_server.serve_forever,
            name="fault-proxy-control",
            daemon=True,
        ).start()

    async def run(self) -> None:
        self.state.loop = asyncio.get_running_loop()
        self._server = await asyncio.start_server(
            self._handle, self.listen_host, self.listen_port
        )
        self._start_control_api()
        LOGGER.info(
            "故障代理已启动，监听=%s:%s，上游=%s:%s，控制接口=%s",
            self.listen_host,
            self.listen_port,
            self.upstream_host,
            self.upstream_port,
            self.control_port,
        )
        async with self._server:
            await self._stop.wait()

    def stop(self) -> None:
        if not self._stop.is_set():
            self._stop.set()
        self.state.disconnect_active()
        if self._http_server:
            self._http_server.shutdown()
            self._http_server.server_close()


def make_handler(state: FaultState) -> type[BaseHTTPRequestHandler]:
    class ControlHandler(BaseHTTPRequestHandler):
        server_version = "WindPowerScadaFaultProxy/1.0"

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
            if length > 65536:
                raise ValueError("请求体过大")
            if not length:
                return {}
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("请求体必须是 JSON 对象")
            return raw

        def do_GET(self) -> None:
            if self.path == "/live":
                self._json(HTTPStatus.OK, {"live": True})
            elif self.path == "/state":
                self._json(HTTPStatus.OK, state.snapshot())
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "endpoint_not_found"})

        def do_POST(self) -> None:
            try:
                if self.path == "/fault":
                    settings = state.configure(self._body())
                    self._json(HTTPStatus.OK, {"ok": True, "settings": asdict(settings)})
                elif self.path == "/reset":
                    settings = state.reset()
                    self._json(HTTPStatus.OK, {"ok": True, "settings": asdict(settings)})
                elif self.path == "/disconnect":
                    state.disconnect_active()
                    self._json(HTTPStatus.OK, {"ok": True})
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "endpoint_not_found"})
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:
                LOGGER.exception("故障控制请求失败")
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    return ControlHandler


async def async_main() -> None:
    proxy = FaultProxy()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, proxy.stop)
        except NotImplementedError:
            pass
    try:
        await proxy.run()
    finally:
        proxy.stop()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
