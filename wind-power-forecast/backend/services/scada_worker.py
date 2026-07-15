#!/usr/bin/env python3
"""
SCADA Connection Worker - Standalone subprocess script
Runs as a child process managed by scada_manager.py

Supports two modes:
  - c104: IEC 60870-5-104 protocol (production)
  - http_poll: HTTP polling (simulation/development)

Usage:
  python scada_worker.py --config '{"farm_code":"CF","protocol":"http_poll",...}'
"""
from __future__ import annotations

import sys
import json
import time
import signal
import logging
import argparse
import os
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
)
logger = logging.getLogger('SCADA-Worker')

running = True

# Minutes before each 15-min boundary to accept data (inclusive)
WINDOW_BEFORE_MINUTES = 2
SUPPORTED_TIMESTAMP_POLICIES = {
    'quarter_window',
    'receive_time',
    'floor_quarter',
    'source_time',
    'source_quarter_window',
}


def resolve_c104_ip(server_ip: str) -> str:
    """Resolve Docker service names before passing them to the c104 client."""
    if server_ip in ('127.0.0.1', 'localhost', '::1'):
        docker_host = os.environ.get('SCADA_SIMULATOR_HOST', '').strip()
        if docker_host:
            logger.info(f"Replacing loopback SCADA host {server_ip} with {docker_host}")
            server_ip = docker_host

    try:
        resolved_ip = socket.gethostbyname(server_ip)
    except socket.gaierror:
        logger.warning(f"Could not resolve SCADA host {server_ip}; using it as-is")
        return server_ip

    if resolved_ip != server_ip:
        logger.info(f"Resolved SCADA host {server_ip} to {resolved_ip}")
    return resolved_ip


def round_to_quarter_hour(now: datetime) -> datetime | None:
    """
    If *now* falls within the acceptance window [T-WINDOW, T] where T is
    the next (or current) 15-minute boundary, return T (naive, second=0).
    Otherwise return None (data should be dropped).

    Window examples (WINDOW_BEFORE_MINUTES=2):
      18:28 → 18:30   (2 min before)
      18:29 → 18:30   (1 min before)
      18:30 → 18:30   (exactly on boundary)
      18:31 → None    (outside window)
      18:14 → 18:15   (1 min before)
      18:00 → 18:00   (exactly on boundary)
    """
    now_bj = now.astimezone(BEIJING_TZ)
    minute = now_bj.minute
    remainder = minute % 15

    if remainder == 0:
        # Exactly on a 15-min boundary
        return now_bj.replace(second=0, microsecond=0, tzinfo=None)
    elif remainder >= 15 - WINDOW_BEFORE_MINUTES:
        # Within WINDOW_BEFORE_MINUTES of the next boundary
        target_minute = (minute // 15 + 1) * 15
        hour = now_bj.hour
        if target_minute >= 60:
            hour += 1
            target_minute -= 60
        # Handle midnight rollover
        if hour >= 24:
            return now_bj.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None,
            ) + timedelta(days=1)
        return now_bj.replace(
            hour=hour, minute=target_minute,
            second=0, microsecond=0, tzinfo=None,
        )
    else:
        return None


def select_sample_timestamp(
    now: datetime,
    config: dict,
    source_time: datetime | None = None,
) -> datetime | None:
    """根据部署策略选择数据时间，默认保持原有十五分钟窗口逻辑。"""

    policy = str(
        config.get('timestamp_policy')
        or os.environ.get('SCADA_TIMESTAMP_POLICY', 'quarter_window')
    ).strip().lower()
    if policy not in SUPPORTED_TIMESTAMP_POLICIES:
        raise ValueError(f'Unsupported timestamp_policy: {policy}')

    candidate = now
    if policy.startswith('source') and source_time is not None:
        candidate = source_time
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=BEIJING_TZ)

    if policy in ('quarter_window', 'source_quarter_window'):
        return round_to_quarter_hour(candidate)
    if policy == 'floor_quarter':
        candidate_bj = candidate.astimezone(BEIJING_TZ)
        return candidate_bj.replace(
            minute=(candidate_bj.minute // 15) * 15,
            second=0,
            microsecond=0,
            tzinfo=None,
        )
    return candidate.astimezone(BEIJING_TZ).replace(tzinfo=None)


def signal_handler(signum, frame):
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


# Windows only supports SIGINT (Ctrl+C) and SIGBREAK
signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, signal_handler)
if hasattr(signal, 'SIGBREAK'):
    signal.signal(signal.SIGBREAK, signal_handler)


