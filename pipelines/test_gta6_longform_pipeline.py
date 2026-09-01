"""Tests for long-form pipeline duration guards."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipelines.gta6_longform_pipeline import validate_script_word_budget


class LongformPipelineGuardTests(unittest.TestCase):
    def test_short_script_is_rejected_before_narration(self) -> None:
        with tempfile.TemporaryDirectory() as raw_folder:
            folder = Path(raw_folder)
            script_path = folder / "script.txt"
            config_path = folder / "script.json"
            script_path.write_text("word " * 259, encoding="utf-8")
            config_path.write_text(
                json.dumps({"target_min_words": 340, "target_max_words": 420}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Resume from step 2"):
                validate_script_word_budget(script_path, config_path)

    def test_script_inside_word_budget_passes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_folder:
            folder = Path(raw_folder)
            script_path = folder / "script.txt"
            config_path = folder / "script.json"
            script_path.write_text("word " * 360, encoding="utf-8")
            config_path.write_text(
                json.dumps({"target_min_words": 340, "target_max_words": 420}),
                encoding="utf-8",
            )

            self.assertEqual(validate_script_word_budget(script_path, config_path), 360)


if __name__ == "__main__":
    unittest.main()
