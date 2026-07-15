"""生成确定性场站 NWP 长格式 CSV，供离线接入链路开发与故障演练。"""

from __future__ import annotations

import csv
import json
import math
import os
import signal
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .engine import load_json


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


class NwpSimulator:
    def __init__(self) -> None:
        self.catalog = load_json(
            os.environ.get("SCADA_CATALOG_PATH", "/app/config/point-catalog.json")
        )
        self.output_root = Path(
            os.environ.get("NWP_OUTPUT_ROOT", "/artifacts/nwp-inbox")
        )
        self.interval_seconds = max(
            5.0, float(os.environ.get("NWP_UPDATE_INTERVAL_SECONDS", "60"))
        )
        self.horizon_steps = max(8, int(os.environ.get("NWP_HORIZON_STEPS", "96")))
        self.scenario = os.environ.get("NWP_SCENARIO", "normal")
        self.running = True
        self.sequence = 0
        self.last_generated_at: str | None = None
        self.last_files: list[str] = []
        self._lock = threading.RLock()

    @staticmethod
    def _forecast_source(now: datetime) -> datetime:
        hour = (now.hour // 6) * 6
        return now.replace(hour=hour, minute=0, second=0, microsecond=0)

    def _rows(self, farm: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
        source = self._forecast_source(now)
        farm_index = next(
            index
            for index, item in enumerate(self.catalog["farms"])
            if item["farm_code"] == farm["farm_code"]
        )
        rows = []
        for step in range(self.horizon_steps):
            forecast_time = source + timedelta(minutes=15 * step)
            phase = step / 10.0 + farm_index * 0.7
            for grid_index in range(4):
                latitude = round(23.80 + farm_index * 0.04 + (grid_index // 2) * 0.05, 4)
                longitude = round(103.20 + farm_index * 0.04 + (grid_index % 2) * 0.05, 4)
                speed = 5.5 + 2.0 * math.sin(phase) + grid_index * 0.15
                direction = 0.6 + farm_index * 0.2 + grid_index * 0.1
                u100 = speed * math.sin(direction)
                v100 = speed * math.cos(direction)
                temperature = 287.15 + 4.0 * math.sin(step / 48.0)
                if self.scenario == "missing" and step % 7 == 0 and grid_index == 0:
                    u100 = ""
                rows.append(
                    {
                        "forecast_source": source.isoformat(),
                        "forecast_time": forecast_time.isoformat(),
                        "latitude": latitude,
                        "longitude": longitude,
                        "100u": u100,
                        "100v": v100,
                        "10u": float(u100) * 0.72 if u100 != "" else "",
                        "10v": v100 * 0.72,
                        "2t": temperature,
                        "2d": temperature - 2.5,
                        "sp": 101325 + 220 * math.cos(step / 48.0),
                    }
                )
        if self.scenario == "malformed" and rows:
            rows[0]["forecast_time"] = "invalid-time"
        return rows

    def generate(self) -> list[str]:
        with self._lock:
            if self.scenario == "stale":
                return []
            now = datetime.now(BEIJING_TZ).replace(microsecond=0)
            created = []
            for farm in self.catalog["farms"]:
                farm_dir = self.output_root / farm["farm_code"]
                farm_dir.mkdir(parents=True, exist_ok=True)
                rows = self._rows(farm, now)
                final_path = farm_dir / f"nwp_{farm['farm_code']}_{now:%Y%m%dT%H%M%S}.csv"
                temporary = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")
                with temporary.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, final_path)
                created.append(str(final_path))
            self.sequence += 1
            self.last_generated_at = now.isoformat()
            self.last_files = created
            return created

    def state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ready": True,
                "scenario": self.scenario,
                "sequence": self.sequence,
                "last_generated_at": self.last_generated_at,
                "last_files": list(self.last_files),
                "farm_count": len(self.catalog["farms"]),
                "horizon_steps": self.horizon_steps,
            }

    def run(self) -> None:
        next_run = 0.0
        while self.running:
            if time.monotonic() >= next_run:
                self.generate()
                next_run = time.monotonic() + self.interval_seconds
            time.sleep(0.2)


def make_handler(simulator: NwpSimulator) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in {"/health", "/ready", "/state"}:
                self._json(200, simulator.state())
            else:
                self._json(404, {"error": "endpoint_not_found"})

        def do_POST(self) -> None:
            if self.path == "/generate":
                self._json(200, {"files": simulator.generate(), **simulator.state()})
                return
            if self.path != "/scenario":
                self._json(404, {"error": "endpoint_not_found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
            scenario = str(raw.get("name") or "")
            if scenario not in {"normal", "missing", "malformed", "stale"}:
                self._json(400, {"error": "unsupported_scenario"})
                return
            simulator.scenario = scenario
            self._json(200, simulator.state())

    return Handler


def main() -> None:
    simulator = NwpSimulator()
    server = ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("NWP_CONTROL_PORT", "8084"))),
        make_handler(simulator),
    )
    server.daemon_threads = True
    worker = threading.Thread(target=simulator.run, daemon=True)
    worker.start()

    def stop(_signum: int, _frame: Any) -> None:
        simulator.running = False
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        simulator.running = False
        server.server_close()


if __name__ == "__main__":
    main()
