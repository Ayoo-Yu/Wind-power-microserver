import json
import os
import tempfile
import shutil

import numpy as np
import pytest


@pytest.fixture
def tmp_cal_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def test_save_and_load_params(tmp_cal_dir):
    from services.calibration_manager import CalibrationManager
    mgr = CalibrationManager(base_dir=tmp_cal_dir)

    mgr.save("dplz", "short", alpha=1.05, beta=-2.3)
    params = mgr.load("dplz", "short")
    assert params is not None
    assert abs(params["alpha"] - 1.05) < 1e-6
    assert abs(params["beta"] - (-2.3)) < 1e-6


def test_load_missing_returns_none(tmp_cal_dir):
    from services.calibration_manager import CalibrationManager
    mgr = CalibrationManager(base_dir=tmp_cal_dir)
    assert mgr.load("dplz", "short") is None


def test_calibrate_apply(tmp_cal_dir):
    from services.calibration_manager import CalibrationManager
    mgr = CalibrationManager(base_dir=tmp_cal_dir)
    mgr.save("dplz", "short", alpha=1.0, beta=5.0)

    raw = np.array([10.0, 20.0, 30.0])
    cap = 47.5
    result = mgr.apply("dplz", "short", raw, cap)
    np.testing.assert_array_almost_equal(result, [15.0, 25.0, 35.0])


def test_calibrate_apply_clips(tmp_cal_dir):
    from services.calibration_manager import CalibrationManager
    mgr = CalibrationManager(base_dir=tmp_cal_dir)
    mgr.save("dplz", "short", alpha=1.0, beta=0.0)

    raw = np.array([50.0, -1.0])
    result = mgr.apply("dplz", "short", raw, 47.5)
    assert result[0] == 47.5
    assert result[1] == 0.0


def test_calibrate_no_params_returns_raw(tmp_cal_dir):
    from services.calibration_manager import CalibrationManager
    mgr = CalibrationManager(base_dir=tmp_cal_dir)
    raw = np.array([10.0, 20.0])
    result = mgr.apply("dplz", "short", raw, 47.5)
    np.testing.assert_array_equal(result, raw)
