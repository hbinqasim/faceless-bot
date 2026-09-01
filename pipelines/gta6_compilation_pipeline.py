"""Build and optionally upload a compilation of every completed GTA 6 video."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ROOT = PROJECT_ROOT / "channels" / "gta6_compilation"
OUTPUT_VIDEO = CHANNEL_ROOT / "videos" / "gta6_complete_compilation.mp4"
METADATA_PATH = CHANNEL_ROOT / "metadata" / "latest_metadata.json"
THUMBNAIL_PATH = CHANNEL_ROOT / "thumbnails" / "latest_thumbnail.jpg"
MANIFEST_PATH = CHANNEL_ROOT / "videos" / "compilation_manifest.json"
UPLOAD_CONFIG = PROJECT_ROOT / "configs" / "gta6_compilation" / "upload.json"
GRAPHICS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_.+_graphics\.mp4$")


def discover_completed_videos(project_root: Path = PROJECT_ROOT) -> list[Path]:
    """Return timestamped captioned masters without latest aliases or raw duplicates."""
    folders = [
        project_root / "channels" / "gta6" / "videos" / "final",
        project_root / "channels" / "gta6_longform" / "videos" / "final",
    ]
    videos: list[Path] = []
    for folder in folders:
        if not folder.exists():
            continue
        videos.extend(
            path
            for path in folder.iterdir()
            if path.is_file() and GRAPHICS_PATTERN.match(path.name)
        )
    return sorted(videos, key=lambda path: (path.name[:19], str(path)))


def probe_media(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    return {
        "duration": float(data.get("format", {}).get("duration", 0) or 0),
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
    }


def normalize_video(source: Path, output: Path, has_audio: bool) -> None:
    """Normalize mixed portrait/landscape masters without changing playback speed."""
    filter_graph = (
        "[0:v]split=2[background][foreground];"
        "[background]scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,gblur=sigma=24[blurred];"
        "[foreground]scale=1920:1080:force_original_aspect_ratio=decrease[front];"
        "[blurred][front]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30[v]"
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-stats",
        "-y",
        "-i",
        str(source),
    ]
    if not has_audio:
        command.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
    command.extend([
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
    ])
    if has_audio:
        command.extend(["-map", "0:a:0", "-af", "loudnorm=I=-16:LRA=11:TP=-1.5"])
    else:
        command.extend(["-map", "1:a:0", "-shortest"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    subprocess.run(command, check=True)


def concatenate_videos(normalized: list[Path], output: Path, workdir: Path) -> None:
    concat_file = workdir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in normalized),
        encoding="utf-8",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-stats",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )


def timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def build_metadata(sources: list[dict[str, Any]]) -> dict[str, Any]:
    chapters: list[str] = []
    elapsed = 0.0
    short_number = 0
    long_number = 0
    for item in sources:
        source = Path(str(item["path"]))
        is_long = "gta6_longform" in source.parts
        if is_long:
            long_number += 1
            label = f"Long-form analysis {long_number}"
        else:
            short_number += 1
            label = f"GTA 6 update {short_number}"
        chapters.append(f"{timestamp(elapsed)} {label} — {source.name[:19]}")
        elapsed += float(item["duration"])

    count = len(sources)
    title = f"GTA 6 Complete Video Compilation | {count} Updates & Deep Dives"
    description = "\n".join(
        [
            f"A complete compilation of {count} GTA 6 news videos and long-form analyses produced by the channel.",
            "",
            "Every completed captioned master is included once and plays at its original speed.",
            "Portrait videos are presented on a blurred 16:9 background for the compilation.",
            "",
            "Chapters:",
            *chapters,
            "",
            "#gta6 #gaming #rockstar #grandtheftauto",
        ]
    )
    return {
        "title": title[:100],
        "description": description[:5000],
        "tags": [
            "GTA 6",
            "Grand Theft Auto VI",
            "Rockstar Games",
            "GTA 6 News",
            "GTA 6 Compilation",
            "Gaming News",
        ],
        "hashtags": ["#gta6", "#gaming", "#rockstar", "#grandtheftauto"],
        "category": "Gaming",
        "language": "en",
        "video_format": "long-form",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_video_count": count,
    }


def extract_frame(video: Path, output: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "00:00:01",
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    scale = max(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (int(image.width * scale), int(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_width) // 2
    top = (resized.height - target_height) // 2
    return resized.crop((left, top, left + target_width, top + target_height))


def create_thumbnail(videos: list[Path], output: Path, workdir: Path) -> None:
    sample_indices = sorted({round(index * (len(videos) - 1) / 3) for index in range(4)})
    samples = [videos[index] for index in sample_indices]
    frames: list[Image.Image] = []
    for index, video in enumerate(samples):
        frame_path = workdir / f"thumbnail_{index}.jpg"
        extract_frame(video, frame_path)
        frames.append(cover(Image.open(frame_path).convert("RGB"), (640, 360)))

    canvas = Image.new("RGB", (1280, 720), (5, 7, 12))
    positions = [(0, 0), (640, 0), (0, 360), (640, 360)]
    for frame, position in zip(frames, positions):
        canvas.paste(frame, position)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, 225, 1280, 495), fill=(0, 0, 0, 175))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font_path = next((path for path in font_paths if Path(path).exists()), None)
    title_font = ImageFont.truetype(font_path, 92) if font_path else ImageFont.load_default()
    sub_font = ImageFont.truetype(font_path, 44) if font_path else ImageFont.load_default()
    title = "GTA 6 MEGA COMPILATION"
    subtitle = f"{len(videos)} VIDEOS • ALL UPDATES"
    title_box = draw.textbbox((0, 0), title, font=title_font, stroke_width=7)
    sub_box = draw.textbbox((0, 0), subtitle, font=sub_font, stroke_width=4)
    draw.text(
        ((1280 - (title_box[2] - title_box[0])) / 2, 270),
        title,
        font=title_font,
        fill=(255, 214, 0),
        stroke_width=7,
        stroke_fill=(0, 0, 0),
    )
    draw.text(
        ((1280 - (sub_box[2] - sub_box[0])) / 2, 390),
        subtitle,
        font=sub_font,
        fill=(255, 255, 255),
        stroke_width=4,
        stroke_fill=(0, 0, 0),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=94)


def build_compilation(videos: list[Path]) -> dict[str, Any]:
    if not videos:
        raise RuntimeError("No timestamped *_graphics.mp4 videos were found.")

    CHANNEL_ROOT.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="gta6-compilation-") as folder:
        workdir = Path(folder)
        normalized: list[Path] = []
        for index, source in enumerate(videos, start=1):
            media = probe_media(source)
            output = workdir / f"normalized_{index:04d}.mp4"
            print(f"[{index}/{len(videos)}] Normalizing {source.name}", flush=True)
            normalize_video(source, output, bool(media["has_audio"]))
            normalized.append(output)
            sources.append({"path": str(source), "duration": media["duration"]})

        concatenate_videos(normalized, OUTPUT_VIDEO, workdir)
        create_thumbnail(videos, THUMBNAIL_PATH, workdir)

    metadata = build_metadata(sources)
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_video": str(OUTPUT_VIDEO),
        "thumbnail": str(THUMBNAIL_PATH),
        "metadata": str(METADATA_PATH),
        "source_video_count": len(sources),
        "sources": sources,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def upload_compilation() -> None:
    env = os.environ.copy()
    env["VICE_STUDIO_CONFIG_PATH"] = str(UPLOAD_CONFIG)
    subprocess.run(
        [sys.executable, "-m", "agents.upload_agent.agent"],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-upload", action="store_true", help="Build without uploading.")
    parser.add_argument("--upload-only", action="store_true", help="Upload an existing compilation.")
    parser.add_argument("--limit", type=int, help="Use only the newest N completed videos.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.upload_only:
        for path in (OUTPUT_VIDEO, METADATA_PATH, THUMBNAIL_PATH):
            if not path.exists():
                raise FileNotFoundError(f"Compilation artifact not found: {path}")
    else:
        videos = discover_completed_videos()
        if args.limit is not None:
            if args.limit <= 0:
                raise ValueError("--limit must be greater than zero.")
            videos = videos[-args.limit :]
        manifest = build_compilation(videos)
        print(f"Compilation created: {manifest['output_video']}")
        print(f"Source videos: {manifest['source_video_count']}")
        print(f"Metadata: {manifest['metadata']}")
        print(f"Thumbnail: {manifest['thumbnail']}")

    if not args.no_upload:
        upload_compilation()


if __name__ == "__main__":
    main()
