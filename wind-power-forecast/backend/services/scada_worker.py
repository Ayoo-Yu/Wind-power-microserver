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

            status = post_power(backend_url, farm_code, timestamp_str, power)
            if 200 <= status < 300:
                logger.info(f"[{farm_code}] {power:7.2f} MW  (cycle {cycle})")
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
    originator_address = config.get('originator_address', 0)
    ioa_points = config.get('ioa_points', {})
    target_ioa = config.get('upload_target_ioa')

    try:
        import c104
    except ImportError:
        logger.error("c104 library not installed. Falling back to http_poll mode.")
        update_status(config, 'error', 'c104 library not available')
        return

    update_status(config, 'connecting', f'Connecting to {server_ip}:{server_port}')

    latest_power = None

    def on_point_callback(point):
        nonlocal latest_power
        value = point.value
        if value is not None:
            latest_power = float(value)
            logger.info(f"IOA={point.io_address}: {latest_power} MW")
            now = datetime.now(BEIJING_TZ)
            post_power(backend_url, farm_code, now.strftime('%Y-%m-%dT%H:%M:%S'), latest_power)
            update_status(config, 'running', f'IOA={point.io_address}: {latest_power:.2f} MW', latest_power)

    def on_connect(client):
        logger.info(f"Connected to {server_ip}:{server_port}")
        update_status(config, 'running', f'Connected to {server_ip}:{server_port}')

    def on_disconnect(client):
        logger.warning(f"Disconnected from {server_ip}:{server_port}")
        update_status(config, 'error', 'Disconnected')

    client = c104.Client(
        server_ip=server_ip,
        server_port=server_port,
        originator_address=originator_address,
    )

    # Set up station and points
    station = c104.Station(common_address=casdu_address)
    for ioa_str, point_type_str in ioa_points.items():
        ioa = int(ioa_str)
        point_type = getattr(c104.Type, point_type_str, c104.Type.M_ME_NC_1)
        point = c104.Point(io_address=ioa, type=point_type)
        point.on_callback(on_point_callback)
        station.add_point(point)

    client.add_station(station)
    client.on_connect(on_connect)
    client.on_disconnect(on_disconnect)

    try:
        client.connect()
        update_status(config, 'running', 'C104 connected, monitoring...')

        while running:
            # Periodic General Interrogation
            try:
                station.interrogation()
                logger.info("Sent General Interrogation")
            except Exception as e:
                logger.error(f"GI failed: {e}")
                update_status(config, 'error', f'GI failed: {e}')

            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

    except Exception as e:
        logger.error(f"C104 error: {e}")
        update_status(config, 'error', str(e))
    finally:
        try:
            client.disconnect()
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