def update_status(config: dict, status: str, message: str = '', power_value=None):
    """Report status back to the manager via HTTP"""
    backend_url = config.get('backend_url', 'http://127.0.0.1:5000')
    url = f'{backend_url}/scada/worker-status'
    payload = {
        'connection_id': config['connection_id'],
        'status': status,
        'status_message': message,
    }
    if power_value is not None:
        payload['last_power_value'] = int(power_value * 10)
    headers = {'Content-Type': 'application/json'}
    secret = config.get('worker_secret') or os.environ.get('SCADA_WORKER_SECRET', '')
    if secret:
        headers['X-Worker-Secret'] = secret
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as e:
        logger.warning(f"Failed to update status: {e}")


def _post_json(url: str, payload: dict, headers: dict | None = None):
    request_headers = {'Content-Type': 'application/json'}
    request_headers.update(headers or {})
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=request_headers,
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('utf-8')
            body = json.loads(raw) if raw else {}
            return resp.status, body
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode('utf-8')
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {}
        return exc.code, body
    except Exception as exc:
        logger.warning(f"POST sample error: {exc}")
        return 0, {'error': str(exc)}


def post_power(backend_url: str, farm_code: str, timestamp_str: str, power: float):
    """兼容旧后端的实际功率写入接口。"""
    url = f'{backend_url}/actual_power/'
    status, _body = _post_json(url, {
        'Timestamp': timestamp_str,
        'farm_code': farm_code,
        'wp_true': round(power, 2),
    })
    return status


def _timestamp_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def point_quality_label(point) -> str:
    """将 c104 质量对象归一化为后端可校验的值。"""
    quality = getattr(point, 'quality', None)
    if quality is None:
        return 'unknown'
    is_good = getattr(quality, 'is_good', None)
    try:
        if callable(is_good):
            return 'good' if is_good() else 'bad'
        if isinstance(is_good, bool):
            return 'good' if is_good else 'bad'
    except Exception:
        pass
    return 'unknown'


def submit_sample(
    config: dict,
    *,
    power: float | None,
    normalized_timestamp: datetime | None,
    source_timestamp: datetime | None,
    ioa: int | None,
    quality: str,
):
    """提交可追溯样本，旧后端仅在新接口不存在时回退。"""
    backend_url = config.get('backend_url', 'http://127.0.0.1:5000')
    headers = {}
    secret = config.get('worker_secret') or os.environ.get('SCADA_WORKER_SECRET', '')
    if secret:
        headers['X-Worker-Secret'] = secret
    status, body = _post_json(
        f'{backend_url}/api/v1/scada/ingest',
        {
            'connection_id': config['connection_id'],
            'farm_code': config['farm_code'],
            'ioa': ioa,
            'source_timestamp': _timestamp_text(source_timestamp),
            'normalized_timestamp': _timestamp_text(normalized_timestamp),
            'power_mw': power,
            'quality': quality,
        },
        headers,
    )
    if status == 404 and normalized_timestamp is not None and power is not None:
        legacy_status = post_power(
            backend_url,
            config['farm_code'],
            normalized_timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
            power,
        )
        return legacy_status, {'outcome': 'legacy_actual_power'}
    return status, body


