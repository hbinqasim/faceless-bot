"""Tests for high-CTR long-form thumbnail behavior."""

from __future__ import annotations

import unittest

from PIL import Image

from services.thumbnail.service import derive_topic_hook, score_thumbnail_frame, split_hook_lines


class LongformThumbnailTests(unittest.TestCase):
    def test_topic_hooks_are_specific_instead_of_generic(self) -> None:
        self.assertEqual(
            derive_topic_hook({"title": "Take-Two sees more room for monetization"}),
            "PLAYERS PAY MORE?",
        )
        self.assertEqual(
            derive_topic_hook({"title": "Netflix reveal is only an appetizer"}),
            "MORE REVEALS COMING",
        )
        self.assertNotEqual(derive_topic_hook({"title": "A surprising new detail"}), "BIG UPDATE")

    def test_detailed_frame_scores_above_flat_frame(self) -> None:
        flat = Image.new("RGB", (320, 180), (110, 110, 110))
        detailed = Image.new("RGB", (320, 180), (25, 25, 25))
        pixels = detailed.load()
        for y in range(detailed.height):
            for x in range(detailed.width):
                if (x // 12 + y // 12) % 2:
                    pixels[x, y] = (230, 150, 30)

        self.assertGreater(score_thumbnail_frame(detailed), score_thumbnail_frame(flat))

    def test_hook_wraps_to_at_most_two_lines(self) -> None:
        self.assertEqual(split_hook_lines("MORE REVEALS COMING"), ["MORE REVEALS", "COMING"])


if __name__ == "__main__":
    unittest.main()
