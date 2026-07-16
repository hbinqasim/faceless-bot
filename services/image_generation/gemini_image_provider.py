"""Gemini image provider for Vice Studio."""

from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image

try:
    from .provider_base import ProviderBase
except ImportError:
    from provider_base import ProviderBase


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class GeminiImageProvider(ProviderBase):
    """Generate images through Google Gemini image models."""

    def __init__(self, config: dict[str, Any]) -> None:
        load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
        self.model = str(config.get("gemini_image_model", "gemini-2.5-flash-image"))
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is missing in .env")

    def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from google import genai

        image_path = Path(output_path).with_suffix(".png")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = self._metadata_path_for(image_path)

        client = genai.Client(api_key=self.api_key)

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        image_saved = False
        text_parts: list[str] = []

        for candidate in response.candidates or []:
            content = candidate.content
            if not content:
                continue

            for part in content.parts or []:
                if getattr(part, "text", None):
                    text_parts.append(str(part.text))

                inline_data = getattr(part, "inline_data", None)
                if inline_data and getattr(inline_data, "data", None):
                    image = Image.open(BytesIO(inline_data.data))
                    image.save(image_path)
                    image_saved = True
                    break

            if image_saved:
                break

        if not image_saved:
            raise RuntimeError(
                "Gemini returned no image data. "
                f"Text response: {' '.join(text_parts).strip()}"
            )

        payload = dict(metadata or {})
        payload.update(
            {
                "provider": "gemini_image",
                "status": "generated",
                "model": self.model,
                "image_path": str(image_path),
                "metadata_path": str(metadata_path),
                "text_response": " ".join(text_parts).strip(),
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
