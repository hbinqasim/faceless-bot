"""Tests for the Pollinations image provider's failure handling."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from services.image_generation.pollinations_provider import PollinationsProvider


class PollinationsProviderTests(TestCase):
    def setUp(self) -> None:
        self.provider = PollinationsProvider(
            {
                "pollinations_max_attempts": 3,
                "pollinations_retry_backoff_seconds": 0,
            }
        )

    @staticmethod
    def response(status_code: int, content: bytes = b"") -> Mock:
        response = Mock(spec=requests.Response)
        response.ok = 200 <= status_code < 300
        response.status_code = status_code
        response.text = content.decode(errors="replace")
        response.content = content
        response.headers = {}
        response.url = "https://example.test/generated"
        return response

    @patch("services.image_generation.pollinations_provider.requests.get")
    def test_retries_temporary_upstream_failure(self, get: Mock) -> None:
        get.side_effect = [
            self.response(500, b"upstream failed"),
            self.response(502, b"bad gateway"),
            self.response(200, b"image data"),
        ]

        with TemporaryDirectory() as folder:
            result = self.provider.generate_image("prompt", Path(folder) / "scene.jpg")
            image_path = Path(result["image_path"])

            self.assertEqual(image_path.read_bytes(), b"image data")
            self.assertEqual(get.call_count, 3)

    @patch("services.image_generation.pollinations_provider.requests.get")
    def test_does_not_retry_permanent_client_error(self, get: Mock) -> None:
        get.return_value = self.response(400, b"invalid prompt")

        with TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "400 invalid prompt"):
                self.provider.generate_image("prompt", Path(folder) / "scene.jpg")

        get.assert_called_once()

    @patch("services.image_generation.pollinations_provider.requests.get")
    def test_reports_exhausted_network_retries(self, get: Mock) -> None:
        get.side_effect = requests.Timeout("timed out")

        with TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
                self.provider.generate_image("prompt", Path(folder) / "scene.jpg")

        self.assertEqual(get.call_count, 3)
