"""Run monthly training for one farm to test the pipeline.

Usage:  python run_test_train.py bnj short
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)

from db_session import db_session
from services.forecast_service import run_monthly_training
from services.model_manager import ModelManager

farm_code = sys.argv[1] if len(sys.argv) > 1 else 'bnj'
forecast_type = sys.argv[2] if len(sys.argv) > 2 else 'short'

print(f"=== Training {farm_code} {forecast_type} ===")
mm = ModelManager()

with db_session() as session:
    result = run_monthly_training(farm_code, forecast_type, mm, session)

print(f"\nResult: {result}")
