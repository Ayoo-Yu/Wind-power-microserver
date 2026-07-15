from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TEST_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEST_ROOT))

from scada_testbed.nwp_simulator import NwpSimulator  # noqa: E402


class NwpSimulatorTests(unittest.TestCase):
    def make_simulator(self, output_root: str) -> NwpSimulator:
        environment = {
            "SCADA_CATALOG_PATH": str(TEST_ROOT / "config" / "point-catalog.json"),
            "NWP_OUTPUT_ROOT": output_root,
            "NWP_HORIZON_STEPS": "8",
            "NWP_UPDATE_INTERVAL_SECONDS": "60",
            "NWP_SCENARIO": "normal",
        }
        with patch.dict(os.environ, environment, clear=False):
            return NwpSimulator()

    @staticmethod
    def read_rows(path: str) -> list[dict[str, str]]:
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_generates_deterministic_shape_for_every_farm(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            simulator = self.make_simulator(folder)
            files = simulator.generate()
            self.assertEqual(len(files), len(simulator.catalog["farms"]))
            for file_path in files:
                rows = self.read_rows(file_path)
                self.assertEqual(len(rows), 8 * 4)
                self.assertIn("100u", rows[0])
                self.assertIn("forecast_time", rows[0])

    def test_fault_scenarios_are_observable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            simulator = self.make_simulator(folder)
            simulator.scenario = "missing"
            missing_rows = self.read_rows(simulator.generate()[0])
            self.assertTrue(any(row["100u"] == "" for row in missing_rows))

            simulator.scenario = "malformed"
            malformed_rows = self.read_rows(simulator.generate()[0])
            self.assertEqual(malformed_rows[0]["forecast_time"], "invalid-time")

            sequence = simulator.sequence
            simulator.scenario = "stale"
            self.assertEqual(simulator.generate(), [])
            self.assertEqual(simulator.sequence, sequence)


if __name__ == "__main__":
    unittest.main()
