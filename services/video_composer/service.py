"""Compose animated scene clips into one final vertical video."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, VideoFileClip, concatenate_audioclips, concatenate_videoclips, vfx
from vice_studio.config_loader import load_component_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
SCENE_CLIP_PATTERN = re.compile(r"^scene_(\d+)\.mp4$", re.IGNORECASE)


def load_config() -> dict[str, Any]:
    """Load video composer configuration."""
    return load_component_config(CONFIG_PATH)


def find_scene_clips(config: dict[str, Any] | None = None) -> list[Path]:
    """Find scene MP4 clips in numeric scene order."""
    active_config = config or load_config()
    input_folder = _resolve_project_path(active_config["input_folder"])
    if not input_folder.exists():
        return []

    clips = [
        path
        for path in input_folder.iterdir()
        if path.is_file() and SCENE_CLIP_PATTERN.match(path.name)
    ]
    return sorted(clips, key=_scene_sort_key)


def compose_video(clips: list[Path], config: dict[str, Any]) -> dict[str, Any]:
    """Concatenate scene clips and write final outputs."""
    if not clips:
        raise RuntimeError("No scene clips found to compose.")

    output_folder = _resolve_project_path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)

    channel = config.get("channel", "video")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    timestamped_output = output_folder / f"{timestamp}_{channel}_video.mp4"
    latest_output = output_folder / "latest_video.mp4"

    fps = int(config.get("fps", 30))
    codec = config.get("codec", "libx264")
    audio_codec = config.get("audio_codec", "aac")
    transition_seconds = float(config.get("transition_seconds", 0))
    use_voiceover = bool(config.get("use_voiceover", False))
    configured_audio_path = config.get("audio_path", "")
    audio_path = _resolve_project_path(configured_audio_path) if configured_audio_path else None

    music_path = PROJECT_ROOT / "channels" / str(config.get("channel")) / "music" / "current_music.mp3"

    source_clips = [VideoFileClip(str(path)) for path in clips]
    clip_items = [
        {
            "input_clip": str(path),
            "duration": float(clip.duration or 0),
        }
        for path, clip in zip(clips, source_clips)
    ]

    composed = None
    adjusted_video = None
    final_video = None
    audio_clip = None
    music_clip = None
    mixed_audio = None
    extra_clips = []
    extra_audio_clips = []
    audio_used = False
    music_used = False
    audio_duration = None
    try:
        transitioned_clips = _apply_fade_transitions(source_clips, transition_seconds)
        composed = concatenate_videoclips(transitioned_clips, method="compose")
        final_video = composed

        if use_voiceover and audio_path is not None:
            if audio_path.exists():
                audio_clip = AudioFileClip(str(audio_path))
                audio_duration = float(audio_clip.duration or 0)
                if audio_duration > 0:
                    adjusted_video, extra_clips = _match_video_duration_to_audio(
                        composed,
                        source_clips[-1],
                        audio_duration,
                        fps,
                    )
                    final_audio = audio_clip

                    if music_path.exists():
                        music_volume = float(config.get("music_volume", 0.14))
                        music_clip = AudioFileClip(str(music_path))
                        music_loop, extra_audio_clips = _loop_audio_to_duration(
                            music_clip,
                            audio_duration,
                        )
                        music_loop = music_loop.with_volume_scaled(music_volume)
                        mixed_audio = CompositeAudioClip([audio_clip, music_loop])
                        final_audio = mixed_audio
                        music_used = True

                    final_video = adjusted_video.with_audio(final_audio)
                    audio_used = True
                else:
                    print(f"Warning: voiceover audio has no duration: {audio_path}")
            else:
                print(f"Warning: voiceover audio not found: {audio_path}")

        final_duration = float(final_video.duration or 0)

        final_video.write_videofile(
            str(timestamped_output),
            fps=fps,
            codec=codec,
            audio=bool(final_video.audio),
            audio_codec=audio_codec,
            preset="medium",
            ffmpeg_params=["-movflags", "+faststart"],
            logger=None,
            pixel_format="yuv420p",
        )
        shutil.copy2(timestamped_output, latest_output)
    finally:
        if final_video is not None and final_video is not composed:
            final_video.close()
        if adjusted_video is not None and adjusted_video is not composed:
            adjusted_video.close()
        if mixed_audio is not None:
            mixed_audio.close()
        if music_clip is not None:
            music_clip.close()
        if audio_clip is not None:
            audio_clip.close()
        for clip in extra_audio_clips:
            clip.close()
        for clip in extra_clips:
            clip.close()
        if composed is not None:
            composed.close()
        for clip in source_clips:
            clip.close()

    return {
        "input_clips": clip_items,
        "output_video": str(latest_output),
        "timestamped_output_video": str(timestamped_output),
        "total_duration": final_duration,
        "final_duration": final_duration,
        "clip_count": len(clips),
        "transition_seconds": transition_seconds,
        "audio_path": str(audio_path) if audio_path is not None else None,
        "audio_used": audio_used,
        "music_used": music_used,
        "music_path": str(music_path) if music_path.exists() else None,
        "audio_duration": audio_duration,
    }


def save_manifest(items: dict[str, Any]) -> Path:
    """Save composition manifest."""
    config = load_config()
    output_folder = _resolve_project_path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)
    manifest_path = output_folder / "composition_manifest.json"

    manifest = {
        "service_name": config.get("service_name"),
        "channel": config.get("channel"),
        "input_folder": config.get("input_folder"),
        "output_folder": config.get("output_folder"),
        "fps": config.get("fps"),
        "codec": config.get("codec"),
        "audio_codec": config.get("audio_codec"),
        "transition_seconds": config.get("transition_seconds"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **items,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def run() -> dict[str, Any]:
    """Run the video composer service."""
    config = load_config()
    if not config.get("enabled", True):
        raise RuntimeError("Video composer service is disabled in config.json.")

    clips = find_scene_clips(config)
    composition = compose_video(clips, config)
    manifest_path = save_manifest(composition)

    print(f"Clips found: {len(clips)}")
    print(f"Audio used: {str(composition['audio_used']).lower()}")
    if composition["audio_used"]:
        print(f"Audio duration: {composition['audio_duration']:.2f} seconds")
    print(f"Final duration: {composition['final_duration']:.2f} seconds")
    print(f"Latest output path: {composition['output_video']}")
    print(f"Timestamped output path: {composition['timestamped_output_video']}")
    print(f"Manifest path: {manifest_path}")

    return {
        "clips_found": len(clips),
        "audio_used": composition["audio_used"],
        "audio_duration": composition["audio_duration"],
        "final_duration": composition["final_duration"],
        "latest_output_path": composition["output_video"],
        "timestamped_output_path": composition["timestamped_output_video"],
        "manifest_path": str(manifest_path),
    }


def _apply_fade_transitions(
    clips: list[VideoFileClip],
    transition_seconds: float,
) -> list[VideoFileClip]:
    if transition_seconds <= 0 or len(clips) < 2:
        return clips

    transitioned = []
    for index, clip in enumerate(clips):
        effects = []
        if index > 0:
            effects.append(vfx.FadeIn(transition_seconds, initial_color=[0, 0, 0]))
        if index < len(clips) - 1:
            effects.append(vfx.FadeOut(transition_seconds, final_color=[0, 0, 0]))

        transitioned.append(clip.with_effects(effects) if effects else clip)

    return transitioned


def _match_video_duration_to_audio(
    video_clip: VideoFileClip,
    last_source_clip: VideoFileClip,
    audio_duration: float,
    fps: int,
) -> tuple[VideoFileClip, list[ImageClip]]:
    video_duration = float(video_clip.duration or 0)
    if audio_duration < video_duration:
        return video_clip.subclipped(0, audio_duration), []

    if audio_duration > video_duration:
        freeze_duration = audio_duration - video_duration
        frame_time = max(float(last_source_clip.duration or 0) - (1 / fps), 0)
        freeze_frame = last_source_clip.get_frame(frame_time)
        freeze_clip = ImageClip(freeze_frame).with_duration(freeze_duration).with_fps(fps)
        extended_clip = concatenate_videoclips(
            [video_clip, freeze_clip],
            method="compose",
        )
        return extended_clip, [freeze_clip]

    return video_clip, []


def _resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    return PROJECT_ROOT / candidate


def _scene_sort_key(path: Path) -> int:
    match = SCENE_CLIP_PATTERN.match(path.name)
    if not match:
        return 0

    return int(match.group(1))


def _loop_audio_to_duration(audio_clip: AudioFileClip, duration: float):
    clips = []
    current_duration = 0.0

    while current_duration < duration:
        remaining = duration - current_duration
        source_duration = float(audio_clip.duration or 0)
        clip_duration = min(source_duration, remaining)

        if clip_duration <= 0:
            break

        clips.append(audio_clip.subclipped(0, clip_duration))
        current_duration += clip_duration

    if not clips:
        return audio_clip.subclipped(0, duration), []

    if len(clips) == 1:
        return clips[0], clips

    return concatenate_audioclips(clips), clips


if __name__ == "__main__":
    run()
