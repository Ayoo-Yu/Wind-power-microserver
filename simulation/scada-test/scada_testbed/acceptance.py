"""独立 SCADA 测试环境的端到端验收套件。"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .engine import load_json
from .probe import collect_snapshot, validate_snapshot


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    raw = json.loads(body) if body else {}
    if not isinstance(raw, dict):
        raise RuntimeError(f"接口未返回 JSON 对象: {url}")
    return raw


def wait_for(
    description: str,
    callback: Callable[[], Any],
    predicate: Callable[[Any], bool],
    timeout_seconds: float,
    interval_seconds: float = 0.25,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last_value: Any = None
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            last_value = callback()
            if predicate(last_value):
                return last_value
        except Exception as exc:
            last_error = exc
        time.sleep(interval_seconds)
    detail = f"，最后结果={last_value!r}" if last_value is not None else ""
    if last_error:
        detail += f"，最后错误={last_error}"
    raise TimeoutError(f"等待超时: {description}{detail}")


class AcceptanceSuite:
    def __init__(self) -> None:
        self.simulator_url = os.environ.get(
            "SCADA_SIMULATOR_CONTROL_URL", "http://scada-simulator:8080"
        ).rstrip("/")
        self.proxy_url = os.environ.get(
            "SCADA_PROXY_CONTROL_URL", "http://fault-proxy:8081"
        ).rstrip("/")
        self.ingress_url = os.environ.get(
            "SCADA_MOCK_INGRESS_URL", "http://mock-ingress:8090"
        ).rstrip("/")
        self.nwp_url = os.environ.get(
            "NWP_SIMULATOR_CONTROL_URL", "http://nwp-simulator:8084"
        ).rstrip("/")
        self.proxy_host = os.environ.get("SCADA_PROBE_HOST", "fault-proxy")
        self.proxy_port = int(os.environ.get("SCADA_PROBE_PORT", "2405"))
        self.catalog = load_json(
            os.environ.get("SCADA_CATALOG_PATH", "/app/config/point-catalog.json")
        )
        self.output_path = Path(
            os.environ.get("SCADA_ACCEPTANCE_REPORT", "/artifacts/acceptance-report.json")
        )
        self.results: list[dict[str, Any]] = []
        self.started_at = datetime.now(timezone.utc)

    def record(self, name: str, callback: Callable[[], Any]) -> None:
        started = time.monotonic()
        try:
            details = callback()
            self.results.append(
                {
                    "name": name,
                    "passed": True,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "details": details,
                }
            )
            print(f"[通过] {name}", flush=True)
        except Exception as exc:
            self.results.append(
                {
                    "name": name,
                    "passed": False,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            print(f"[失败] {name}: {exc}", flush=True)

    def readiness(self) -> dict[str, Any]:
        simulator = wait_for(
            "仿真器就绪",
            lambda: request_json("GET", f"{self.simulator_url}/ready"),
            lambda value: value.get("ready") is True,
            40,
        )
        proxy = wait_for(
            "故障代理就绪",
            lambda: request_json("GET", f"{self.proxy_url}/live"),
            lambda value: value.get("live") is True,
            20,
        )
        ingress = wait_for(
            "模拟接收端就绪",
            lambda: request_json("GET", f"{self.ingress_url}/health"),
            lambda value: value.get("status") == "healthy",
            20,
        )
        nwp = wait_for(
            "NWP 仿真器就绪",
            lambda: request_json("GET", f"{self.nwp_url}/ready"),
            lambda value: value.get("ready") is True,
            20,
        )
        return {"simulator": simulator, "proxy": proxy, "ingress": ingress, "nwp": nwp}

    def normal_protocol(self) -> dict[str, Any]:
        request_json("POST", f"{self.proxy_url}/reset", {})
        request_json("POST", f"{self.simulator_url}/scenario", {"name": "normal"})
        snapshot = collect_snapshot(
            catalog=self.catalog,
            host=self.proxy_host,
            port=self.proxy_port,
            timeout_seconds=15,
        )
        validate_snapshot(snapshot, expect_quality="good")
        expected = sum(len(farm["points"]) for farm in self.catalog["farms"])
        if snapshot["point_count"] != expected:
            raise RuntimeError(
                f"点位数量不符，期望 {expected}，收到 {snapshot['point_count']}"
            )
        return {
            "point_count": snapshot["point_count"],
            "elapsed_seconds": snapshot["elapsed_seconds"],
        }

    def production_worker_path(self) -> dict[str, Any]:
        request_json("POST", f"{self.ingress_url}/reset", {})
        expected_farms = sorted(farm["farm_code"] for farm in self.catalog["farms"])
        expected_metrics = sorted({
            metric
            for farm in self.catalog["farms"]
            for metric in farm["points"]
        })

        def worker_snapshot() -> dict[str, Any]:
            stats = request_json("GET", f"{self.ingress_url}/stats")
            events = request_json("GET", f"{self.ingress_url}/events?limit=2000").get("events", [])
            metrics_by_farm = {
                farm_code: sorted({
                    str(event.get("metric"))
                    for event in events
                    if event.get("farm_code") == farm_code
                })
                for farm_code in expected_farms
            }
            return {**stats, "metrics_by_farm": metrics_by_farm}

        stats = wait_for(
            "真实 scada_worker 上送全部场站和五类指标",
            worker_snapshot,
            lambda value: (
                value.get("farm_codes") == expected_farms
                and all(
                    value.get("metrics_by_farm", {}).get(farm_code) == expected_metrics
                    for farm_code in expected_farms
                )
            ),
            25,
            0.5,
        )
        return {
            "farm_codes": stats["farm_codes"],
            "metrics": expected_metrics,
            "deliveries": stats["deliveries"],
            "worker_count": len(stats.get("worker_status", {})),
        }

    @staticmethod
    def _read_nwp_rows(file_path: str) -> list[dict[str, str]]:
        with Path(file_path).open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def nwp_packages(self) -> dict[str, Any]:
        request_json("POST", f"{self.nwp_url}/scenario", {"name": "normal"})
        normal = request_json("POST", f"{self.nwp_url}/generate", {})
        files = normal.get("files") or []
        if len(files) != len(self.catalog["farms"]):
            raise RuntimeError("NWP 正常场景没有为全部场站生成文件")
        expected_rows = int(normal["horizon_steps"]) * 4
        for file_path in files:
            rows = self._read_nwp_rows(file_path)
            if len(rows) != expected_rows:
                raise RuntimeError(f"NWP 文件行数不符: {file_path}")
            required = {"forecast_source", "forecast_time", "100u", "100v", "2t", "sp"}
            if not rows or not required.issubset(rows[0]):
                raise RuntimeError(f"NWP 文件字段不完整: {file_path}")

        request_json("POST", f"{self.nwp_url}/scenario", {"name": "missing"})
        missing = request_json("POST", f"{self.nwp_url}/generate", {})
        missing_rows = self._read_nwp_rows(missing["files"][0])
        if not any(row.get("100u") == "" for row in missing_rows):
            raise RuntimeError("NWP 缺失值场景没有注入空值")

        request_json("POST", f"{self.nwp_url}/scenario", {"name": "malformed"})
        malformed = request_json("POST", f"{self.nwp_url}/generate", {})
        malformed_rows = self._read_nwp_rows(malformed["files"][0])
        if not any(row.get("forecast_time") == "invalid-time" for row in malformed_rows):
            raise RuntimeError("NWP 非法时间场景没有注入异常值")

        request_json("POST", f"{self.nwp_url}/scenario", {"name": "stale"})
        stale = request_json("POST", f"{self.nwp_url}/generate", {})
        if stale.get("files"):
            raise RuntimeError("NWP 陈旧场景仍生成了新文件")
        request_json("POST", f"{self.nwp_url}/scenario", {"name": "normal"})
        return {
            "farm_files": len(files),
            "rows_per_file": expected_rows,
            "scenarios": ["normal", "missing", "malformed", "stale"],
        }

    def invalid_quality(self) -> dict[str, Any]:
        request_json(
            "POST", f"{self.simulator_url}/scenario", {"name": "invalid_quality"}
        )
        snapshot = collect_snapshot(
            catalog=self.catalog,
            host=self.proxy_host,
            port=self.proxy_port,
            timeout_seconds=15,
        )
        validate_snapshot(snapshot, expect_quality="bad")
        bad_count = sum(1 for point in snapshot["points"] if not point["quality_good"])
        return {"bad_quality_points": bad_count}

    def latency_fault(self) -> dict[str, Any]:
        request_json("POST", f"{self.simulator_url}/scenario", {"name": "normal"})
        request_json(
            "POST",
            f"{self.proxy_url}/fault",
            {"enabled": True, "latency_ms": 200, "jitter_ms": 0},
        )
        snapshot = collect_snapshot(
            catalog=self.catalog,
            host=self.proxy_host,
            port=self.proxy_port,
            timeout_seconds=20,
        )
        validate_snapshot(snapshot, expect_quality="good")
        if snapshot["elapsed_seconds"] < 0.18:
            raise RuntimeError("故障代理未体现配置的链路延迟")
        request_json("POST", f"{self.proxy_url}/reset", {})
        return {"elapsed_seconds": snapshot["elapsed_seconds"], "latency_ms": 200}

    def reconnect_after_outage(self) -> dict[str, Any]:
        request_json("POST", f"{self.proxy_url}/fault", {"enabled": False})
        time.sleep(3)
        during = request_json("GET", f"{self.ingress_url}/stats")
        deliveries_during = int(during.get("deliveries", 0))
        request_json("POST", f"{self.proxy_url}/reset", {})
        recovered = wait_for(
            "采集 Worker 在链路恢复后继续上送",
            lambda: request_json("GET", f"{self.ingress_url}/stats"),
            lambda value: int(value.get("deliveries", 0)) > deliveries_during,
            30,
            0.5,
        )
        return {
            "deliveries_at_recovery": recovered["deliveries"],
            "proxy": request_json("GET", f"{self.proxy_url}/state")["metrics"],
        }

    def curtailment_coherence(self) -> dict[str, Any]:
        request_json("POST", f"{self.simulator_url}/scenario", {"name": "curtailment"})
        time.sleep(2.5)
        state = request_json("GET", f"{self.simulator_url}/state")
        frame = state["engine"]["frame"]
        capacities = {
            farm["farm_code"]: float(farm["capacity_mw"])
            for farm in self.catalog["farms"]
        }
        curtailed = 0
        for farm_code, values in frame["farms"].items():
            limit = capacities[farm_code] * 0.4
            if values["active_power_mw"] > limit + 0.05:
                raise RuntimeError(f"{farm_code} 超过限功率值")
            if values["theoretical_power_mw"] > values["active_power_mw"] + 0.5:
                curtailed += 1
        if curtailed == 0:
            raise RuntimeError("限功率场景没有形成理论功率与实发功率差值")
        return {"curtailed_farms": curtailed, "sequence": frame["sequence"]}

    def stale_data(self) -> dict[str, Any]:
        request_json("POST", f"{self.simulator_url}/scenario", {"name": "stale"})
        time.sleep(7.5)
        first = request_json("GET", f"{self.simulator_url}/state")
        time.sleep(2.5)
        second = request_json("GET", f"{self.simulator_url}/state")
        first_frame = first["engine"]["frame"]
        second_frame = second["engine"]["frame"]
        if first_frame["sequence"] != second_frame["sequence"]:
            raise RuntimeError("陈旧数据场景仍在推进数据序号")
        if second_frame["transmit"] is not False:
            raise RuntimeError("陈旧数据场景仍标记为主动发送")
        if second["last_transmit_count"] != 0:
            raise RuntimeError("陈旧数据场景仍有主动发送点位")
        return {"frozen_sequence": second_frame["sequence"]}

    def cleanup(self) -> None:
        try:
            request_json("POST", f"{self.proxy_url}/reset", {})
        except Exception:
            pass
        try:
            request_json("POST", f"{self.simulator_url}/scenario", {"name": "normal"})
        except Exception:
            pass
        try:
            request_json("POST", f"{self.nwp_url}/scenario", {"name": "normal"})
        except Exception:
            pass

    def run(self) -> int:
        self.record("服务与控制面就绪", self.readiness)
        self.record("C104 点表和正常质量码", self.normal_protocol)
        self.record("真实 scada_worker 端到端上送", self.production_worker_path)
        self.record("NWP 多场站文件与故障场景", self.nwp_packages)
        self.record("无效质量码注入", self.invalid_quality)
        self.record("链路延迟注入", self.latency_fault)
        self.record("断线后的自动重连", self.reconnect_after_outage)
        self.record("限功率多变量一致性", self.curtailment_coherence)
        self.record("陈旧数据停止更新", self.stale_data)
        self.cleanup()

        finished_at = datetime.now(timezone.utc)
        passed = all(item["passed"] for item in self.results)
        report = {
            "suite": "wind-power-scada-testbed-acceptance",
            "version": "1.0.0",
            "passed": passed,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round(
                (finished_at - self.started_at).total_seconds(), 3
            ),
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for item in self.results if item["passed"]),
                "failed": sum(1 for item in self.results if not item["passed"]),
            },
            "results": self.results,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
        print(f"验收报告: {self.output_path}", flush=True)
        return 0 if passed else 1


def main() -> None:
    try:
        code = AcceptanceSuite().run()
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"验收套件无法继续: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
