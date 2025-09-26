# Wind Power API Gateway

Kong API Gateway implementation for the wind power forecasting microservices system.

## 🚀 Quick Start

```bash
# Start all services
docker-compose up -d

# Wait for initialization
sleep 30

# Initialize Kong configuration
./scripts/init-kong.sh

# Test the API gateway
./scripts/test-api-gateway.sh
```

Access the API gateway at: http://localhost:8000

## 📋 Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Kong Admin    │    │   Kong Proxy    │    │   Konga GUI     │
│   Port: 8001    │    │   Port: 8000    │    │   Port: 1337    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │   Microservices │
│   Port: 5432    │    │   Port: 6379    │    │   Ports: 8001-8007│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Services Configuration

### Microservices Overview
| Service | Port | Base Path | Description |
|---------|------|-----------|-------------|
| Meteorological | 8001 | `/api/v1/weather-*` | Weather data and forecasts |
| SCADA | 8002 | `/api/v1/scada-*` | Real-time sensor data |
| Power Prediction | 8003 | `/api/v1/predictions` | ML-based power predictions |
| Report | 8004 | `/api/v1/reports` | Reports and analytics |
| Tenant | 8007 | `/api/v1/auth` | User management |
| Wind Farm | 8006 | `/api/v1/wind-farms` | Wind farm management |

### Security Features
- ✅ JWT Authentication with custom plugin
- ✅ Rate limiting (1000/min, 10000/hour)
- ✅ CORS configuration
- ✅ Request/response validation

### Monitoring & Management
- ✅ Prometheus metrics collection
- ✅ Konga GUI for management
- ✅ Health check endpoints
- ✅ Comprehensive logging

## 📖 Documentation

- [API Documentation](API_DOCUMENTATION.md) - Complete API reference
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Production deployment instructions
- [Kong Configuration](config/kong.conf) - Kong server configuration
- [Declarative Config](declarative/kong.yml) - Service definitions

## 🛠️ Management Scripts

| Script | Description |
|--------|-------------|
| `init-kong.sh` | Initialize Kong with all services |
| `health-check.sh` | Comprehensive health monitoring |
| `test-api-gateway.sh` | Integration testing suite |
| `kong-manager.py` | Python management tool |

## 🔍 Testing

```bash
# Run all tests
./scripts/test-api-gateway.sh

# Test specific component
./scripts/test-api-gateway.sh --test jwt

# Test with custom URLs
./scripts/test-api-gateway.sh --kong-admin-url http://kong:8001
```

## 📊 Monitoring

### Health Checks
```bash
# Kong status
curl http://localhost:8001/status

# Service health
curl http://localhost:8000/health
```

### Metrics
```bash
# Prometheus metrics
curl http://localhost:8001/metrics

# Konga GUI
open http://localhost:1337
```

## 🔐 Authentication

### Get JWT Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass"}'
```

### Use JWT Token
```bash
curl -X GET http://localhost:8000/api/v1/weather-stations \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🚀 Development

### Local Development
```bash
# Start development environment
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# View logs
docker-compose logs -f kong
```

### Custom Plugin Development
```bash
# Build with custom plugins
docker-compose build kong

# Test plugin
./scripts/test-api-gateway.sh --test plugins
```

## 🔧 Configuration

### Environment Variables
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### Key Configuration Files
- `config/kong.conf` - Kong server settings
- `declarative/kong.yml` - Service definitions
- `docker-compose.yml` - Container orchestration
- `plugins/jwt-custom/` - Custom JWT plugin

## 📈 Performance

### Rate Limiting
- 1000 requests/minute per consumer
- 10000 requests/hour per consumer
- Configurable per service

### Caching
- Redis-backed rate limiting
- Plugin-level caching
- Database connection pooling

### Scaling
```bash
# Scale Kong instances
docker-compose up -d --scale kong=3

# Configure load balancer
# Update upstream configuration
```

## 🚨 Troubleshooting

### Common Issues

#### Database Connection
```bash
# Check database
docker-compose logs kong-db

# Test connectivity
docker exec -it api-gateway_kong-db_1 psql -U kong -d kong
```

#### Service Registration
```bash
# Re-initialize services
./scripts/init-kong.sh

# Check service status
./scripts/kong-manager.py --command services
```

#### Authentication Issues
```bash
# Test JWT plugin
./scripts/test-api-gateway.sh --test jwt

# Check consumers
./scripts/kong-manager.py --command consumers
```

### Log Analysis
```bash
# View all logs
docker-compose logs -f

# Filter by service
docker-compose logs -f kong
```

## 🔒 Security

### Production Checklist
- [ ] Change default passwords
- [ ] Enable SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring
- [ ] Implement log aggregation
- [ ] Regular security updates

### Security Features
- JWT token validation
- Rate limiting protection
- CORS policy enforcement
- Request sanitization
- Audit logging

## 📚 Additional Resources

- [Kong Documentation](https://docs.konghq.com/)
- [Kong Plugin Development](https://docs.konghq.com/gateway/latest/plugin-development/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Microservices Best Practices](https://microservices.io/)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check troubleshooting section
2. Review logs
3. Consult documentation
4. Submit GitHub issue

---

**Note**: This API Gateway is part of the Wind Power Forecasting System. Ensure all microservices are running before starting the gateway.