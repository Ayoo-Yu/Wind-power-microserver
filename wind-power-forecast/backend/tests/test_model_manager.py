import json
import os
import tempfile
import shutil

import numpy as np
import pytest


class FakeModel:
    """Module-level fake model so pickle can serialize it."""

    def __init__(self, val=None):
        self.val = val


@pytest.fixture
def tmp_models_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def test_save_and_load_models(tmp_models_dir):
    from services.model_manager import ModelManager
    mgr = ModelManager(base_dir=tmp_models_dir)

    models = {"lgb": FakeModel(1), "xgb": FakeModel(2), "cb": FakeModel(3)}
    feature_columns = ["wind_speed_100m", "air_density", "hour_sin"]
    meta = {"train_date": "2026-05-01", "n_samples": 10000, "scores": {"accuracy_percent": 85.2}}

    mgr.save("dplz", "short", models, feature_columns, meta)

    loaded = mgr.load("dplz", "short")
    assert set(loaded.keys()) == {"lgb", "xgb", "cb", "feature_columns", "meta"}
    assert loaded["lgb"].val == 1
    assert loaded["feature_columns"] == feature_columns
    assert loaded["meta"]["train_date"] == "2026-05-01"


def test_load_missing_models_returns_none(tmp_models_dir):
    from services.model_manager import ModelManager
    mgr = ModelManager(base_dir=tmp_models_dir)
    result = mgr.load("dplz", "short")
    assert result is None


def test_models_saved_to_correct_path(tmp_models_dir):
    from services.model_manager import ModelManager
    mgr = ModelManager(base_dir=tmp_models_dir)

    models = {"lgb": FakeModel(), "xgb": FakeModel(), "cb": FakeModel()}
    mgr.save("bnj", "mid", models, ["col1"], {})

    assert os.path.exists(os.path.join(tmp_models_dir, "bnj", "mid", "lgb_model.pkl"))
    assert os.path.exists(os.path.join(tmp_models_dir, "bnj", "mid", "xgb_model.pkl"))
    assert os.path.exists(os.path.join(tmp_models_dir, "bnj", "mid", "cb_model.pkl"))
    assert os.path.exists(os.path.join(tmp_models_dir, "bnj", "mid", "feature_columns.json"))
    assert os.path.exists(os.path.join(tmp_models_dir, "bnj", "mid", "meta.json"))
