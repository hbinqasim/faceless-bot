"""Tests for long-form narration rate calibration."""

from __future__ import annotations

import unittest

from services.narration.service import calculate_adaptive_rate


class NarrationRateTests(unittest.TestCase):
    def test_slightly_short_audio_gets_small_natural_adjustment(self) -> None:
        self.assertEqual(calculate_adaptive_rate(117.84, 122.0, "+5%"), "+1%")

    def test_adjustment_respects_slow_rate_floor(self) -> None:
        self.assertEqual(calculate_adaptive_rate(90.0, 122.0, "+5%"), "-5%")

    def test_invalid_rate_defaults_to_neutral_math(self) -> None:
        self.assertEqual(calculate_adaptive_rate(120.0, 120.0, "fast"), "+0%")


if __name__ == "__main__":
    unittest.main()
