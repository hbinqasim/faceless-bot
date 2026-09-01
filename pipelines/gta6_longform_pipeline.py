"""Run the isolated 2-3 minute GTA 6 long-form production pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from moviepy import AudioFileClip, VideoFileClip


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = PROJECT_ROOT / "configs" / "gta6_longform"
CHANNEL_ROOT = PROJECT_ROOT / "channels" / "gta6_longform"
FINAL_VIDEO_PATH = CHANNEL_ROOT / "videos" / "final" / "latest_video_graphics.mp4"
MIN_DURATION_SECONDS = 120.0
MAX_DURATION_SECONDS = 180.0

PIPELINE_STEPS = [
    ("Research Agent", "agents.research_agent.agent", "research.json"),
    ("Long-form Script Agent", "agents.script_agent.agent", "script.json"),
    ("Long-form Storyboard Agent", "agents.storyboard_agent.agent", "storyboard.json"),
    ("Visual Director Agent", "agents.visual_director_agent.agent", "visual_director.json"),
    ("Stock Query Agent", "agents.prompt_engineer_agent.agent", "prompt_engineer.json"),
    ("Narration Service", "services.narration.service", "narration.json"),
    ("Pixabay Stock Footage Service", "services.image_generation.service", "stock_media.json"),
    ("Footage Normalization Service", "services.animation.service", "animation.json"),
    ("Music Service", "services.music.service", "music.json"),
    ("Video Composer Service", "services.video_composer.service", "video_composer.json"),
    ("Graphics Service", "services.graphics.service", "graphics.json"),
    ("Thumbnail Service", "services.thumbnail.service", "thumbnail.json"),
    ("Metadata Agent", "agents.metadata_agent.agent", "metadata.json"),
    ("Upload Agent", "agents.upload_agent.agent", "upload.json"),
]


def cleanup_stale_working_files() -> None:
    """Remove only replaceable long-form working assets from earlier runs."""
    folders = [
        CHANNEL_ROOT / "media" / "downloaded",
        CHANNEL_ROOT / "videos" / "scenes",
    ]
    deleted_count = 0
    for folder in folders:
        if not folder.exists():
            continue
        for pattern in ("scene_*.mp4", "scene_*_metadata.json"):
            for path in folder.glob(pattern):
                path.unlink()
                deleted_count += 1
    print(f"Deleted stale long-form working files: {deleted_count}")


def run_step(
    name: str,
    module_name: str,
    config_name: str,
    index: int,
    total: int,
    extra_args: list[str] | None = None,
) -> None:
    print(f"\n[{index}/{total}] {name}")
    env = os.environ.copy()
    env["VICE_STUDIO_CONFIG_PATH"] = str(CONFIG_ROOT / config_name)
    subprocess.run(
        [sys.executable, "-m", module_name, *(extra_args or [])],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def validate_audio_duration() -> float:
    audio_path = CHANNEL_ROOT / "audio" / "voice.mp3"
    with AudioFileClip(str(audio_path)) as audio:
        duration = float(audio.duration or 0)
    _validate_duration(duration, "Narration")
    print(f"Narration duration validated: {duration:.2f} seconds")
    return duration


def validate_script_word_budget(
    script_path: Path | None = None,
    config_path: Path | None = None,
) -> int:
    """Reject stale short scripts before narration synthesis or scene work."""
    active_script_path = script_path or CHANNEL_ROOT / "scripts" / "latest_script.txt"
    active_config_path = config_path or CONFIG_ROOT / "script.json"
    config = json.loads(active_config_path.read_text(encoding="utf-8"))
    script = active_script_path.read_text(encoding="utf-8")
    word_count = len(script.split())
    minimum = int(config.get("target_min_words", 0))
    maximum = int(config.get("target_max_words", 0))

    if minimum and word_count < minimum:
        raise RuntimeError(
            f"Long-form script has {word_count} words; at least {minimum} are required "
            "for a 2-3 minute narration. Resume from step 2 to regenerate it."
        )
    if maximum and word_count > maximum:
        raise RuntimeError(
            f"Long-form script has {word_count} words; the maximum is {maximum}. "
            "Resume from step 2 to regenerate it."
        )

    print(f"Long-form script word budget validated: {word_count} words")
    return word_count


def validate_final_duration() -> float:
    with VideoFileClip(str(FINAL_VIDEO_PATH)) as video:
        duration = float(video.duration or 0)
    _validate_duration(duration, "Final video")
    print(f"Final duration validated: {duration:.2f} seconds")
    return duration


def _validate_duration(duration: float, label: str) -> None:
    if not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
        raise RuntimeError(
            f"{label} must be 2-3 minutes; generated duration was {duration:.2f} seconds."
        )


def run(
    video_number: int = 0,
    upload: bool = True,
    start_at: int = 1,
    stop_after: int | None = None,
) -> None:
    """Run the separate long-form profile and optionally stop before upload."""
    start_time = time.perf_counter()
    if start_at <= 7:
        cleanup_stale_working_files()

    steps = PIPELINE_STEPS if upload else PIPELINE_STEPS[:-1]
    total = len(steps)
    topic_steps = steps[:3]
    max_topic_attempts = 5

    if not 1 <= start_at <= total:
        raise ValueError(f"--start-at must be between 1 and {total}")
    if stop_after is not None and not start_at <= stop_after <= total:
        raise ValueError(f"--stop-after must be between {start_at} and {total}")

    # Starting after the script step means the pipeline will consume an
    # existing script. Validate it before expensive storyboard/media/audio work.
    if start_at >= 3:
        validate_script_word_budget()

    try:
        if start_at == 1:
            topic_ready = False
            for attempt in range(1, max_topic_attempts + 1):
                print(f"\nLong-form topic attempt {attempt}/{max_topic_attempts}")
                try:
                    for index, (name, module, config) in enumerate(topic_steps, start=1):
                        run_step(name, module, config, index, total)
                        if module == "agents.script_agent.agent":
                            validate_script_word_budget()
                    topic_ready = True
                    break
                except subprocess.CalledProcessError:
                    print("Long-form topic or script rejected. Trying another fresh topic...")

            if not topic_ready:
                raise RuntimeError("No usable long-form topic found after all attempts.")
            remaining_steps = steps[3:]
            remaining_start = 4
        else:
            print(f"Resuming long-form pipeline at step {start_at}.")
            remaining_steps = steps[start_at - 1 :]
            remaining_start = start_at

        for index, (name, module, config) in enumerate(remaining_steps, start=remaining_start):
            args = [str(video_number)] if module == "agents.upload_agent.agent" else None
            run_step(name, module, config, index, total, args)
            if module == "agents.script_agent.agent":
                validate_script_word_budget()
            if module == "services.narration.service":
                validate_audio_duration()
            if module == "services.graphics.service":
                validate_final_duration()
            if stop_after == index:
                print(f"Stopped after requested step {stop_after}.")
                break

    except subprocess.CalledProcessError as error:
        elapsed = time.perf_counter() - start_time
        print(f"\nLong-form pipeline stopped after failure in step: {error.cmd}")
        print(f"Total execution time: {elapsed:.2f} seconds")
        raise SystemExit(error.returncode) from error
    except RuntimeError as error:
        elapsed = time.perf_counter() - start_time
        print(f"\nLong-form pipeline stopped: {error}")
        print(f"Total execution time: {elapsed:.2f} seconds")
        raise SystemExit(1) from error

    elapsed = time.perf_counter() - start_time
    if stop_after is not None and stop_after < total:
        print("\nLong-form pipeline checkpoint completed successfully.")
    else:
        print("\nLong-form pipeline completed successfully.")
    print(f"Total execution time: {elapsed:.2f} seconds")
    print(f"Final video path: {FINAL_VIDEO_PATH}")
    if not upload:
        print("Upload skipped by --no-upload.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-number", type=int, default=0)
    parser.add_argument("--no-upload", action="store_true")
    parser.add_argument(
        "--start-at",
        type=int,
        default=1,
        help="Resume at a numbered pipeline step using existing earlier outputs.",
    )
    parser.add_argument(
        "--stop-after",
        type=int,
        help="Stop after a numbered step so intermediate output can be reviewed.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run(
        arguments.video_number,
        upload=not arguments.no_upload,
        start_at=arguments.start_at,
        stop_after=arguments.stop_after,
    )
