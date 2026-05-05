"""Run monthly ultra-short-term training for one farm.

Usage:  python run_test_train_ultrashort.py bnj
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
from services.forecast_service import run_ultrashort_monthly_training
from services.model_manager import ModelManager

farm_code = sys.argv[1] if len(sys.argv) > 1 else "bnj"

print(f"=== Training {farm_code} supershort ===")
mm = ModelManager()

with db_session() as session:
    result = run_ultrashort_monthly_training(farm_code, mm, session)

print(f"\nResult: {result}")
