# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

This is a wind power forecasting system (风电功率预测系统) with multiple components:
- **Backend**: Flask-based API server with PostgreSQL/KingBase database
- **Frontend**: Vue.js web interface
- **Data Processing**: Python scripts for meteorological data processing and power prediction
- **Auto-reporting**: Automated scheduler for power data reporting
- **SCADA Integration**: C104 protocol integration for real-time data

## Development Commands

### Backend Development
```bash
# Navigate to backend directory
cd wind-power-forecast/backend

# Install dependencies (uses conda environment)
conda env create -f environment.yml
conda activate wind-power-env

# Run development server
python app.py

# Run with gunicorn (production)
gunicorn -w 4 -k gevent -b 0.0.0.0:5000 app:app

# Database migrations
alembic upgrade head
```

### Frontend Development
```bash
# Navigate to frontend directory
cd wind-power-forecast/frontend

# Install dependencies
npm install

# Development server
npm run serve

# Production build
npm run build

# Lint code
npm run lint
```

### Docker Development
```bash
# Start full stack with docker-compose
cd wind-power-forecast
docker-compose -f frontend-backend-compose.yaml up -d

# Check logs
docker-compose -f frontend-backend-compose.yaml logs -f

# Stop services
docker-compose -f frontend-backend-compose.yaml down
```

### Testing
```bash
# Test scheduler functionality
cd wind-power-forecast
python test_scheduler.py

# Database connection check
cd wind-power-forecast/backend
python check_db.py
```

## Architecture Overview

### Backend Structure (wind-power-forecast/backend/)
- **app.py**: Main Flask application entry point with gevent monkey patching
- **config.py**: Configuration management with environment variables
- **database_config.py**: SQLAlchemy database setup and connection
- **db_models/**: Database models using SQLAlchemy ORM
- **services/**: Business logic services (file handling, predictions, reporting)
- **routes/**: API endpoint definitions
- **auto_scripts/**: Automated prediction and reporting scripts
- **utils/**: Utility functions and helpers

### Key Features
1. **Multi-timescale Predictions**: 超短期(15min), 短期(4h), 中期(72h) predictions
2. **Operational Data Management**: CSV upload for 7 types of operational data
3. **Auto-reporting Scheduler**: Precise 15-minute interval reporting with APScheduler
4. **Real-time Data**: WebSocket integration for live data updates
5. **Multi-database Support**: PostgreSQL and KingBase database compatibility

### Data Flow
1. **Meteorological Data**: External APIs → Data processing scripts → Database
2. **SCADA Data**: C104 protocol → Real-time processing → Database
3. **Predictions**: Historical data → ML models → Prediction results → Database
4. **Reporting**: Database → Scheduled reporting → External systems

### Environment Configuration
Key environment variables (set in docker-compose or .env):
- Database: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
- MinIO/S3: MINIO_ENDPOINT, MINIO_PORT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
- JWT: JWT_SECRET_KEY
- Redis: REDIS_HOST, REDIS_PORT

### Database Schema
The system uses operational data tables:
- wind_speed_data: Individual turbine wind speed data
- turbine_power_data: Individual turbine power output
- weather_data: Weather station data
- installed_capacity_data: Wind farm capacity information
- available_capacity_data: Available capacity and fault info
- theoretical_power_data: Theoretical power calculations
- available_power_data: Available power and constraints

### API Endpoints
- `/operational/api/upload_operational_csv`: CSV data upload
- `/api/report/*`: Auto-reporting configuration and control
- `/api/prediction/*`: Prediction results and management
- `/api/scheduler/*`: Scheduler control and status

### Important Notes
- Always use gevent monkey patch at the start of any script
- Database migrations use Alembic - run upgrades before starting services
- The auto-reporting scheduler runs on precise 15-minute intervals (XX:14:30, XX:29:30, XX:44:30, XX:59:30)
- CSV uploads require UTF-8 encoding and specific timestamp format (YYYY-MM-DD HH:MM:SS)
- KingBase database requires specific connection parameters and schema adjustments