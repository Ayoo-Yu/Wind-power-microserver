FROM wind-power-scada-simulator:v1

WORKDIR /app

COPY simulation/scada-test/scada_testbed /app/scada_testbed
COPY simulation/scada-test/config /app/config
COPY wind-power-forecast/backend/services/scada_worker.py /app/production/scada_worker.py

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SCADA_CATALOG_PATH=/app/config/point-catalog.json \
    SCADA_SCENARIOS_PATH=/app/config/scenarios.json

EXPOSE 2404 2405 8080 8081 8084 8090

CMD ["python3", "-m", "scada_testbed.simulator"]
