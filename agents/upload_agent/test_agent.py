"""Tests for YouTube authentication recovery."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from google.auth.exceptions import RefreshError

from agents.upload_agent.agent import get_youtube_service
import youtube_uploader


class YouTubeAuthenticationTests(unittest.TestCase):
    @patch("agents.upload_agent.agent.pickle.dump")
    @patch("agents.upload_agent.agent.pickle.load")
    @patch("agents.upload_agent.agent.build")
    @patch("agents.upload_agent.agent.InstalledAppFlow.from_client_secrets_file")
    def test_revoked_refresh_token_starts_browser_reauthorization(
        self,
        from_client_secrets_file: Mock,
        build: Mock,
        pickle_load: Mock,
        pickle_dump: Mock,
    ) -> None:
        with TemporaryDirectory() as folder:
            root = Path(folder)
            token_path = root / "token.pickle"
            secret_path = root / "client_secret.json"
            token_path.touch()
            secret_path.write_text("{}", encoding="utf-8")

            expired = Mock(valid=False, expired=True, refresh_token="revoked")
            expired.refresh.side_effect = RefreshError("invalid_grant")
            fresh = Mock(valid=True)
            flow = from_client_secrets_file.return_value
            flow.run_local_server.return_value = fresh
            pickle_load.return_value = expired

            service = get_youtube_service(
                {
                    "token_file": str(token_path),
                    "client_secret_file": str(secret_path),
                }
            )

            expired.refresh.assert_called_once()
            flow.run_local_server.assert_called_once_with(
                port=0,
                access_type="offline",
                prompt="consent",
            )
            pickle_dump.assert_called_once_with(fresh, unittest.mock.ANY)
            build.assert_called_once_with("youtube", "v3", credentials=fresh)
            self.assertEqual(service, build.return_value)

    @patch("youtube_uploader.pickle.dump")
    @patch("youtube_uploader.pickle.load")
    @patch("youtube_uploader.build")
    @patch("youtube_uploader.authorize_with_browser")
    def test_legacy_uploader_also_recovers_from_revoked_token(
        self,
        authorize_with_browser: Mock,
        build: Mock,
        pickle_load: Mock,
        pickle_dump: Mock,
    ) -> None:
        with TemporaryDirectory() as folder:
            token_path = Path(folder) / "legacy-token.pickle"
            token_path.touch()

            expired = Mock(valid=False, expired=True, refresh_token="revoked")
            expired.refresh.side_effect = RefreshError("invalid_grant")
            fresh = Mock(valid=True)
            pickle_load.return_value = expired
            authorize_with_browser.return_value = fresh

            with (
                patch.object(youtube_uploader, "TOKEN_FILE", str(token_path)),
                patch.object(
                    youtube_uploader,
                    "CLIENT_SECRET_FILE",
                    str(Path(folder) / "client_secret.json"),
                ),
            ):
                service = youtube_uploader.get_youtube_service()

            authorize_with_browser.assert_called_once_with(
                Path(folder) / "client_secret.json",
                youtube_uploader.SCOPES,
            )
            pickle_dump.assert_called_once_with(fresh, unittest.mock.ANY)
            self.assertEqual(service, build.return_value)


if __name__ == "__main__":
    unittest.main()
