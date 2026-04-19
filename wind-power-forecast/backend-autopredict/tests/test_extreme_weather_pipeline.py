"""End-to-end test: ECMWF data → detect → correct → alarm."""
import pytest
import sys
import os
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestFullPipeline:
    """Test the complete detection → correction → alarm flow."""

    def test_high_wind_pipeline(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        # Simulate ECMWF input with high wind
        ecmwf_rows = [
            {"ws100_avg": 28.0, "ws10_avg": 12.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
            {"ws100_avg": 26.0, "ws10_avg": 11.0, "temp_2t_avg": 14.0, "tcwv_avg": 4.0},
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
        ]
        predictions = np.array([200.0, 180.0, 100.0])

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        active = detector.get_active_conditions(conditions)
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        assert len(active) == 2  # rows 0 and 1 are high wind
        assert corrected[0] == 0.0
        assert corrected[1] == 0.0
        assert corrected[2] == 100.0  # normal, unchanged
        assert len(records) == 2

    def test_cold_wave_with_decay_pipeline(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        ecmwf_rows = [
            {"ws100_avg": 8.0, "ws10_avg": 4.0, "temp_2t_avg": -10.0, "tcwv_avg": 5.0, "temp_24h_drop": 12.0},
        ]
        predictions = np.array([300.0])

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        # decay = max(0.3, 0.7 - (abs(-10) - 5) * 0.05) = max(0.3, 0.45) = 0.45
        assert abs(corrected[0] - 135.0) < 0.01
        assert len(records) == 1
        assert records[0]["type"] == "cold_wave"

    def test_mixed_conditions_pipeline(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        ecmwf_rows = [
            {"ws100_avg": 35.0, "ws10_avg": 15.0, "temp_2t_avg": 20.0, "tcwv_avg": 5.0},   # typhoon
            {"ws100_avg": 2.0, "ws10_avg": 1.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},     # calm
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": -2.0, "tcwv_avg": 18.0},    # icing
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},     # normal
        ]
        predictions = np.array([400.0, 50.0, 250.0, 100.0])

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        assert corrected[0] == 0.0     # typhoon → clamp
        assert corrected[1] == 0.0     # calm → clamp
        assert corrected[2] < 250.0    # icing → decay
        assert corrected[2] > 0.0
        assert corrected[3] == 100.0   # normal → unchanged
        assert len(records) == 3

    def test_alarm_injection(self):
        """Verify alarm creation for warning/danger conditions."""
        from services.extreme_weather_detector import ExtremeWeatherDetector

        detector = ExtremeWeatherDetector()
        ecmwf_rows = [
            {"ws100_avg": 35.0, "ws10_avg": 15.0, "temp_2t_avg": 20.0, "tcwv_avg": 5.0},
        ]
        conditions = [detector.detect(r) for r in ecmwf_rows]
        active = detector.get_active_conditions(conditions)

        assert len(active) == 1
        assert active[0].severity == "danger"
        assert active[0].condition_type == "typhoon"

    def test_no_false_positives(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        ecmwf_rows = [
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
        ] * 10
        predictions = np.array([100.0] * 10)

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        active = detector.get_active_conditions(conditions)
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        assert len(active) == 0
        assert len(records) == 0
        assert np.array_equal(corrected, predictions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