def run_http_poll(config: dict):
    """HTTP polling mode - polls a remote endpoint for power data"""
    server_ip = config['server_ip']
    server_port = config['server_port']
    farm_code = config['farm_code']
    backend_url = config.get('backend_url', 'http://127.0.0.1:5000')
    interval = config.get('fetch_interval', 60)
    capacity = config.get('capacity', 200)
    farm_index = config.get('farm_index', 0)

    update_status(config, 'running', 'HTTP polling mode started')

    import math
    import random

    cycle = 0
    while running:
        try:
            cycle += 1
            now = datetime.now(BEIJING_TZ)
            timestamp_str = now.strftime('%Y-%m-%dT%H:%M:%S')
            hour = now.hour + now.minute / 60.0
            day_of_year = now.timetuple().tm_yday

            # Generate simulated power (same algorithm as scada_multifarm.py)
            phase_offset = farm_index * 1.2
            amplitude = 0.25 + farm_index * 0.05
            diurnal = 0.5 + amplitude * math.sin((hour - 4 + phase_offset) * math.pi / 12.0)
            seasonal = 0.5 + 0.2 * math.sin(day_of_year * math.pi / 182.5)
            gust = random.gauss(0, 0.04)
            factor = max(0.0, min(1.0, diurnal * seasonal + gust))

            if random.random() < 0.03:
                factor = random.uniform(0.0, 0.05)

            power = round(factor * capacity, 2)

            rounded = select_sample_timestamp(now, config)
            status, result = submit_sample(
                config,
                power=power,
                normalized_timestamp=rounded,
                source_timestamp=now,
                ioa=config.get('upload_target_ioa'),
                quality='good',
            )
            if 200 <= status < 300:
                outcome = result.get('outcome', 'accepted')
                if rounded is None:
                    logger.debug(
                        f"[{farm_code}] {power:.2f} MW observed without quarter-hour write"
                    )
                else:
                    logger.info(
                        f"[{farm_code}] {power:7.2f} MW → {rounded.strftime('%H:%M')} "
                        f"({outcome}, cycle {cycle})"
                    )
                update_status(config, 'running', f'Cycle {cycle}: {power:.2f} MW, {outcome}', power)
            elif rounded is None:
                logger.debug(
                    f"[{farm_code}] sample submission failed status={status}"
                )
            else:
                logger.warning(f"[{farm_code}] sample submission failed status={status}")
            if not 200 <= status < 300:
                error = result.get('error') or result.get('message') or f'HTTP {status}'
                update_status(config, 'running', f'Sample rejected: {error}')

        except Exception as e:
            logger.error(f"Error in polling cycle: {e}")
            update_status(config, 'error', str(e))

        # Sleep in small increments so we can respond to shutdown signals
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    update_status(config, 'stopped', 'Worker shut down')


