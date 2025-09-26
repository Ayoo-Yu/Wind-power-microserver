# Wind Power Forecasting Microservices Platform

A modern, scalable microservices architecture for wind power forecasting systems.

## Architecture Overview

This platform consists of 5 core microservices:

1. **Tenant Management Service** - Multi-tenant wind farm management and authentication
2. **SCADA Data Service** - Real-time power data ingestion from wind turbines
3. **Meteorological Data Service** - Weather data acquisition and processing
4. **Prediction Service** - ML-based power forecasting across multiple time horizons
5. **Reporting Service** - Automated reporting and external system integration

## Project Structure

```
wind-power-microservices/
├── shared/                          # Shared libraries and utilities
├── api-gateway/                     # API Gateway implementation
├── services/                        # Microservices implementations
│   ├── tenant-service/             # Tenant Management Service
│   ├── scada-service/              # SCADA Data Service
│   ├── meteorological-service/     # Meteorological Data Service
│   ├── prediction-service/         # Prediction Service
│   └── reporting-service/          # Reporting Service
├── infrastructure/                  # Infrastructure as Code
│   ├── kubernetes/                 # Kubernetes manifests
│   ├── helm-charts/               # Helm charts for deployment
│   └── terraform/                 # Terraform configurations
├── scripts/                        # Automation scripts
└── docs/                          # Documentation
```

## Technology Stack

- **Framework**: FastAPI (Python)
- **Databases**: PostgreSQL, TimescaleDB, Redis
- **Message Queue**: Apache Kafka
- **Service Mesh**: Istio
- **Container Orchestration**: Kubernetes
- **API Gateway**: Kong/Envoy
- **Monitoring**: Prometheus, Grafana, Jaeger
- **CI/CD**: GitLab CI/CD, ArgoCD

## Quick Start

### Prerequisites
- Docker Desktop
- Kubernetes cluster (minikube/kind for local development)
- Helm 3.x
- kubectl
- Python 3.9+

### Local Development Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Start local infrastructure: `./scripts/start-local-infrastructure.sh`
4. Deploy services: `./scripts/deploy-local.sh`

## Service Communication

- **Synchronous**: REST APIs with OpenAPI 3.0
- **Asynchronous**: Apache Kafka for event-driven architecture
- **Service Discovery**: Kubernetes DNS + Consul
- **Load Balancing**: Kubernetes Services + Istio

## Development Guidelines

See [Development Guide](docs/development-guide.md) for:
- Service development patterns
- API design standards
- Testing strategies
- Deployment procedures

## Monitoring & Observability

- **Metrics**: Prometheus + Grafana dashboards
- **Tracing**: Jaeger for distributed tracing
- **Logging**: ELK stack (Elasticsearch, Logstash, Kibana)
- **Health Checks**: Kubernetes liveness/readiness probes

## Security

- **Authentication**: OAuth 2.0 + JWT tokens
- **Authorization**: RBAC with service-specific permissions
- **Network Security**: mTLS between services
- **Secrets Management**: Kubernetes Secrets + HashiCorp Vault

## Contributing

See [Contributing Guide](CONTRIBUTING.md) for development workflow and coding standards.