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
import sys
import json
import time
import signal
import logging
import argparse
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
    secret = config.get('worker_secret')
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


def post_power(backend_url: str, farm_code: str, timestamp_str: str, power: float):
    """POST power data to the backend actual_power API"""
    url = f'{backend_url}/actual_power/'
    payload = json.dumps({
        'Timestamp': timestamp_str,
        'farm_code': farm_code,
        'wp_true': round(power, 2),
    }).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        logger.warning(f"POST power failed: {e.code}")
        return e.code
    except Exception as e:
        logger.warning(f"POST power error: {e}")
        return 0


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

            rounded = round_to_quarter_hour(now)
            if rounded is None:
                logger.debug(
                    f"[{farm_code}] {power:.2f} MW skipped "
                    f"(outside {WINDOW_BEFORE_MINUTES}-min window, now={now.strftime('%H:%M:%S')})"
                )
            else:
                ts_str = rounded.strftime('%Y-%m-%dT%H:%M:%S')
                status = post_power(backend_url, farm_code, ts_str, power)
                if 200 <= status < 300:
                    logger.info(
                        f"[{farm_code}] {power:7.2f} MW → {rounded.strftime('%H:%M')}  (cycle {cycle})"
                    )
                    update_status(config, 'running', f'Cycle {cycle}: {power:.2f} MW', power)
                else:
                    logger.warning(f"[{farm_code}] POST failed status={status}")
                    update_status(config, 'running', f'POST failed: status={status}', power)

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
    server_ip = config['server_ip']
    server_port = config['server_port']
    farm_code = config['farm_code']
    backend_url = config.get('backend_url', 'http://127.0.0.1:5000')
    interval = config.get('fetch_interval', 60)
    casdu_address = config.get('casdu_address', 1)
    ioa_points = config.get('ioa_points', {})
    target_ioa = config.get('upload_target_ioa')

    try:
        import c104
    except ImportError:
        logger.error("c104 library not installed.")
        update_status(config, 'error', 'c104 library not available')
        return

    update_status(config, 'connecting', f'Connecting to {server_ip}:{server_port}')

    def on_measurement(point: c104.Point, previous_info: c104.Information,
                       message: c104.IncomingMessage) -> c104.ResponseState:
        value = point.value
        if value is not None:
            power = float(value)
            now = datetime.now(BEIJING_TZ)
            rounded = round_to_quarter_hour(now)
            if rounded is None:
                logger.debug(
                    f"IOA={point.io_address}: {power} MW skipped "
                    f"(outside {WINDOW_BEFORE_MINUTES}-min window)"
                )
            else:
                ts_str = rounded.strftime('%Y-%m-%dT%H:%M:%S')
                post_power(backend_url, farm_code, ts_str, power)
                logger.info(f"IOA={point.io_address}: {power} MW → {rounded.strftime('%H:%M')}")
                update_status(config, 'running', f'IOA={point.io_address}: {power:.2f} MW', power)
        return c104.ResponseState.SUCCESS

    def on_state_change(connection: c104.Connection,
                        state: c104.ConnectionState) -> None:
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
            update_status(config, 'running', f'Connected to {server_ip}:{server_port}')
        elif state == c104.ConnectionState.CLOSED:
            update_status(config, 'error', 'Disconnected')

    client = c104.Client()

    connection = client.add_connection(
        ip=server_ip,
        port=server_port,
        init=c104.Init.INTERROGATION,
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
                if connection.interrogation(common_address=casdu_address):
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
