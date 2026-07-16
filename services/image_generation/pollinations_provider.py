"""Pollinations image provider for Vice Studio."""

from __future__ import annotations

import json
import random
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

        response = requests.get(url, params=params, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(
                f"Pollinations request failed: {response.status_code} {response.text[:500]}"
            )

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

    @staticmethod
    def _metadata_path_for(image_path: Path) -> Path:
        return image_path.with_name(f"{image_path.stem}_metadata.json")
