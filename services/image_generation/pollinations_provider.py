"""Pollinations image provider for Vice Studio."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

try:
    from .provider_base import ProviderBase
except ImportError:
    from provider_base import ProviderBase


class PollinationsProvider(ProviderBase):
    """Generate images through Pollinations image API."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(
            config.get("pollinations_base_url", "https://image.pollinations.ai/prompt")
        ).rstrip("/")
        self.model = str(config.get("pollinations_model", "flux"))
        self.width = int(config.get("image_width", 768))
        self.height = int(config.get("image_height", 1344))
        self.timeout = int(config.get("pollinations_timeout_seconds", 180))
        self.max_attempts = max(1, int(config.get("pollinations_max_attempts", 4)))
        self.retry_backoff = max(
            0.0, float(config.get("pollinations_retry_backoff_seconds", 2.0))
        )
        self.enhance = bool(config.get("pollinations_enhance", False))
        self.nologo = bool(config.get("pollinations_nologo", True))

    def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        image_path = Path(output_path).with_suffix(".jpg")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = self._metadata_path_for(image_path)

        seed = random.randint(1, 2_147_483_647)
        url = f"{self.base_url}/{quote(prompt)}"
        params = {
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "seed": seed,
            "enhance": str(self.enhance).lower(),
            "nologo": str(self.nologo).lower(),
        }

        response, request_attempts = self._request_with_retries(url, params)

        image_path.write_bytes(response.content)

        payload = dict(metadata or {})
        payload.update(
            {
                "provider": "pollinations",
                "status": "generated",
                "model": self.model,
                "seed": seed,
                "width": self.width,
                "height": self.height,
                "request_attempts": request_attempts,
                "image_path": str(image_path),
                "metadata_path": str(metadata_path),
                "request_url": response.url,
            }
        )

        metadata_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return {
            "image_path": str(image_path),
            "metadata_path": str(metadata_path),
            "status": "generated",
        }

    def _request_with_retries(
        self, url: str, params: dict[str, Any]
    ) -> tuple[requests.Response, int]:
        """Retry temporary network and upstream failures with exponential backoff."""
        retryable_statuses = {408, 425, 429, 500, 502, 503, 504}

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as error:
                if attempt == self.max_attempts:
                    raise RuntimeError(
                        "Pollinations request failed after "
                        f"{attempt} attempts: {type(error).__name__}: {error}"
                    ) from error
                self._wait_before_retry(attempt, None)
                continue

            if response.ok:
                return response, attempt

            error_detail = response.text[:500]
            if response.status_code not in retryable_statuses:
                raise RuntimeError(
                    f"Pollinations request failed: {response.status_code} {error_detail}"
                )
            if attempt == self.max_attempts:
                raise RuntimeError(
                    "Pollinations request failed after "
                    f"{attempt} attempts: {response.status_code} {error_detail}"
                )

            self._wait_before_retry(attempt, response)

        raise AssertionError("Pollinations retry loop exited unexpectedly")

    def _wait_before_retry(
        self, attempt: int, response: requests.Response | None
    ) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        try:
            delay = float(retry_after) if retry_after is not None else None
        except ValueError:
            delay = None

        if delay is None:
            delay = self.retry_backoff * (2 ** (attempt - 1))
        if delay > 0:
            time.sleep(delay)

    @staticmethod
    def _metadata_path_for(image_path: Path) -> Path:
        return image_path.with_name(f"{image_path.stem}_metadata.json")
