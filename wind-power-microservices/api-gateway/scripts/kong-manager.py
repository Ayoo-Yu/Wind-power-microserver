#!/usr/bin/env python3
"""
Kong API Gateway Management Tool

This script provides utilities to manage and monitor Kong API Gateway
including service configuration, health checks, and metrics collection.
"""

import requests
import json
import time
import argparse
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KongManager:
    """Kong API Gateway management client."""

    def __init__(self, admin_url: str = "http://localhost:8001"):
        self.admin_url = admin_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to Kong Admin API."""
        url = f"{self.admin_url}/{endpoint.lstrip('/')}"

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=30)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=30)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, timeout=30)
            elif method.upper() == 'PATCH':
                response = self.session.patch(url, json=data, timeout=30)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get Kong server status."""
        return self._make_request('GET', '/status')

    def get_services(self) -> List[Dict[str, Any]]:
        """Get all services."""
        response = self._make_request('GET', '/services')
        return response.get('data', [])

    def get_routes(self) -> List[Dict[str, Any]]:
        """Get all routes."""
        response = self._make_request('GET', '/routes')
        return response.get('data', [])

    def get_plugins(self) -> List[Dict[str, Any]]:
        """Get all plugins."""
        response = self._make_request('GET', '/plugins')
        return response.get('data', [])

    def get_consumers(self) -> List[Dict[str, Any]]:
        """Get all consumers."""
        response = self._make_request('GET', '/consumers')
        return response.get('data', [])

    def get_upstreams(self) -> List[Dict[str, Any]]:
        """Get all upstreams."""
        response = self._make_request('GET', '/upstreams')
        return response.get('data', [])

    def create_service(self, name: str, url: str, **kwargs) -> Dict[str, Any]:
        """Create a new service."""
        data = {
            'name': name,
            'url': url,
            **kwargs
        }
        return self._make_request('POST', '/services', data)

    def create_route(self, service_name: str, name: str, paths: List[str],
                    methods: Optional[List[str]] = None,
                    strip_path: bool = False) -> Dict[str, Any]:
        """Create a new route for a service."""
        data = {
            'name': name,
            'service': {'name': service_name},
            'paths': paths,
            'strip_path': strip_path
        }

        if methods:
            data['methods'] = methods

        return self._make_request('POST', '/routes', data)

    def enable_plugin(self, plugin_name: str, service_name: Optional[str] = None,
                     route_name: Optional[str] = None, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Enable a plugin."""
        data = {
            'name': plugin_name,
            'config': config or {}
        }

        if service_name:
            data['service'] = {'name': service_name}
        elif route_name:
            data['route'] = {'name': route_name}

        return self._make_request('POST', '/plugins', data)

    def create_consumer(self, username: str, custom_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new consumer."""
        data = {'username': username}
        if custom_id:
            data['custom_id'] = custom_id
        return self._make_request('POST', '/consumers', data)

    def create_jwt_credential(self, consumer_username: str, key: str, secret: str,
                            algorithm: str = "HS256") -> Dict[str, Any]:
        """Create JWT credential for a consumer."""
        data = {
            'key': key,
            'secret': secret,
            'algorithm': algorithm
        }
        return self._make_request('POST', f'/consumers/{consumer_username}/jwt', data)

    def get_metrics(self) -> Dict[str, Any]:
        """Get Kong metrics from Prometheus plugin."""
        try:
            response = self.session.get(f"{self.admin_url}/metrics", timeout=10)
            response.raise_for_status()

            # Parse Prometheus metrics format
            metrics_text = response.text
            metrics = {}

            for line in metrics_text.split('\n'):
                if line and not line.startswith('#'):
                    parts = line.split(' ')
                    if len(parts) == 2:
                        metric_name, metric_value = parts
                        metrics[metric_name] = float(metric_value)

            return metrics
        except requests.exceptions.RequestException:
            logger.warning("Prometheus metrics not available")
            return {}

    def health_check(self, service_name: str) -> bool:
        """Perform health check on a service."""
        try:
            # Get service targets
            targets_response = self._make_request('GET', f'/upstreams/{service_name}-upstream/targets')
            targets = targets_response.get('data', [])

            healthy_count = 0
            total_count = len(targets)

            for target in targets:
                if target.get('health') == 'HEALTHY':
                    healthy_count += 1

            health_percentage = (healthy_count / total_count * 100) if total_count > 0 else 0

            logger.info(f"Service {service_name} health: {healthy_count}/{total_count} ({health_percentage:.1f}%) targets healthy")
            return health_percentage >= 50  # Consider healthy if 50%+ targets are healthy

        except Exception as e:
            logger.error(f"Health check failed for service {service_name}: {e}")
            return False

    def setup_wind_farm_services(self) -> None:
        """Setup all wind farm microservices in Kong."""
        logger.info("Setting up wind farm microservices...")

        services_config = [
            {
                'name': 'meteorological-service',
                'url': 'http://meteorological-service:8001',
                'routes': [
                    {'name': 'weather-stations', 'paths': ['/api/v1/weather-stations'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                    {'name': 'weather-data', 'paths': ['/api/v1/weather-data'], 'methods': ['GET', 'POST']},
                    {'name': 'forecasts', 'paths': ['/api/v1/forecasts'], 'methods': ['GET', 'POST']},
                ]
            },
            {
                'name': 'scada-service',
                'url': 'http://scada-service:8002',
                'routes': [
                    {'name': 'scada-data', 'paths': ['/api/v1/scada-data'], 'methods': ['GET', 'POST']},
                    {'name': 'scada-alerts', 'paths': ['/api/v1/scada-alerts'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                ]
            },
            {
                'name': 'power-prediction-service',
                'url': 'http://power-prediction-service:8003',
                'routes': [
                    {'name': 'predictions', 'paths': ['/api/v1/predictions'], 'methods': ['GET', 'POST']},
                    {'name': 'ml-models', 'paths': ['/api/v1/ml-models'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                ]
            },
            {
                'name': 'report-service',
                'url': 'http://report-service:8004',
                'routes': [
                    {'name': 'reports', 'paths': ['/api/v1/reports'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                    {'name': 'charts', 'paths': ['/api/v1/charts'], 'methods': ['GET', 'POST', 'DELETE']},
                    {'name': 'templates', 'paths': ['/api/v1/templates'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                ]
            },
            {
                'name': 'tenant-service',
                'url': 'http://tenant-service:8007',
                'routes': [
                    {'name': 'auth', 'paths': ['/api/v1/auth'], 'methods': ['POST']},
                    {'name': 'users', 'paths': ['/api/v1/users'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                    {'name': 'tenants', 'paths': ['/api/v1/tenants'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                ]
            },
            {
                'name': 'wind-farm-service',
                'url': 'http://windfarm-service:8006',
                'routes': [
                    {'name': 'wind-farms', 'paths': ['/api/v1/wind-farms'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                    {'name': 'turbines', 'paths': ['/api/v1/turbines'], 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                ]
            }
        ]

        for service_config in services_config:
            try:
                # Create service
                service = self.create_service(service_config['name'], service_config['url'])
                logger.info(f"✅ Created service: {service_config['name']}")

                # Create routes
                for route_config in service_config['routes']:
                    route = self.create_route(
                        service_config['name'],
                        route_config['name'],
                        route_config['paths'],
                        route_config['methods']
                    )
                    logger.info(f"✅ Created route: {route_config['name']}")

                # Enable common plugins
                self.enable_plugin('cors', service_name=service_config['name'])
                self.enable_plugin('rate-limiting', service_name=service_config['name'], config={
                    'minute': 1000,
                    'hour': 10000,
                    'policy': 'local'
                })
                logger.info(f"✅ Enabled plugins for service: {service_config['name']}")

            except Exception as e:
                logger.error(f"❌ Failed to setup service {service_config['name']}: {e}")

    def setup_authentication(self) -> None:
        """Setup JWT authentication for API consumers."""
        logger.info("Setting up JWT authentication...")

        consumers = [
            {'username': 'wind-farm-web-ui', 'custom_id': 'web-ui-001'},
            {'username': 'wind-farm-mobile-app', 'custom_id': 'mobile-app-001'},
            {'username': 'external-api-client', 'custom_id': 'external-api-001'},
            {'username': 'admin-client', 'custom_id': 'admin-client-001'}
        ]

        for consumer_config in consumers:
            try:
                # Create consumer
                consumer = self.create_consumer(consumer_config['username'], consumer_config['custom_id'])
                logger.info(f"✅ Created consumer: {consumer_config['username']}")

                # Create JWT credential
                jwt_cred = self.create_jwt_credential(
                    consumer_config['username'],
                    f"{consumer_config['username']}-key",
                    f"{consumer_config['username']}-secret-change-in-production"
                )
                logger.info(f"✅ Created JWT credential for: {consumer_config['username']}")

            except Exception as e:
                logger.error(f"❌ Failed to setup consumer {consumer_config['username']}: {e}")

    def monitor_services(self) -> Dict[str, Any]:
        """Monitor all services health and metrics."""
        logger.info("Monitoring services...")

        services = ['meteorological-service', 'scada-service', 'power-prediction-service',
                   'report-service', 'tenant-service', 'wind-farm-service']

        monitoring_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'services': {}
        }

        for service_name in services:
            try:
                # Health check
                is_healthy = self.health_check(service_name)

                # Get service info
                service_info = self._make_request('GET', f'/services/{service_name}')

                monitoring_results['services'][service_name] = {
                    'healthy': is_healthy,
                    'status': service_info.get('status', 'unknown'),
                    'url': service_info.get('url', 'unknown'),
                    'created_at': service_info.get('created_at', 'unknown')
                }

                logger.info(f"Service {service_name}: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")

            except Exception as e:
                logger.error(f"❌ Failed to monitor service {service_name}: {e}")
                monitoring_results['services'][service_name] = {
                    'healthy': False,
                    'error': str(e)
                }

        return monitoring_results

def main():
    parser = argparse.ArgumentParser(description='Kong API Gateway Management Tool')
    parser.add_argument('--admin-url', default='http://localhost:8001', help='Kong Admin API URL')
    parser.add_argument('--command', choices=['status', 'services', 'routes', 'plugins', 'consumers',
                                            'setup-services', 'setup-auth', 'monitor', 'metrics'],
                       required=True, help='Command to execute')

    args = parser.parse_args()

    # Create Kong manager
    kong_manager = KongManager(args.admin_url)

    try:
        if args.command == 'status':
            status = kong_manager.get_status()
            print(json.dumps(status, indent=2))

        elif args.command == 'services':
            services = kong_manager.get_services()
            print(json.dumps(services, indent=2))

        elif args.command == 'routes':
            routes = kong_manager.get_routes()
            print(json.dumps(routes, indent=2))

        elif args.command == 'plugins':
            plugins = kong_manager.get_plugins()
            print(json.dumps(plugins, indent=2))

        elif args.command == 'consumers':
            consumers = kong_manager.get_consumers()
            print(json.dumps(consumers, indent=2))

        elif args.command == 'setup-services':
            kong_manager.setup_wind_farm_services()

        elif args.command == 'setup-auth':
            kong_manager.setup_authentication()

        elif args.command == 'monitor':
            results = kong_manager.monitor_services()
            print(json.dumps(results, indent=2))

        elif args.command == 'metrics':
            metrics = kong_manager.get_metrics()
            print(json.dumps(metrics, indent=2))

    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1

    return 0

if __name__ == '__main__':
    exit(main())