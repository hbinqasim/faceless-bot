"""Pixabay media provider for Vice Studio image generation service."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

try:
    from .provider_base import ProviderBase
except ImportError:  # pragma: no cover
    from provider_base import ProviderBase


class PixabayProvider(ProviderBase):
    """Download free stock media from Pixabay for each scene."""

    def __init__(self, config: dict[str, Any]) -> None:
        load_dotenv()
        self.api_key = os.getenv("PIXABAY_API_KEY")
        if not self.api_key:
            raise RuntimeError("PIXABAY_API_KEY is missing in .env")

        self.media_type = str(config.get("pixabay_media_type", "video")).lower()
        self.orientation = str(config.get("pixabay_orientation", "vertical"))
        self.per_page = int(config.get("pixabay_per_page", 10))
        self.timeout = int(config.get("pixabay_timeout_seconds", 60))
        self.query_fields = list(
            config.get(
                "pixabay_query_fields",
                ["background", "visual_world", "midground", "foreground"],
            )
        )

    def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(metadata or {})
        search_query = self._build_search_query(prompt, payload)

        if self.media_type == "image":
            hit = self._search_images(search_query)
            media_url = hit["largeImageURL"]
            media_path = Path(output_path).with_suffix(".jpg")
        else:
            hit = self._search_videos(search_query)
            media_url = self._best_video_url(hit)
            media_path = Path(output_path).with_suffix(".mp4")

        media_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = self._metadata_path_for(media_path)

        self._download(media_url, media_path)

        payload.update(
            {
                "provider": "pixabay",
                "status": "downloaded",
                "media_type": self.media_type,
                "search_query": search_query,
                "media_path": str(media_path),
                "image_path": str(media_path),
                "metadata_path": str(metadata_path),
                "pixabay_hit": self._safe_hit(hit),
            }
        )

        metadata_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return {
            "image_path": str(media_path),
            "media_path": str(media_path),
            "metadata_path": str(metadata_path),
            "status": "downloaded",
        }

    def _search_videos(self, query: str) -> dict[str, Any]:
        url = "https://pixabay.com/api/videos/"
        params = {
            "key": self.api_key,
            "q": query,
            "per_page": self.per_page,
            "orientation": self.orientation,
            "safesearch": "true",
        }
        data = self._get_json(url, params)
        hits = data.get("hits", [])
        if not hits:
            raise RuntimeError(f"No Pixabay videos found for: {query}")
        return hits[0]

    def _search_images(self, query: str) -> dict[str, Any]:
        url = "https://pixabay.com/api/"
        params = {
            "key": self.api_key,
            "q": query,
            "per_page": self.per_page,
            "orientation": self.orientation,
            "safesearch": "true",
            "image_type": "photo",
        }
        data = self._get_json(url, params)
        hits = data.get("hits", [])
        if not hits:
            raise RuntimeError(f"No Pixabay images found for: {query}")
        return hits[0]

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(f"{url}?{urlencode(params)}", timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Pixabay request failed: {response.status_code} {response.text}")
        return response.json()

    def _download(self, url: str, output_path: Path) -> None:
        response = requests.get(url, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Pixabay download failed: {response.status_code}")
        output_path.write_bytes(response.content)

    @staticmethod
    def _best_video_url(hit: dict[str, Any]) -> str:
        videos = hit.get("videos", {})
        for quality in ("large", "medium", "small", "tiny"):
            item = videos.get(quality)
            if item and item.get("url"):
                return item["url"]
        raise RuntimeError("Pixabay video hit has no downloadable URL.")

    def _build_search_query(self, prompt: str, metadata: dict[str, Any]) -> str:
        source_scene = metadata.get("source_scene", {})
        if isinstance(source_scene, dict):
            parts = [
                str(source_scene.get(field, "")).strip()
                for field in self.query_fields
                if str(source_scene.get(field, "")).strip()
            ]
            if parts:
                return self._clean_query(" ".join(parts))

        return self._clean_query(prompt)

    @staticmethod
    def _clean_query(prompt: str) -> str:
        words = prompt.replace(",", " ").replace(".", " ").split()
        cleaned = " ".join(words[:10]).strip()
        if len(cleaned) > 95:
            cleaned = cleaned[:95].rsplit(" ", 1)[0].strip()
        return cleaned or "cinematic background"

    @staticmethod
    def _metadata_path_for(media_path: Path) -> Path:
        return media_path.with_name(f"{media_path.stem}_metadata.json")

    @staticmethod
    def _safe_hit(hit: dict[str, Any]) -> dict[str, Any]:
        allowed = [
            "id",
            "pageURL",
            "type",
            "tags",
            "duration",
            "views",
            "downloads",
            "likes",
            "user",
            "user_id",
        ]
        return {key: hit.get(key) for key in allowed if key in hit}
