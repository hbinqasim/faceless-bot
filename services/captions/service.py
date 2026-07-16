"""Add animated line-by-line captions to the final video."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from moviepy import CompositeVideoClip, TextClip, VideoFileClip, vfx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
DEFAULT_MAX_CAPTION_WIDTH = 940
DEFAULT_CAPTION_Y_RATIO = 0.78
MIN_SEGMENT_WORDS = 3
MAX_SEGMENT_WORDS = 5
MAX_CAPTION_LINES = 2
TEXT_COLOR = "white"
STROKE_COLOR = "black"
SHADOW_COLOR = "black"


def load_config() -> dict[str, Any]:
    """Load caption service configuration."""
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_script_lines(config: dict[str, Any] | None = None) -> list[str]:
    """Load non-empty script lines."""
    active_config = config or load_config()
    script_path = _resolve_project_path(active_config["script_path"])
    return [
        line.strip()
        for line in script_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def make_caption_clips(
    segments: list[str],
    duration: float,
    config: dict[str, Any],
    video_size: tuple[int, int] = (1080, 1920),
) -> list[Any]:
    """Create timed caption clips distributed by segment character length."""
    if not segments:
        return []

    video_width, video_height = video_size
    caption_center_y = int(
        config.get("caption_y", video_height * config.get("caption_y_ratio", DEFAULT_CAPTION_Y_RATIO))
    )
    font_size = int(config.get("font_size", 86))
    stroke_width = int(config.get("stroke_width", 8))
    shadow_offset = int(config.get("shadow_offset", 5))
    shadow_opacity = float(config.get("shadow_opacity", 0.42))
    safe_margin = int(config.get("safe_margin", 96))
    max_caption_width = int(config.get("max_caption_width", DEFAULT_MAX_CAPTION_WIDTH))
    font = _find_bold_font(config)
    weights = [max(len(segment), 1) for segment in segments]
    total_weight = sum(weights)
    caption_clips: list[Any] = []
    start_time = 0.0

    for index, segment in enumerate(segments):
        if index == len(segments) - 1:
            segment_duration = max(duration - start_time, 0.01)
        else:
            segment_duration = duration * (weights[index] / total_weight)

        caption_text = format_caption_segment(segment)
        shadow = TextClip(
            text=caption_text,
            font=font,
            font_size=font_size,
            color=SHADOW_COLOR,
            stroke_color=SHADOW_COLOR,
            stroke_width=stroke_width,
            method="caption",
            size=(max_caption_width, None),
            text_align="center",
            horizontal_align="center",
            vertical_align="center",
        )
        shadow = shadow.with_opacity(shadow_opacity)

        caption = TextClip(
            text=caption_text,
            font=font,
            font_size=font_size,
            color=TEXT_COLOR,
            stroke_color=STROKE_COLOR,
            stroke_width=stroke_width,
            method="caption",
            size=(max_caption_width, None),
            text_align="center",
            horizontal_align="center",
            vertical_align="center",
        )

        caption_x = (video_width - caption.w) / 2
        caption_y = _clamp(
            caption_center_y - (caption.h / 2),
            safe_margin,
            video_height - safe_margin - caption.h,
        )
        shadow_x = _clamp(caption_x + shadow_offset, safe_margin, video_width - safe_margin - shadow.w)
        shadow_y = _clamp(caption_y + shadow_offset, safe_margin, video_height - safe_margin - shadow.h)

        shadow = shadow.with_start(start_time).with_duration(segment_duration)
        shadow = shadow.with_position((shadow_x, shadow_y))
        shadow = _apply_caption_fades(shadow, segment_duration)

        caption = caption.with_start(start_time).with_duration(segment_duration)
        caption = caption.with_position((caption_x, caption_y))
        caption = _apply_caption_fades(caption, segment_duration)
        caption_clips.append(shadow)
        caption_clips.append(caption)
        start_time += segment_duration

    return caption_clips


def add_captions(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render captioned video and timestamped copy."""
    active_config = config or load_config()
    input_video = _resolve_project_path(active_config["input_video"])
    output_video = _resolve_project_path(active_config["output_video"])
    output_video.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    timestamped_output = (
        output_video.parent / f"{timestamp}_{active_config.get('channel', 'video')}_captioned.mp4"
    )

    lines = load_script_lines(active_config)
    caption_segments = split_caption_segments(lines)
    video = VideoFileClip(str(input_video))
    caption_clips: list[Any] = []
    composed = None

    try:
        duration = float(video.duration or 0)
        caption_clips = make_caption_clips(
            caption_segments,
            duration,
            active_config,
            video_size=(video.w, video.h),
        )
        composed = CompositeVideoClip([video, *caption_clips], size=(video.w, video.h))
        composed = composed.with_duration(duration).with_audio(video.audio)
        composed.write_videofile(
            str(output_video),
            fps=video.fps or 30,
            codec="libx264",
            audio=bool(video.audio),
            audio_codec="aac",
            preset="medium",
            ffmpeg_params=["-movflags", "+faststart"],
            logger=None,
            pixel_format="yuv420p",
        )
        shutil.copy2(output_video, timestamped_output)
    finally:
        if composed is not None:
            composed.close()
        for caption in caption_clips:
            caption.close()
        video.close()

    return {
        "input_video": str(input_video),
        "output_video": str(output_video),
        "timestamped_output_video": str(timestamped_output),
        "script_path": str(_resolve_project_path(active_config["script_path"])),
        "script_line_count": len(lines),
        "caption_count": len(caption_segments),
        "caption_segments": caption_segments,
        "video_duration": duration,
    }


