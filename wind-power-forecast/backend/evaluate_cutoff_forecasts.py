"""Evaluate production forecast algorithms before a fixed actual-power cutoff.

This script is read-only with respect to the database and model directories.
It reuses services.forecast_service training/evaluation functions, filters
training rows to timestamps <= the cutoff, and writes CSV/JSON summaries under
forecast_eval_results.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

from db_session import db_session
from farm_registry.farms_config import get_all_farms
from services.forecast_service import (
    load_training_data_from_db,
    split_train_calibrate,
    train_ensemble,
    train_ultrashort_ensemble,
)


DEFAULT_CUTOFF = "2025-07-15 23:45:00"
DEFAULT_TYPES = ("short", "medium", "supershort")


def _type_to_feature_table(farm: dict, forecast_type: str) -> str:
    if forecast_type == "medium":
        return farm["mid_table"]
    if forecast_type == "supershort":
        return farm["supershort_table"]
    return farm["short_table"]


def _short_medium_metrics(models: dict, feature_columns: list[str], meta: dict, test_df: pd.DataFrame, cap: float) -> dict:
    raw_metrics = meta.get("raw_accuracy") or {}
    cal_metrics = meta.get("cal_accuracy") or {}
    init_cal = meta.get("init_calibration") or {}
    return {
        "raw_accuracy_percent": raw_metrics.get("accuracy_percent"),
        "raw_weighted_rmse": raw_metrics.get("weighted_rmse"),
        "raw_mae": raw_metrics.get("mae"),
        "raw_r2": raw_metrics.get("r2"),
        "raw_bias": raw_metrics.get("bias"),
        "cal_accuracy_percent": cal_metrics.get("accuracy_percent"),
        "cal_weighted_rmse": cal_metrics.get("weighted_rmse"),
        "cal_mae": cal_metrics.get("mae"),
        "cal_r2": cal_metrics.get("r2"),
        "cal_bias": cal_metrics.get("bias"),
        "cal_alpha": init_cal.get("alpha"),
        "cal_beta": init_cal.get("beta"),
        "cal_method": (meta.get("dynamic_calibration") or {}).get("method"),
    }


def _ultrashort_metrics(shift_models: dict, meta: dict, train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, cap: float) -> dict:
    raw_metrics = meta.get("raw_accuracy") or {}
    cal_metrics = meta.get("cal_accuracy") or {}
    dynamic = meta.get("dynamic_calibration") or {}
    dynamic_results = dynamic.get("results", [])
    raw_row = next((r for r in dynamic_results if r.get("method") == "raw"), None)
    if raw_row:
        raw_metrics = dict(raw_metrics)
        raw_metrics["accuracy_percent"] = raw_row.get("accuracy_percent")
    return {
        "raw_accuracy_percent": raw_metrics.get("accuracy_percent"),
        "raw_weighted_rmse": raw_metrics.get("weighted_rmse"),
        "raw_mae": raw_metrics.get("mae"),
        "raw_r2": raw_metrics.get("r2"),
        "raw_bias": raw_metrics.get("bias"),
        "cal_accuracy_percent": cal_metrics.get("accuracy_percent"),
        "cal_weighted_rmse": cal_metrics.get("weighted_rmse"),
        "cal_mae": cal_metrics.get("mae"),
        "cal_r2": cal_metrics.get("r2"),
        "cal_bias": cal_metrics.get("bias"),
        "cal_method": dynamic.get("method"),
        "cal_results": json.dumps(dynamic_results, ensure_ascii=False),
    }


def _evaluate_one(session, farm: dict, forecast_type: str, cutoff: pd.Timestamp) -> dict:
    farm_code = farm["farm_code"]
    cap = float(farm["capacity_mw"])
    feature_table = _type_to_feature_table(farm, forecast_type)

    started = time.time()
    df = load_training_data_from_db(session, feature_table, farm_code)
    raw_rows = int(len(df))
    if df.empty:
        return {
            "farm_code": farm_code,
            "farm_name": farm["name"],
            "forecast_type": forecast_type,
            "status": "error",
            "message": f"No rows loaded from {feature_table}",
            "raw_rows": raw_rows,
        }

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df[df["Timestamp"] <= cutoff].copy()
    cutoff_rows = int(len(df))
    df = df.dropna(subset=["Total_Power"]).sort_values("Timestamp").reset_index(drop=True)
    label_rows = int(len(df))

    if label_rows < 100:
        return {
            "farm_code": farm_code,
            "farm_name": farm["name"],
            "forecast_type": forecast_type,
            "status": "error",
            "message": f"Insufficient labeled rows after cutoff ({label_rows})",
            "raw_rows": raw_rows,
            "cutoff_rows": cutoff_rows,
            "label_rows": label_rows,
        }

    train_df, val_df, test_df = split_train_calibrate(df)
    if forecast_type == "supershort":
        shift_models, meta = train_ultrashort_ensemble(train_df, val_df, test_df, cap)
        eval_metrics = _ultrashort_metrics(shift_models, meta, train_df, val_df, test_df, cap)
    else:
        models, feature_columns, meta = train_ensemble(train_df, val_df, test_df, cap)
        eval_metrics = _short_medium_metrics(models, feature_columns, meta, test_df, cap)

    return {
        "farm_code": farm_code,
        "farm_name": farm["name"],
        "forecast_type": forecast_type,
        "status": "ok",
        "feature_table": feature_table,
        "raw_rows": raw_rows,
        "cutoff_rows": cutoff_rows,
        "label_rows": label_rows,
        "train_rows": meta.get("n_samples"),
        "val_rows": meta.get("n_val_samples"),
        "test_rows": meta.get("n_test_samples"),
        "n_features": meta.get("n_features"),
        "n_shifts": meta.get("n_shifts"),
        **eval_metrics,
        "elapsed_sec": round(time.time() - started, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    parser.add_argument("--types", nargs="+", default=list(DEFAULT_TYPES), choices=list(DEFAULT_TYPES))
    parser.add_argument("--farms", nargs="+", default=None)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()
    os.environ.setdefault("ULTRASHORT_FULL_CAL_EVAL", "1")

    cutoff = pd.Timestamp(args.cutoff)
    farms = get_all_farms()
    if args.farms:
        requested = {f.lower() for f in args.farms}
        farms = [f for f in farms if f["farm_code"].lower() in requested]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir or Path(__file__).resolve().parent / "forecast_eval_results" / f"cutoff_{timestamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with db_session() as session:
        for farm in farms:
            for forecast_type in args.types:
                print(f"[RUN] {farm['farm_code']} {forecast_type} cutoff={cutoff}")
                try:
                    result = _evaluate_one(session, farm, forecast_type, cutoff)
                except Exception as exc:
                    result = {
                        "farm_code": farm["farm_code"],
                        "farm_name": farm["name"],
                        "forecast_type": forecast_type,
                        "status": "error",
                        "message": str(exc),
                    }
                results.append(result)
                print(json.dumps(result, ensure_ascii=False, default=str))

    summary = pd.DataFrame(results)
    csv_path = out_dir / "summary.csv"
    json_path = out_dir / "summary.json"
    summary.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[DONE] wrote {csv_path}")
    print(f"[DONE] wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
