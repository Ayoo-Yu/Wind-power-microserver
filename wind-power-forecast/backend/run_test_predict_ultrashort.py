"""Run one ultra-short-term prediction for one farm.

Usage:  python run_test_predict_ultrashort.py bnj
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from db_session import db_session
from services.forecast_service import run_ultrashort_prediction
from services.model_manager import ModelManager
from services.calibration_manager import CalibrationManager

farm_code = sys.argv[1] if len(sys.argv) > 1 else "bnj"

print(f"=== Predicting {farm_code} supershort ===")
mm = ModelManager()
cm = CalibrationManager()

with db_session() as session:
    result = run_ultrashort_prediction(farm_code, mm, cm, session)

print(f"\nResult: {result}")
