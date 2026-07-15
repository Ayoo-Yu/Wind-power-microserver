"""用于独立测试的实际功率接收端。"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
LOGGER = logging.getLogger("scada-testbed.mock-ingress")


class EventStore:
    def __init__(self, event_path: str | Path) -> None:
        self.path = Path(event_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._deliveries: list[dict[str, Any]] = []
        self._latest: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._worker_status: dict[str, dict[str, Any]] = {}
        self._response_status = 200
        self._failure_remaining = 0
        self._sequence = 0
        self._started_at = time.time()

    def configure(self, raw: dict[str, Any]) -> dict[str, int]:
        allowed = {"response_status", "failure_count"}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"未知控制字段: {', '.join(sorted(unknown))}")
        status = raw.get("response_status", self._response_status)
        failure_count = raw.get("failure_count", self._failure_remaining)
        if not isinstance(status, int) or not 100 <= status <= 599:
            raise ValueError("response_status 必须位于 100 至 599")
        if not isinstance(failure_count, int) or failure_count < 0:
            raise ValueError("failure_count 必须是非负整数")
        with self._lock:
            self._response_status = status
            self._failure_remaining = failure_count
            return {
                "response_status": self._response_status,
                "failure_count": self._failure_remaining,
            }

    def should_fail(self) -> int | None:
        with self._lock:
            if self._failure_remaining <= 0:
                return None
            self._failure_remaining -= 1
            return self._response_status

    def add_power(self, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        required = {"Timestamp", "farm_code", "wp_true"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"缺少字段: {', '.join(missing)}")
        farm_code = payload["farm_code"]
        if not isinstance(farm_code, str) or not farm_code.strip():
            raise ValueError("farm_code 无效")
        try:
            timestamp = datetime.fromisoformat(str(payload["Timestamp"]))
            power = float(payload["wp_true"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Timestamp 或 wp_true 无效") from exc

        key = (farm_code.strip(), timestamp.isoformat(), "active_power_mw")
        with self._lock:
            action = "updated" if key in self._latest else "created"
            self._sequence += 1
            event = {
                "delivery_sequence": self._sequence,
                "received_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                "Timestamp": timestamp.isoformat(),
                "farm_code": farm_code.strip(),
                "wp_true": round(power, 6),
                "metric": "active_power_mw",
                "action": action,
            }
            self._deliveries.append(event)
            self._deliveries = self._deliveries[-20000:]
            self._latest[key] = event
            serialized = json.dumps(event, ensure_ascii=False, sort_keys=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized + "\n")
                handle.flush()
            return action, event

    def add_worker_status(self, payload: dict[str, Any]) -> None:
        connection_id = str(payload.get("connection_id", "")).strip()
        if not connection_id:
            raise ValueError("connection_id 不能为空")
        with self._lock:
            self._worker_status[connection_id] = {
                **payload,
                "received_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            }

    def add_ingest(self, payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
        required = {"connection_id", "farm_code", "quality"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"缺少字段: {', '.join(missing)}")
        quality = str(payload.get("quality", "unknown")).lower()
        metric = str(payload.get("metric") or "active_power_mw")
        value = payload.get("value", payload.get("power_mw"))
        if quality != "good" or value is None:
            event = {
                "connection_id": payload.get("connection_id"),
                "farm_code": payload.get("farm_code"),
                "quality": quality,
                "metric": metric,
                "outcome": "rejected",
                "message": "模拟接收端拒绝无效质量样本",
            }
            return False, "rejected", event

        timestamp = payload.get("normalized_timestamp") or payload.get("source_timestamp")
        if not timestamp:
            timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        if metric == "active_power_mw":
            action, event = self.add_power({
                "Timestamp": timestamp,
                "farm_code": payload["farm_code"],
                "wp_true": value,
            })
        else:
            key = (str(payload["farm_code"]), str(timestamp), metric)
            with self._lock:
                action = "updated" if key in self._latest else "created"
                self._sequence += 1
                event = {
                    "delivery_sequence": self._sequence,
                    "received_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                    "Timestamp": str(timestamp),
                    "farm_code": str(payload["farm_code"]),
                    "metric": metric,
                    "value": float(value),
                    "unit": payload.get("unit"),
                    "action": action,
                }
                self._deliveries.append(event)
                self._deliveries = self._deliveries[-20000:]
                self._latest[key] = event
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()
        event.update({
            "connection_id": payload.get("connection_id"),
            "ioa": payload.get("ioa"),
            "quality": quality,
            "outcome": action,
        })
        return True, action, event

    def reset(self) -> None:
        with self._lock:
            self._deliveries.clear()
            self._latest.clear()
            self._worker_status.clear()
            self._response_status = 200
            self._failure_remaining = 0
            self._sequence = 0
            self.path.write_text("", encoding="utf-8")

    def events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._deliveries[-max(1, min(limit, 2000)):])

    def stats(self) -> dict[str, Any]:
        with self._lock:
            farms = sorted({event["farm_code"] for event in self._deliveries})
            return {
                "service": "wind-power-scada-mock-ingress",
                "version": "1.0.0",
                "deliveries": len(self._deliveries),
                "unique_records": len(self._latest),
                "farm_codes": farms,
                "worker_status": dict(self._worker_status),
                "response_status": self._response_status,
                "failure_remaining": self._failure_remaining,
                "uptime_seconds": round(time.time() - self._started_at, 3),
            }


def make_handler(store: EventStore) -> type[BaseHTTPRequestHandler]:
    class IngressHandler(BaseHTTPRequestHandler):
        server_version = "WindPowerScadaMockIngress/1.0"

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
            if length <= 0 or length > 1048576:
                raise ValueError("请求体长度无效")
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("请求体必须是 JSON 对象")
            return raw

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._json(HTTPStatus.OK, {"status": "healthy"})
            elif parsed.path == "/stats":
                self._json(HTTPStatus.OK, store.stats())
            elif parsed.path == "/events":
                query = parse_qs(parsed.query)
                try:
                    limit = int(query.get("limit", ["200"])[0])
                except ValueError:
                    limit = 200
                self._json(HTTPStatus.OK, {"events": store.events(limit)})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "endpoint_not_found"})

        def do_POST(self) -> None:
            try:
                if self.path == "/actual_power/":
                    failure = store.should_fail()
                    if failure is not None:
                        self._json(failure, {"error": "injected_downstream_failure"})
                        return
                    action, event = store.add_power(self._body())
                    self._json(HTTPStatus.OK, {"success": True, "action": action, "data": event})
                elif self.path == "/api/v1/scada/ingest":
                    failure = store.should_fail()
                    if failure is not None:
                        self._json(failure, {"error": "injected_downstream_failure"})
                        return
                    accepted, outcome, event = store.add_ingest(self._body())
                    status = HTTPStatus.OK if accepted else HTTPStatus.UNPROCESSABLE_ENTITY
                    self._json(status, {
                        "accepted": accepted,
                        "outcome": outcome,
                        "message": event.get("message", "模拟接收端已处理"),
                        "data": event,
                    })
                elif self.path == "/scada/worker-status":
                    store.add_worker_status(self._body())
                    self._json(HTTPStatus.OK, {"success": True})
                elif self.path == "/control":
                    settings = store.configure(self._body())
                    self._json(HTTPStatus.OK, {"ok": True, "settings": settings})
                elif self.path == "/reset":
                    store.reset()
                    self._json(HTTPStatus.OK, {"ok": True})
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "endpoint_not_found"})
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:
                LOGGER.exception("接收端请求处理失败")
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    return IngressHandler


def main() -> None:
    port = int(os.environ.get("MOCK_INGRESS_PORT", "8090"))
    event_path = os.environ.get(
        "MOCK_INGRESS_EVENT_PATH", "/artifacts/ingress-events.jsonl"
    )
    store = EventStore(event_path)
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(store))
    server.daemon_threads = True

    def stop(_signum: int, _frame: Any) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    LOGGER.info("模拟实际功率接收端已启动，端口=%s，事件文件=%s", port, event_path)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
