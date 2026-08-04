"""Tests for varied Pixabay stock-media selection."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from services.image_generation.pixabay_provider import PixabayProvider


class PixabayProviderTests(TestCase):
    @patch.dict(os.environ, {"PIXABAY_API_KEY": "test-key"})
    def test_avoids_previously_used_hit_and_updates_history(self) -> None:
        with TemporaryDirectory() as folder:
            root = Path(folder)
            history_path = root / "history.json"
            history_path.write_text('{"used_hit_ids": [101]}\n', encoding="utf-8")
            provider = PixabayProvider(
                {
                    "pixabay_media_type": "video",
                    "pixabay_history_path": str(history_path),
                    "pixabay_video_qualities": ["medium"],
                }
            )
            provider._get_json = lambda *_args, **_kwargs: {
                "hits": [
                    self.video_hit(101, "https://example.test/old.mp4"),
                    self.video_hit(202, "https://example.test/new.mp4"),
                ]
            }
            provider._download = lambda _url, output: output.write_bytes(b"video")

            result = provider.generate_image("gaming", root / "scene_01.mp4")

            metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
            history = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["pixabay_hit"]["id"], 202)
            self.assertIn("202", history["used_hit_ids"])

    @patch.dict(os.environ, {"PIXABAY_API_KEY": "test-key"})
    @patch("services.image_generation.pixabay_provider.time.sleep")
    @patch("services.image_generation.pixabay_provider.requests.get")
    def test_retries_transient_api_failures(self, mock_get: Mock, mock_sleep: Mock) -> None:
        failed = Mock(ok=False, status_code=500, text="temporary upstream error")
        failed.headers = {}
        succeeded = Mock(ok=True, status_code=200)
        succeeded.json.return_value = {"hits": []}
        mock_get.side_effect = [failed, failed, succeeded]
        provider = PixabayProvider(
            {
                "pixabay_max_request_attempts": 3,
                "pixabay_retry_backoff_seconds": 1,
            }
        )

        result = provider._get_json("https://pixabay.test/api/", {"q": "gaming"})

        self.assertEqual(result, {"hits": []})
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [1, 2])

    @patch.dict(os.environ, {"PIXABAY_API_KEY": "test-key"})
    @patch("services.image_generation.pixabay_provider.time.sleep")
    @patch("services.image_generation.pixabay_provider.requests.get")
    def test_retries_transient_download_failures(
        self, mock_get: Mock, mock_sleep: Mock
    ) -> None:
        with TemporaryDirectory() as folder:
            failed = Mock(ok=False, status_code=503, text="unavailable")
            failed.headers = {"Retry-After": "0"}
            succeeded = Mock(ok=True, status_code=200, content=b"video")
            mock_get.side_effect = [failed, succeeded]
            provider = PixabayProvider({"pixabay_max_request_attempts": 2})
            output = Path(folder) / "scene.mp4"

            provider._download("https://cdn.pixabay.test/scene.mp4", output)

            self.assertEqual(output.read_bytes(), b"video")
            self.assertEqual(mock_get.call_count, 2)
            mock_sleep.assert_not_called()

    @staticmethod
    def video_hit(hit_id: int, url: str) -> dict:
        return {
            "id": hit_id,
            "duration": 12,
            "tags": "video gaming controller",
            "videos": {"medium": {"url": url}},
        }
