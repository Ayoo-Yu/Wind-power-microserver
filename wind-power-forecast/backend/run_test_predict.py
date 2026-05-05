"""Run daily prediction for one farm to test the pipeline.

Usage:  python run_test_predict.py bnj short
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)

from db_session import db_session
from services.forecast_service import run_daily_prediction
from services.model_manager import ModelManager
from services.calibration_manager import CalibrationManager

farm_code = sys.argv[1] if len(sys.argv) > 1 else 'bnj'
forecast_type = sys.argv[2] if len(sys.argv) > 2 else 'short'

print(f"=== Predicting {farm_code} {forecast_type} ===")
mm = ModelManager()
cm = CalibrationManager()

with db_session() as session:
    result = run_daily_prediction(farm_code, forecast_type, mm, cm, session)

print(f"\nResult: {result}")
