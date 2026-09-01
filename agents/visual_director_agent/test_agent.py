"""Tests for generated visual-plan normalization."""

from __future__ import annotations

import unittest

from agents.visual_director_agent.agent import normalize_scene


class VisualPlanNormalizationTests(unittest.TestCase):
    def test_removes_logos_brand_names_and_readable_signs(self) -> None:
        scene = {
            "scene_number": 1,
            "script_line": "Rockstar announced a new collaboration.",
            "visual_subject": "Netflix logo on a television",
            "foreground": "Netflix logo on the TV screen",
            "midground": "office door with a sign that reads Strauss Zelnick",
            "background": "Take-Two headquarters",
            "visual_world": "Rockstar branded office",
        }
        fallback = {
            "scene_number": 1,
            "purpose": "hook",
            "emotion": "curiosity",
            "shot_type": "close-up",
        }

        normalized = normalize_scene(scene, fallback, 1)
        visual_text = " ".join(
            str(normalized[field])
            for field in ("visual_subject", "foreground", "midground", "background", "visual_world")
        ).lower()

        self.assertNotIn("logo", visual_text)
        self.assertNotIn("netflix", visual_text)
        self.assertNotIn("take-two", visual_text)
        self.assertNotIn("rockstar", visual_text)
        self.assertNotIn("sign that reads", visual_text)
        self.assertEqual(normalized["foreground"], "story-relevant real-world object")


if __name__ == "__main__":
    unittest.main()
