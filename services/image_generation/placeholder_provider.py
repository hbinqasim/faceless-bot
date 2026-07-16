"""Placeholder image provider for downstream pipeline testing."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    from .provider_base import ProviderBase
except ImportError:  # pragma: no cover - supports direct script execution.
    from provider_base import ProviderBase


class PlaceholderProvider(ProviderBase):
    """Create cinematic test-frame JPGs from prompts."""

    def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(metadata or {})
        width = int(payload.get("image_width") or 1080)
        height = int(payload.get("image_height") or 1920)
        scene_number = int(payload.get("scene_number") or 0)

        image_path = Path(output_path).with_suffix(".jpg")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = self._metadata_path_for(image_path)

        image = self._create_frame(width, height, scene_number, prompt)
        image.save(image_path, format="JPEG", quality=92, optimize=True)

        payload.update(
            {
                "provider": "placeholder",
                "image_path": str(image_path),
                "metadata_path": str(metadata_path),
                "status": "generated",
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

    def _create_frame(
        self,
        width: int,
        height: int,
        scene_number: int,
        prompt: str,
    ) -> Image.Image:
        image = self._gradient_background(width, height)
        draw = ImageDraw.Draw(image)

        title_font = self._load_font(78, bold=True)
        prompt_font = self._load_font(42)
        footer_font = self._load_font(46, bold=True)

        margin = 96
        scene_title = f"SCENE {scene_number:02d}" if scene_number else "SCENE"
        self._draw_centered_text(
            draw,
            scene_title,
            title_font,
            y=140,
            width=width,
            fill=(246, 226, 190),
        )

        preview = self._short_preview(prompt)
        wrapped_preview = "\n".join(textwrap.wrap(preview, width=34))
        prompt_box_width = width - (margin * 2)
        prompt_bbox = draw.multiline_textbbox(
            (0, 0),
            wrapped_preview,
            font=prompt_font,
            spacing=14,
        )
        prompt_height = prompt_bbox[3] - prompt_bbox[1]
        prompt_y = int((height - prompt_height) / 2)

        draw.rounded_rectangle(
            [
                margin - 30,
                prompt_y - 42,
                width - margin + 30,
                prompt_y + prompt_height + 42,
            ],
            radius=34,
            fill=(5, 9, 14),
            outline=(218, 124, 82),
            width=3,
        )
        self._draw_multiline_centered_text(
            draw,
            wrapped_preview,
            prompt_font,
            y=prompt_y,
            width=width,
            fill=(232, 239, 238),
            spacing=14,
        )

        draw.line(
            [(margin, height - 265), (width - margin, height - 265)],
            fill=(82, 168, 174),
            width=3,
        )
        self._draw_centered_text(
            draw,
            "VICE STUDIO TEST FRAME",
            footer_font,
            y=height - 220,
            width=width,
            fill=(239, 184, 104),
        )

        return image

    @staticmethod
    def _gradient_background(width: int, height: int) -> Image.Image:
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        top = (4, 8, 16)
        mid = (7, 39, 48)
        bottom = (42, 18, 32)

        for y in range(height):
            ratio = y / max(height - 1, 1)
            if ratio < 0.58:
                local_ratio = ratio / 0.58
                color = _interpolate_color(top, mid, local_ratio)
            else:
                local_ratio = (ratio - 0.58) / 0.42
                color = _interpolate_color(mid, bottom, local_ratio)
            draw.line([(0, y), (width, y)], fill=color)

        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse(
            [-280, int(height * 0.12), int(width * 0.7), int(height * 0.62)],
            fill=(0, 126, 137, 58),
        )
        glow_draw.ellipse(
            [int(width * 0.35), int(height * 0.52), width + 320, height + 260],
            fill=(213, 82, 43, 48),
        )
        glow_draw.rectangle(
            [0, 0, width, height],
            outline=(0, 0, 0, 140),
            width=32,
        )

        return Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf" if bold else "",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return ImageFont.truetype(candidate, size=size)

        return ImageFont.load_default()

    @staticmethod
    def _short_preview(prompt: str) -> str:
        compact_prompt = " ".join(prompt.split())
        if len(compact_prompt) <= 420:
            return compact_prompt
        return compact_prompt[:417].rstrip() + "..."

    @staticmethod
    def _draw_centered_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        y: int,
        width: int,
        fill: tuple[int, int, int],
    ) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) / 2, y), text, font=font, fill=fill)

    @staticmethod
    def _draw_multiline_centered_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        y: int,
        width: int,
        fill: tuple[int, int, int],
        spacing: int,
    ) -> None:
        for line in text.splitlines():
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            draw.text(((width - line_width) / 2, y), line, font=font, fill=fill)
            y += (bbox[3] - bbox[1]) + spacing

    @staticmethod
    def _metadata_path_for(image_path: Path) -> Path:
        return image_path.with_name(f"{image_path.stem}_metadata.json")


def _interpolate_color(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    return tuple(int(start[index] + (end[index] - start[index]) * ratio) for index in range(3))
