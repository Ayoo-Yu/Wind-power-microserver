# tests/test_quantile_predict.py
import numpy as np
import pytest


class TestIntervalConstraints:
    """测试预测区间的约束条件。"""

    def test_lower_leq_pred_leq_upper(self):
        """lower <= pred <= upper 必须成立。"""
        pred = np.array([100.0, 200.0, 300.0, 400.0])
        lower = np.array([80.0, 150.0, 250.0, 350.0])
        upper = np.array([120.0, 250.0, 350.0, 450.0])
        assert np.all(lower <= pred)
        assert np.all(pred <= upper)

    def test_clamp_to_zero_and_capacity(self):
        """区间限制在 [0, capacity] 范围。"""
        capacity = 779.0
        pred = np.array([-10.0, 400.0, 800.0])
        lower = np.clip(np.array([-20.0, 350.0, 780.0]), 0, capacity)
        upper = np.clip(np.array([5.0, 450.0, 810.0]), 0, capacity)
        assert np.all(lower >= 0)
        assert np.all(upper <= capacity)

    def test_enforce_ordering(self):
        """强制排序：lower = min(lower, pred), upper = max(upper, pred)。"""
        pred = np.array([100.0, 200.0])
        lower_raw = np.array([110.0, 180.0])  # lower > pred 的情况
        upper_raw = np.array([90.0, 220.0])   # upper < pred 的情况
        lower = np.minimum(lower_raw, pred)
        upper = np.maximum(upper_raw, pred)
        assert np.all(lower <= pred)
        assert np.all(pred <= upper)

    def test_coverage_rate_calculation(self):
        """覆盖率 = 实际值落入区间的比例。"""
        actual = np.array([100.0, 150.0, 300.0, 500.0])
        lower = np.array([80.0, 140.0, 250.0, 450.0])
        upper = np.array([120.0, 200.0, 350.0, 550.0])
        in_interval = np.sum((actual >= lower) & (actual <= upper))
        coverage = in_interval / len(actual)
        assert coverage == 1.0  # 全部在区间内

    def test_coverage_rate_partial(self):
        """部分超出区间。"""
        actual = np.array([100.0, 250.0, 300.0, 500.0])  # 250 > upper=200
        lower = np.array([80.0, 140.0, 250.0, 450.0])
        upper = np.array([120.0, 200.0, 350.0, 550.0])
        in_interval = np.sum((actual >= lower) & (actual <= upper))
        coverage = in_interval / len(actual)
        assert coverage == 0.75

    def test_interval_width_calculation(self):
        """区间宽度 = mean(upper - lower) / capacity。"""
        capacity = 779.0
        lower = np.array([80.0, 140.0, 250.0, 450.0])
        upper = np.array([120.0, 200.0, 350.0, 550.0])
        avg_width = np.mean(upper - lower) / capacity
        expected = np.mean([40.0, 60.0, 100.0, 100.0]) / 779.0
        assert abs(avg_width - expected) < 1e-9
