from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEST_ROOT))

from scada_testbed.engine import (  # noqa: E402
    ConfigurationError,
    ScenarioEngine,
    load_json,
    power_curve_fraction,
    validate_catalog,
    validate_scenarios,
)


class ScenarioEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_json(TEST_ROOT / "config" / "point-catalog.json")
        cls.scenarios = load_json(TEST_ROOT / "config" / "scenarios.json")

    def make_engine(self) -> ScenarioEngine:
        return ScenarioEngine(self.catalog, self.scenarios)

    def test_configuration_is_valid(self) -> None:
        validate_catalog(self.catalog)
        validate_scenarios(self.scenarios)

    def test_reset_reproduces_the_same_frame(self) -> None:
        engine = self.make_engine()
        now = datetime(2026, 7, 15, 4, 0, tzinfo=timezone.utc)
        first = engine.tick(now)
        engine.tick(now + timedelta(seconds=2))
        engine.reset()
        replayed = engine.tick(now)
        self.assertEqual(first.sequence, replayed.sequence)
        self.assertEqual(first.farms, replayed.farms)

    def test_normal_frame_is_physically_coherent(self) -> None:
        frame = self.make_engine().tick(
            datetime(2026, 7, 15, 4, 0, tzinfo=timezone.utc)
        )
        for values in frame.farms.values():
            self.assertGreaterEqual(values["active_power_mw"], 0)
            self.assertLessEqual(
                values["active_power_mw"], values["theoretical_power_mw"] + 0.001
            )
            self.assertLessEqual(
                values["active_power_mw"], values["available_power_mw"] + 0.001
            )
            self.assertGreaterEqual(values["availability_pct"], 0)
            self.assertLessEqual(values["availability_pct"], 100)

    def test_ramp_up_increases_theoretical_power(self) -> None:
        engine = self.make_engine()
        engine.select("ramp_up")
        values = [engine.tick().farms["CF"]["theoretical_power_mw"] for _ in range(30)]
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[-1], values[0])

    def test_curtailment_honours_configured_limit(self) -> None:
        engine = self.make_engine()
        engine.select("curtailment")
        frame = engine.tick()
        capacities = {
            farm["farm_code"]: float(farm["capacity_mw"])
            for farm in self.catalog["farms"]
        }
        for farm_code, values in frame.farms.items():
            self.assertLessEqual(values["active_power_mw"], capacities[farm_code] * 0.4 + 0.001)

    def test_turbine_trip_marks_target_unavailable(self) -> None:
        engine = self.make_engine()
        engine.select("turbine_trip")
        frame = None
        for _ in range(5):
            frame = engine.tick()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.farms["SDS"]["availability_pct"], 0)
        self.assertEqual(frame.farms["SDS"]["active_power_mw"], 0)

    def test_invalid_quality_scenario(self) -> None:
        engine = self.make_engine()
        engine.select("invalid_quality")
        self.assertEqual(engine.tick().quality, "Invalid")

    def test_stale_scenario_freezes_sequence_and_transmission(self) -> None:
        engine = self.make_engine()
        engine.select("stale")
        first = engine.tick()
        second = engine.tick()
        third = engine.tick()
        stale = engine.tick()
        self.assertEqual((first.sequence, second.sequence, third.sequence), (1, 2, 3))
        self.assertEqual(stale.sequence, 3)
        self.assertFalse(stale.transmit)
        self.assertFalse(engine.snapshot()["frame"]["transmit"])

    def test_clock_skew_is_visible_in_source_time(self) -> None:
        engine = self.make_engine()
        engine.select("clock_skew")
        now = datetime(2026, 7, 15, 4, 0, tzinfo=timezone.utc)
        frame = engine.tick(now)
        source_time = datetime.fromisoformat(frame.source_time)
        self.assertEqual(source_time - now, timedelta(minutes=5))

    def test_unknown_scenario_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            self.make_engine().select("missing")

    def test_power_curve_boundaries(self) -> None:
        self.assertEqual(power_curve_fraction(2.9), 0)
        self.assertEqual(power_curve_fraction(12.0), 1)
        self.assertEqual(power_curve_fraction(25.0), 0)


if __name__ == "__main__":
    unittest.main()
