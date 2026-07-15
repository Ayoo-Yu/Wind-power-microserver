"""C104 点表探针与协议验收工具。"""

from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import c104

from .engine import load_json, validate_catalog


class ProbeError(RuntimeError):
    """协议探针未在限定时间内获得有效结果。"""


def collect_snapshot(
    *,
    catalog: dict[str, Any],
    host: str,
    port: int,
    timeout_seconds: float = 12.0,
) -> dict[str, Any]:
    validate_catalog(catalog)
    expected: dict[int, dict[str, Any]] = {}
    for farm in catalog["farms"]:
        for metric, definition in farm["points"].items():
            expected[int(definition["ioa"])] = {
                "farm_code": farm["farm_code"],
                "metric": metric,
                "capacity_mw": float(farm["capacity_mw"]),
                **definition,
            }

    events: dict[int, dict[str, Any]] = {}
    lock = threading.RLock()
    complete = threading.Event()
    started = time.monotonic()
    try:
        resolved_host = socket.gethostbyname(host)
    except socket.gaierror as exc:
        raise ProbeError(f"无法解析 C104 主机: {host}") from exc
    client = c104.Client(tick_rate_ms=50, command_timeout_ms=5000)
    connection = client.add_connection(
        ip=resolved_host, port=int(port), init=c104.Init.MUTED
    )
    if connection is None:
        raise ProbeError(f"无法创建 C104 连接: {host}:{port}")
    station = connection.add_station(common_address=int(catalog["common_address"]))
    if station is None:
        raise ProbeError(f"无法创建 CASDU {catalog['common_address']}")

    def on_measurement(point, previous_info, message):
        quality = getattr(point, "quality", None)
        recorded_at = getattr(point, "recorded_at", None)
        quality_good = bool(quality is None or quality.is_good())
        event = {
            "ioa": int(point.io_address),
            "type": str(point.type.name),
            "value": float(point.value),
            "quality": "Good" if quality_good else str(quality.name),
            "quality_good": quality_good,
            "recorded_at": recorded_at.isoformat() if recorded_at else None,
            "received_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        }
        with lock:
            events[event["ioa"]] = event
            if set(events) >= set(expected):
                complete.set()
        return c104.ResponseState.SUCCESS

    on_measurement.__annotations__ = {
        "point": c104.Point,
        "previous_info": c104.Information,
        "message": c104.IncomingMessage,
        "return": c104.ResponseState,
    }

    for ioa, definition in expected.items():
        point_type = getattr(c104.Type, str(definition["type"]), None)
        if point_type is None:
            raise ProbeError(f"C104 库不支持 Type ID: {definition['type']}")
        point = station.add_point(io_address=ioa, type=point_type)
        if point is None:
            raise ProbeError(f"无法创建探针 IOA: {ioa}")
        point.on_receive(callable=on_measurement)

    try:
        client.start()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline and not connection.is_connected:
            time.sleep(0.05)
        if not connection.is_connected:
            raise ProbeError(f"C104 连接超时: {host}:{port}")
        if getattr(connection, "is_muted", False):
            connection.unmute()
        connection.interrogation(
            common_address=int(catalog["common_address"]),
            qualifier=c104.Qoi.STATION,
            wait_for_response=False,
        )
        remaining = max(0.0, deadline - time.monotonic())
        complete.wait(remaining)
        with lock:
            missing = sorted(set(expected) - set(events))
            snapshot = [
                {**expected[ioa], **events[ioa]}
                for ioa in sorted(events)
                if ioa in expected
            ]
        if missing:
            raise ProbeError(f"未收到全部点位，缺少 IOA: {missing}")
        return {
            "host": host,
            "resolved_host": resolved_host,
            "port": int(port),
            "common_address": int(catalog["common_address"]),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "point_count": len(snapshot),
            "points": snapshot,
        }
    finally:
        client.stop()


def validate_snapshot(snapshot: dict[str, Any], *, expect_quality: str = "good") -> None:
    points = snapshot.get("points", [])
    if not points:
        raise ProbeError("探针结果中没有点位")
    by_farm: dict[str, dict[str, float]] = {}
    for point in points:
        quality_good = bool(point["quality_good"])
        if expect_quality == "good" and not quality_good:
            raise ProbeError(f"IOA {point['ioa']} 出现坏质量码: {point['quality']}")
        if expect_quality == "bad" and quality_good:
            raise ProbeError(f"IOA {point['ioa']} 未携带预期的坏质量码")
        by_farm.setdefault(point["farm_code"], {})[point["metric"]] = float(point["value"])

    for farm_code, values in by_farm.items():
        required = {
            "active_power_mw",
            "wind_speed_mps",
            "theoretical_power_mw",
            "available_power_mw",
            "availability_pct",
        }
        missing = required - set(values)
        if missing:
            raise ProbeError(f"{farm_code} 缺少指标: {', '.join(sorted(missing))}")
        if values["active_power_mw"] < 0 or values["theoretical_power_mw"] < 0:
            raise ProbeError(f"{farm_code} 出现负功率")
        if not 0 <= values["availability_pct"] <= 100:
            raise ProbeError(f"{farm_code} 可用率越界")
        tolerance = max(0.5, values["available_power_mw"] * 0.02)
        if values["active_power_mw"] > values["available_power_mw"] + tolerance:
            raise ProbeError(f"{farm_code} 实发功率超过可用功率")


def main() -> None:
    parser = argparse.ArgumentParser(description="C104 点表协议探针")
    parser.add_argument("--catalog", default="/app/config/point-catalog.json")
    parser.add_argument("--host", default=os.environ.get("SCADA_PROBE_HOST", "fault-proxy"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SCADA_PROBE_PORT", "2405")))
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--expect-quality", choices=("good", "bad", "any"), default="good")
    parser.add_argument("--output")
    args = parser.parse_args()
    catalog = load_json(args.catalog)
    snapshot = collect_snapshot(
        catalog=catalog,
        host=args.host,
        port=args.port,
        timeout_seconds=args.timeout,
    )
    if args.expect_quality != "any":
        validate_snapshot(snapshot, expect_quality=args.expect_quality)
    rendered = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
