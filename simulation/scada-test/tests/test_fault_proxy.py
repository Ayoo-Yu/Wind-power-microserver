from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEST_ROOT))

from scada_testbed.fault_proxy import FaultState  # noqa: E402


class FaultStateTests(unittest.TestCase):
    def test_fault_settings_are_applied(self) -> None:
        state = FaultState()
        settings = state.configure(
            {
                "enabled": True,
                "latency_ms": 250,
                "jitter_ms": 25,
                "bandwidth_kbps": 64,
                "close_after_bytes": 4096,
            }
        )
        self.assertEqual(settings.latency_ms, 250)
        self.assertEqual(settings.jitter_ms, 25)
        self.assertEqual(settings.bandwidth_kbps, 64)
        self.assertEqual(settings.close_after_bytes, 4096)

    def test_invalid_fault_settings_are_rejected(self) -> None:
        state = FaultState()
        with self.assertRaises(ValueError):
            state.configure({"latency_ms": -1})
        with self.assertRaises(ValueError):
            state.configure({"unknown": 1})

    def test_reset_restores_clean_link(self) -> None:
        state = FaultState()
        state.configure({"enabled": False, "latency_ms": 100})
        settings = state.reset()
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.latency_ms, 0)


if __name__ == "__main__":
    unittest.main()