def run_c104(config: dict):
    """C104 protocol mode - connects to IEC 60870-5-104 server"""
    configured_server_ip = config['server_ip']
    server_ip = resolve_c104_ip(configured_server_ip)
    server_port = config['server_port']
    farm_code = config['farm_code']
    backend_url = config.get('backend_url', 'http://127.0.0.1:5000')
    interval = config.get('fetch_interval', 60)
    casdu_address = config.get('casdu_address', 1)
    originator_address = config.get('originator_address', 0)
    ioa_points = config.get('ioa_points', {})
    target_ioa = config.get('upload_target_ioa')
    if target_ioa is not None:
        target_ioa = int(target_ioa)
        ioa_points = {str(k): v for k, v in ioa_points.items()}
        ioa_points.setdefault(str(target_ioa), 'M_ME_NC_1')

    try:
        import c104
    except ImportError:
        logger.error("c104 library not installed.")
        update_status(config, 'error', 'c104 library not available')
        return

    update_status(config, 'connecting', f'Connecting to {configured_server_ip}:{server_port}')

    def on_measurement(point, previous_info, message):
        if target_ioa is not None and int(point.io_address) != target_ioa:
            return c104.ResponseState.SUCCESS

        quality = point_quality_label(point)
        value = point.value
        power = float(value) if value is not None else None
        now = datetime.now(BEIJING_TZ)
        source_time = getattr(point, 'recorded_at', None)
        rounded = (
            select_sample_timestamp(now, config, source_time)
            if power is not None and quality == 'good'
            else None
        )
        status, result = submit_sample(
            config,
            power=power,
            normalized_timestamp=rounded,
            source_timestamp=source_time,
            ioa=int(point.io_address),
            quality=quality,
        )
        if 200 <= status < 300 and power is not None:
            outcome = result.get('outcome', 'accepted')
            target = rounded.strftime('%H:%M') if rounded is not None else 'raw'
            logger.info(f"IOA={point.io_address}: {power} MW → {target} ({outcome})")
            update_status(
                config,
                'running',
                f'IOA={point.io_address}: {power:.2f} MW, {outcome}',
                power,
            )
        else:
            error = result.get('error') or result.get('message') or f'HTTP {status}'
            logger.warning(
                f"IOA={point.io_address}: sample rejected status={status}, reason={error}"
            )
            update_status(config, 'running', f'Sample rejected: {error}')
        return c104.ResponseState.SUCCESS
    on_measurement.__annotations__ = {
        'point': c104.Point,
        'previous_info': c104.Information,
        'message': c104.IncomingMessage,
        'return': c104.ResponseState,
    }

    def on_state_change(connection, state):
        state_names = {
            c104.ConnectionState.CLOSED: 'CLOSED',
            c104.ConnectionState.CLOSED_AWAIT_OPEN: 'CONNECTING',
            c104.ConnectionState.CLOSED_AWAIT_RECONNECT: 'RECONNECTING',
            c104.ConnectionState.OPEN: 'CONNECTED',
            c104.ConnectionState.OPEN_AWAIT_CLOSED: 'DISCONNECTING',
            c104.ConnectionState.OPEN_MUTED: 'MUTED',
        }
        name = state_names.get(state, str(state))
        logger.info(f"Connection state: {name}")
        if state == c104.ConnectionState.OPEN:
            update_status(config, 'running', f'Connected to {configured_server_ip}:{server_port}')
        elif state == c104.ConnectionState.CLOSED:
            update_status(config, 'error', 'Disconnected')
    on_state_change.__annotations__ = {
        'connection': c104.Connection,
        'state': c104.ConnectionState,
        'return': None,
    }

    client = c104.Client()
    if originator_address:
        client.originator_address = int(originator_address)

    connection = client.add_connection(
        ip=server_ip,
        port=server_port,
        init=c104.Init.MUTED,
    )
    connection.on_state_change(callable=on_state_change)

    station = connection.add_station(common_address=casdu_address)
    for ioa_str, point_type_str in ioa_points.items():
        ioa = int(ioa_str)
        point_type = getattr(c104.Type, point_type_str, c104.Type.M_ME_NC_1)
        point = station.add_point(io_address=ioa, type=point_type)
        point.on_receive(callable=on_measurement)

    try:
        client.start()
        logger.info("Client started, waiting for connection...")

        while running:
            try:
                if not connection.is_connected:
                    logger.warning("GI skipped: connection not open")
                elif getattr(connection, 'is_muted', False):
                    try:
                        connection.unmute()
                        logger.info("Connection unmuted")
                    except Exception as e:
                        logger.warning(f"Unmute failed: {e}")
                elif connection.interrogation(
                    common_address=casdu_address,
                    qualifier=c104.Qoi.STATION,
                ):
                    logger.info("Sent General Interrogation")
                else:
                    logger.warning("GI failed: connection not open")
            except Exception as e:
                logger.error(f"GI failed: {e}")

            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

    except Exception as e:
        logger.error(f"C104 error: {e}")
        update_status(config, 'error', str(e))
    finally:
        try:
            client.stop()
        except Exception:
            pass
        update_status(config, 'stopped', 'Worker shut down')


def main():
    parser = argparse.ArgumentParser(description='SCADA Connection Worker')
    parser.add_argument('--config', required=True, help='JSON configuration string')
    args = parser.parse_args()

    config = json.loads(args.config)
    logger.info(f"Starting worker for farm={config['farm_code']} protocol={config.get('protocol', 'c104')}")
    logger.info(f"Server: {config['server_ip']}:{config['server_port']}")

    protocol = config.get('protocol', 'c104')
    if protocol == 'http_poll':
        run_http_poll(config)
    else:
        run_c104(config)

    logger.info("Worker exited.")


if __name__ == '__main__':
    main()
