"""Tests for GTA 6 compilation discovery and metadata."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pipelines.gta6_compilation_pipeline import build_metadata, discover_completed_videos


class CompilationPipelineTests(unittest.TestCase):
    def test_discovers_only_timestamped_graphics_masters(self) -> None:
        with TemporaryDirectory() as folder:
            root = Path(folder)
            final = root / "channels" / "gta6" / "videos" / "final"
            final.mkdir(parents=True)
            wanted = final / "2026-08-10_19-35-40_gta6_graphics.mp4"
            wanted.touch()
            (final / "2026-08-10_19-34-06_gta6_video.mp4").touch()
            (final / "latest_video_graphics.mp4").touch()

            self.assertEqual(discover_completed_videos(root), [wanted])

    def test_metadata_contains_source_count_and_chapters(self) -> None:
        sources = [
            {"path": "/tmp/channels/gta6/videos/final/2026-08-01_10-00-00_gta6_graphics.mp4", "duration": 30},
            {"path": "/tmp/channels/gta6_longform/videos/final/2026-08-02_10-00-00_gta6_longform_graphics.mp4", "duration": 125},
        ]

        metadata = build_metadata(sources)

        self.assertEqual(metadata["source_video_count"], 2)
        self.assertIn("0:00 GTA 6 update 1", metadata["description"])
        self.assertIn("0:30 Long-form analysis 1", metadata["description"])
        self.assertEqual(metadata["video_format"], "long-form")


if __name__ == "__main__":
    unittest.main()