def save_manifest(items: dict[str, Any]) -> Path:
    """Save caption generation manifest."""
    config = load_config()
    output_video = _resolve_project_path(config["output_video"])
    manifest_path = output_video.parent / "captions_manifest.json"

    manifest = {
        "service_name": config.get("service_name"),
        "channel": config.get("channel"),
        "font_size": config.get("font_size"),
        "caption_y": config.get("caption_y"),
        "max_caption_width": config.get("max_caption_width"),
        "stroke_width": config.get("stroke_width"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **items,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def run() -> dict[str, Any]:
    """Run the caption service."""
    config = load_config()
    if not config.get("enabled", True):
        raise RuntimeError("Caption service is disabled in config.json.")

    result = add_captions(config)
    manifest_path = save_manifest(result)

    print(f"Input video: {result['input_video']}")
    print(f"Script path: {result['script_path']}")
    print(f"Caption count: {result['caption_count']}")
    print(f"Video duration: {result['video_duration']:.2f} seconds")
    print(f"Output video: {result['output_video']}")
    print(f"Timestamped output: {result['timestamped_output_video']}")
    print(f"Manifest path: {manifest_path}")

    return {
        **result,
        "manifest_path": str(manifest_path),
    }


def split_caption_segments(lines: list[str]) -> list[str]:
    """Split script lines into short 3-5 word caption segments."""
    chunks: list[list[str]] = []
    for line in lines:
        words = line.split()
        while words:
            chunk_size = _choose_caption_chunk_size(len(words))
            chunks.append(words[:chunk_size])
            words = words[chunk_size:]

    chunks = _merge_short_chunks(chunks)
    return [" ".join(chunk) for chunk in chunks if chunk]


def format_caption_segment(segment: str) -> str:
    """Format a segment as uppercase text with at most two lines."""
    words = segment.upper().split()
    if len(words) <= 3:
        return " ".join(words)

    split_at = min(3, max(2, (len(words) + 1) // MAX_CAPTION_LINES))
    return f"{' '.join(words[:split_at])}\n{' '.join(words[split_at:])}"


def _choose_caption_chunk_size(remaining_words: int) -> int:
    if remaining_words <= MAX_SEGMENT_WORDS:
        return remaining_words
    if remaining_words == 6:
        return 3
    if remaining_words == 7:
        return 4
    if remaining_words == 8:
        return 4
    if remaining_words in {9, 10}:
        return 5
    return 4


def _merge_short_chunks(chunks: list[list[str]]) -> list[list[str]]:
    merged = [chunk[:] for chunk in chunks if chunk]
    index = 0
    while index < len(merged):
        if len(merged[index]) >= MIN_SEGMENT_WORDS:
            index += 1
            continue

        if index > 0 and len(merged[index - 1]) + len(merged[index]) <= MAX_SEGMENT_WORDS:
            merged[index - 1].extend(merged[index])
            merged.pop(index)
            continue

        if index + 1 < len(merged) and len(merged[index]) + len(merged[index + 1]) <= MAX_SEGMENT_WORDS:
            merged[index].extend(merged[index + 1])
            merged.pop(index + 1)
            continue

        index += 1

    return merged


def _apply_caption_fades(caption: TextClip, duration: float) -> TextClip:
    fade_duration = min(0.2, max(duration / 4, 0.05))
    return caption.with_effects(
        [
            vfx.FadeIn(fade_duration),
            vfx.FadeOut(fade_duration),
        ]
    )


def _find_bold_font(config: dict[str, Any]) -> str | None:
    configured_font = config.get("font")
    if configured_font:
        font_path = _resolve_project_path(configured_font)
        if font_path.exists():
            return str(font_path)
        return str(configured_font)

    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    return None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    if maximum < minimum:
        return minimum
    return max(minimum, min(value, maximum))


def _resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    return PROJECT_ROOT / candidate


if __name__ == "__main__":
    run()
