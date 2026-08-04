"""Add exact word-timed animated captions to the final video."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel
from PIL import Image, ImageDraw, ImageFont
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip
from vice_studio.config_loader import load_component_config


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "services/graphics/config.json"


def load_config() -> dict[str, Any]:
    return load_component_config(CONFIG_PATH)


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def find_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def transcribe_words(config: dict[str, Any]) -> list[dict[str, Any]]:
    audio_path = resolve_path(config["audio_path"])
    model_name = str(config.get("whisper_model", "base"))

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        vad_filter=True,
    )

    words: list[dict[str, Any]] = []

    for segment in segments:
        for word in segment.words or []:
            clean = clean_word(word.word)
            if not clean:
                continue

            words.append(
                {
                    "word": clean.upper(),
                    "start": float(word.start),
                    "end": float(word.end),
                }
            )

    return words


def clean_word(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    value = value.strip()
    value = value.strip(".,:;\"“”")
    return value


def make_caption_groups(words: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    max_words = int(config.get("max_words_per_caption", 4))
    max_gap = float(config.get("max_caption_gap_seconds", 0.55))

    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for item in words:
        if not current:
            current.append(item)
            continue

        gap = float(item["start"]) - float(current[-1]["end"])
        if len(current) >= max_words or gap > max_gap:
            groups.append(current)
            current = [item]
        else:
            current.append(item)

    if current:
        groups.append(current)

    output: list[dict[str, Any]] = []
    for group in groups:
        output.append(
            {
                "words": group,
                "start": float(group[0]["start"]),
                "end": float(group[-1]["end"]),
            }
        )

    return output


def render_caption_overlay(
    group: dict[str, Any],
    active_index: int,
    width: int,
    height: int,
    config: dict[str, Any],
    output_dir: Path,
    image_index: int,
) -> Path:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    words = [item["word"] for item in group["words"]]

    safe_margin = int(config.get("safe_margin", 64))
    max_box_width = int(config.get("max_box_width", 960))
    max_text_width = min(max_box_width - 90, width - safe_margin * 2 - 90)
    y_ratio = float(config.get("y_position_ratio", 0.66))
    base_font_size = int(config.get("font_size", 104))
    stroke_width = int(config.get("stroke_width", 10))
    shadow_offset = int(config.get("shadow_offset", 7))
    box_opacity = int(config.get("box_opacity", 135))

    text_color = tuple(config.get("text_color", [255, 255, 255]))
    highlight_color = tuple(config.get("highlight_color", [255, 204, 0]))
    stroke_color = tuple(config.get("stroke_color", [0, 0, 0]))

    font_size, font, lines = fit_caption_lines(words, base_font_size, stroke_width, max_text_width)
    metrics = measure_lines(draw, lines, font, stroke_width)

    line_gap = max(12, font_size // 6)
    total_height = sum(item["height"] for item in metrics) + line_gap * (len(lines) - 1)
    center_y = int(height * y_ratio)
    start_y = clamp(center_y - total_height // 2, safe_margin, height - safe_margin - total_height)

    max_line_width = max(item["width"] for item in metrics)
    box_margin_x = 45
    box_margin_y = 32
    box_width = min(max_line_width + box_margin_x * 2, max_box_width, width - safe_margin * 2)

    box_x1 = int((width - box_width) / 2)
    box_y1 = int(start_y - box_margin_y)
    box_x2 = int(box_x1 + box_width)
    box_y2 = int(start_y + total_height + box_margin_y)

    draw.rounded_rectangle(
        [box_x1, box_y1, box_x2, box_y2],
        radius=34,
        fill=(0, 0, 0, box_opacity),
    )

    word_counter = 0
    current_y = start_y

    for line, metric in zip(lines, metrics):
        x = int((width - metric["width"]) / 2)

        for word in line:
            is_active = word_counter == active_index
            fill = highlight_color if is_active else text_color

            text = word + " "
            draw.text(
                (x + shadow_offset, current_y + shadow_offset),
                text,
                font=font,
                fill=(0, 0, 0, 190),
                stroke_width=stroke_width,
                stroke_fill=(0, 0, 0),
            )
            draw.text(
                (x, current_y),
                text,
                font=font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
            )

            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
            x += bbox[2] - bbox[0]
            word_counter += 1

        current_y += metric["height"] + line_gap

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"caption_{image_index:04d}.png"
    image.save(output_path)
    return output_path


def create_caption_clips(groups: list[dict[str, Any]], video: VideoFileClip, config: dict[str, Any]) -> list[Any]:
    output_video = resolve_path(config["output_video"])
    overlay_dir = output_video.parent / "graphics_overlays"
    shutil.rmtree(overlay_dir, ignore_errors=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    clips: list[Any] = []
    image_index = 1

    for group in groups:
        words = group["words"]

        for active_index, item in enumerate(words):
            start = float(item["start"])
            end = float(item["end"])
            duration = max(0.05, end - start)

            overlay_path = render_caption_overlay(
                group,
                active_index if config.get("highlight_current_word", True) else -1,
                video.w,
                video.h,
                config,
                overlay_dir,
                image_index,
            )
            image_index += 1

            clip = (
                ImageClip(str(overlay_path))
                .with_start(start)
                .with_duration(duration)
                .with_position(("center", "center"))
            )
            clips.append(clip)

    return clips


def fit_caption_lines(words: list[str], base_font_size: int, stroke_width: int, max_text_width: int):
    font_size = base_font_size

    while font_size >= 52:
        font = find_font(font_size)
        lines = split_lines(words)
        test_image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        draw = ImageDraw.Draw(test_image)
        widths = [text_width(draw, line, font, stroke_width) for line in lines]

        if widths and max(widths) <= max_text_width:
            return font_size, font, lines

        font_size -= 4

    font = find_font(font_size)
    return font_size, font, split_lines(words)


def split_lines(words: list[str]) -> list[list[str]]:
    if len(words) <= 3:
        return [words]

    midpoint = (len(words) + 1) // 2
    return [words[:midpoint], words[midpoint:]]


def measure_lines(draw: ImageDraw.ImageDraw, lines: list[list[str]], font: ImageFont.ImageFont, stroke_width: int):
    metrics = []
    for line in lines:
        text = " ".join(line)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        metrics.append({"width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]})
    return metrics


def text_width(draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.ImageFont, stroke_width: int) -> int:
    total = 0
    for word in words:
        text = word + " "
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        total += bbox[2] - bbox[0]
    return total


def save_manifest(config: dict[str, Any], result: dict[str, Any]) -> Path:
    output_video = resolve_path(config["output_video"])
    manifest_path = output_video.parent / "graphics_manifest.json"

    manifest = {
        "service_name": config.get("service_name", "graphics"),
        "channel": config.get("channel"),
        "caption_mode": config.get("caption_mode", "word_timed"),
        "input_video": str(resolve_path(config["input_video"])),
        "output_video": str(output_video),
        "audio_path": str(resolve_path(config["audio_path"])),
        "word_count": result["word_count"],
        "caption_group_count": result["caption_group_count"],
        "caption_clip_count": result["caption_clip_count"],
        "video_duration": result["video_duration"],
        "timestamped_output": result["timestamped_output"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run() -> dict[str, Any]:
    config = load_config()

    if not config.get("enabled", True):
        raise RuntimeError("Graphics service is disabled in config.json.")

    input_video = resolve_path(config["input_video"])
    output_video = resolve_path(config["output_video"])
    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("Transcribing voice for exact word timings...")
    words = transcribe_words(config)
    groups = make_caption_groups(words, config)

    video = VideoFileClip(str(input_video))
    overlays = []
    final = None

    try:
        overlays = create_caption_clips(groups, video, config)
        final = CompositeVideoClip([video, *overlays], size=(video.w, video.h)).with_audio(video.audio)
        final.write_videofile(
            str(output_video),
            fps=video.fps or 30,
            codec="libx264",
            audio_codec="aac",
            logger=None,
            pixel_format="yuv420p",
        )

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        channel = str(config.get("channel", "video"))
        timestamped = output_video.parent / f"{timestamp}_{channel}_graphics.mp4"
        shutil.copy2(output_video, timestamped)

        result = {
            "word_count": len(words),
            "caption_group_count": len(groups),
            "caption_clip_count": len(overlays),
            "video_duration": float(video.duration or 0),
            "output_video": str(output_video),
            "timestamped_output": str(timestamped),
        }

        manifest_path = save_manifest(config, result)

        print("Graphics video created:")
        print(output_video)
        print(timestamped)
        print(f"Words: {len(words)}")
        print(f"Caption groups: {len(groups)}")
        print(f"Caption clips: {len(overlays)}")
        print(f"Manifest: {manifest_path}")

        return result

    finally:
        if final is not None:
            final.close()
        for overlay in overlays:
            overlay.close()
        video.close()


def clamp(value: float, minimum: float, maximum: float) -> float:
    if maximum < minimum:
        return minimum
    return max(minimum, min(value, maximum))


if __name__ == "__main__":
    run()
