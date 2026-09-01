"""Tests for deterministic storyboard fallbacks."""

from __future__ import annotations

import unittest

from agents.storyboard_agent.agent import fallback_storyboard


class FallbackStoryboardTests(unittest.TestCase):
    def test_reuses_verified_narration_instead_of_inventing_filler(self) -> None:
        script_lines = [
            "Rockstar is currently focused on its next release.",
            "The reported priority is the single-player story.",
            "The announced date remains unchanged for now.",
            "Follow for more GTA 6 breakdowns.",
        ]
        config = {
            "scene_count": 6,
            "cta": "Follow for more GTA 6 breakdowns.",
        }

        storyboard = fallback_storyboard("\n".join(script_lines), config)
        scene_lines = [scene["script_line"] for scene in storyboard["scenes"]]

        self.assertEqual(len(scene_lines), 6)
        self.assertTrue(set(scene_lines).issubset(set(script_lines[:-1])))
        self.assertNotIn("The story continues to develop.", scene_lines)
        self.assertEqual(scene_lines[0], script_lines[0])
        self.assertEqual(scene_lines[-1], script_lines[-2])


if __name__ == "__main__":
    unittest.main()
