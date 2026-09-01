"""Pixabay media provider for Vice Studio image generation service."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any

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
        self.max_request_attempts = max(
            1, int(config.get("pixabay_max_request_attempts", 4))
        )
        self.retry_backoff_seconds = max(
            0.0, float(config.get("pixabay_retry_backoff_seconds", 2.0))
        )
        self.order = str(config.get("pixabay_order", "popular"))
        self.random_pages = max(1, int(config.get("pixabay_random_pages", 1)))
        self.required_tag_terms = {
            str(item).strip().lower()
            for item in config.get("pixabay_required_tag_terms", [])
            if str(item).strip()
        }
        self.video_qualities = [
            str(item)
            for item in config.get(
                "pixabay_video_qualities", ["large", "medium", "small", "tiny"]
            )
        ]
        self.fallback_queries = [
            str(item).strip()
            for item in config.get("pixabay_fallback_queries", [])
            if str(item).strip()
        ]
        history_value = str(config.get("pixabay_history_path", "")).strip()
        self.history_path = self._resolve_project_path(history_value) if history_value else None
        self.history_limit = max(1, int(config.get("pixabay_history_limit", 500)))
        self.used_ids = self._load_used_ids()
        self.random = random.SystemRandom()
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
            hit, search_query = self._search_images(search_query)
            media_url = hit["largeImageURL"]
            media_path = Path(output_path).with_suffix(".jpg")
        else:
            hit, search_query = self._search_videos(search_query)
            media_url = self._best_video_url(hit, self.video_qualities)
            media_path = Path(output_path).with_suffix(".mp4")

        media_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = self._metadata_path_for(media_path)

        self._download(media_url, media_path)
        self._remember_hit(hit)

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

    def _search_videos(self, query: str) -> tuple[dict[str, Any], str]:
        url = "https://pixabay.com/api/videos/"
        return self._search(url, query, {"orientation": self.orientation})

    def _search_images(self, query: str) -> tuple[dict[str, Any], str]:
        url = "https://pixabay.com/api/"
        return self._search(
            url,
            query,
            {"orientation": self.orientation, "image_type": "photo"},
        )

    def _search(
        self, url: str, query: str, extra_params: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        queries = list(dict.fromkeys([query, *self.fallback_queries]))
        for active_query in queries:
            pages = list(range(1, self.random_pages + 1))
            self.random.shuffle(pages)
            for page in pages:
                params = {
                    "key": self.api_key,
                    "q": active_query,
                    "per_page": self.per_page,
                    "page": page,
                    "order": self.order,
                    "safesearch": "true",
                    **extra_params,
                }
                data = self._get_json(url, params)
                hits = [item for item in data.get("hits", []) if isinstance(item, dict)]
                hits = [hit for hit in hits if self._has_required_tags(hit)]
                if not hits:
                    continue

                unused_hits = [hit for hit in hits if str(hit.get("id")) not in self.used_ids]
                return self.random.choice(unused_hits or hits), active_query

        raise RuntimeError(f"No Pixabay {self.media_type} results found for: {query}")

    def _has_required_tags(self, hit: dict[str, Any]) -> bool:
        if not self.required_tag_terms:
            return True
        tags = str(hit.get("tags", "")).lower()
        return any(term in tags for term in self.required_tag_terms)

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        for attempt in range(1, self.max_request_attempts + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                if response.ok:
                    return response.json()
                errors.append(f"HTTP {response.status_code}: {response.text[:300]}")
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                retry_after = self._retry_after_seconds(response)
            except (requests.RequestException, ValueError) as error:
                errors.append(self._redact_api_key(str(error)))
                retry_after = None

            if attempt < self.max_request_attempts:
                self._wait_before_retry(attempt, retry_after)

        raise RuntimeError(
            f"Pixabay request failed after {len(errors)} attempt(s): {errors[-1]}"
        )

    def _redact_api_key(self, message: str) -> str:
        """Keep credentials out of request errors and pipeline logs."""
        return message.replace(self.api_key, "[REDACTED]")

    def _download(self, url: str, output_path: Path) -> None:
        errors: list[str] = []
        for attempt in range(1, self.max_request_attempts + 1):
            try:
                response = requests.get(url, timeout=self.timeout)
                if response.ok:
                    output_path.write_bytes(response.content)
                    return
                errors.append(f"HTTP {response.status_code}")
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                retry_after = self._retry_after_seconds(response)
            except requests.RequestException as error:
                errors.append(str(error))
                retry_after = None

            if attempt < self.max_request_attempts:
                self._wait_before_retry(attempt, retry_after)

        raise RuntimeError(
            f"Pixabay download failed after {len(errors)} attempt(s): {errors[-1]}"
        )

    def _wait_before_retry(self, attempt: int, retry_after: float | None) -> None:
        delay = (
            retry_after
            if retry_after is not None
            else self.retry_backoff_seconds * (2 ** (attempt - 1))
        )
        if delay > 0:
            time.sleep(delay)

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float | None:
        value = str(response.headers.get("Retry-After", "")).strip()
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    @staticmethod
    def _best_video_url(
        hit: dict[str, Any], qualities: list[str] | None = None
    ) -> str:
        videos = hit.get("videos", {})
        for quality in qualities or ["large", "medium", "small", "tiny"]:
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

    def _load_used_ids(self) -> set[str]:
        if self.history_path is None or not self.history_path.exists():
            return set()
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return set()
        items = data.get("used_hit_ids", []) if isinstance(data, dict) else []
        return {str(item) for item in items}

    def _remember_hit(self, hit: dict[str, Any]) -> None:
        hit_id = str(hit.get("id", "")).strip()
        if not hit_id:
            return
        self.used_ids.add(hit_id)
        if self.history_path is None:
            return

        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        recent_ids = list(self.used_ids)[-self.history_limit :]
        self.history_path.write_text(
            json.dumps({"used_hit_ids": recent_ids}, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _resolve_project_path(path_value: str) -> Path:
        path = Path(path_value)
        return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path

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
