"""Tests for resilient background-music generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.music import service


class MusicRecoveryTests(unittest.TestCase):
    def config(self, folder: Path, allow_no_music: bool = True) -> dict[str, object]:
        return {
            "enabled": True,
            "service_name": "music",
            "channel": "test",
            "script_path": str(folder / "script.txt"),
            "knowledge_path": str(folder / "knowledge.json"),
            "output_folder": str(folder),
            "output_audio_path": str(folder / "current_music.mp3"),
            "reuse_existing_on_failure": True,
            "allow_no_music_on_failure": allow_no_music,
        }

    def test_search_failure_reuses_existing_track(self) -> None:
        with tempfile.TemporaryDirectory() as raw_folder:
            folder = Path(raw_folder)
            music = folder / "current_music.mp3"
            music.write_bytes(b"existing")
            with (
                patch.object(service, "load_config", return_value=self.config(folder)),
                patch.object(service, "build_music_query", return_value="energetic hype urban"),
                patch.object(service, "search_jamendo_music", side_effect=RuntimeError("no track")),
            ):
                result = service.run()

            self.assertEqual(result["status"], "reused_existing")
            self.assertEqual(music.read_bytes(), b"existing")

    def test_search_failure_can_continue_without_music(self) -> None:
        with tempfile.TemporaryDirectory() as raw_folder:
            folder = Path(raw_folder)
            with (
                patch.object(service, "load_config", return_value=self.config(folder)),
                patch.object(service, "build_music_query", return_value="energetic hype urban"),
                patch.object(service, "search_jamendo_music", side_effect=RuntimeError("no track")),
            ):
                result = service.run()

            self.assertEqual(result["status"], "skipped")
            self.assertIsNone(result["music_path"])


if __name__ == "__main__":
    unittest.main()
