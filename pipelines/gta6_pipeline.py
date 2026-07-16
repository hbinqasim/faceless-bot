"""Run the full Vice Studio GTA 6 production pipeline."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINAL_VIDEO_PATH = PROJECT_ROOT / "channels" / "gta6" / "videos" / "final" / "latest_video_graphics.mp4"

PIPELINE_STEPS = [
    ("Research Agent", "agents/research_agent/agent.py"),
    ("Script Agent", "agents/script_agent/agent.py"),
    ("Storyboard Agent", "agents/storyboard_agent/agent.py"),
    ("Visual Director Agent", "agents/visual_director_agent/agent.py"),
    ("Prompt Engineer Agent", "agents/prompt_engineer_agent/agent.py"),
    ("Image Generation Service", "services/image_generation/service.py"),
    ("Animation Service", "services/animation/service.py"),
    ("Narration Service", "services/narration/service.py"),
    ("Music Service", "services/music/service.py"),
    ("Video Composer Service", "services/video_composer/service.py"),
    ("Graphics Service", "services/graphics/service.py"),
    ("Thumbnail Service", "services/thumbnail/service.py"),
    ("Metadata Agent", "agents/metadata_agent/agent.py"),
    ("Upload Agent", "agents/upload_agent/agent.py"),
]




def cleanup_stale_generated_files() -> None:
    """Remove generated scene artifacts that should never be reused."""
    patterns = [
        PROJECT_ROOT / "channels" / "gta6" / "images" / "generated" / "scene_*.png",
        PROJECT_ROOT / "channels" / "gta6" / "images" / "generated" / "scene_*.jpg",
        PROJECT_ROOT / "channels" / "gta6" / "videos" / "scenes" / "scene_*.mp4",
    ]
    deleted_count = 0
    for pattern in patterns:
        for path in pattern.parent.glob(pattern.name):
            path.unlink()
            deleted_count += 1

    print(f"Deleted stale generated files: {deleted_count}")


def run_step(name: str, relative_path: str, index: int, total: int) -> None:
    print(f"\n[{index}/{total}] {name}")
    module_name = relative_path.replace("/", ".").removesuffix(".py")
    subprocess.run(
        [sys.executable, "-m", module_name],
        cwd=PROJECT_ROOT,
        check=True,
    )


def run(video_number: int = 0) -> None:
    """Run every GTA 6 pipeline step in order."""
    start_time = time.perf_counter()
    cleanup_stale_generated_files()

    research_steps = PIPELINE_STEPS[:3]
    production_steps = PIPELINE_STEPS[3:]
    max_topic_attempts = 5

    try:
        topic_ready = False

        for attempt in range(1, max_topic_attempts + 1):
            print(f"\nTopic attempt {attempt}/{max_topic_attempts}")

            try:
                for offset, (name, relative_path) in enumerate(research_steps, start=1):
                    run_step(name, relative_path, offset, len(PIPELINE_STEPS))

                topic_ready = True
                break

            except subprocess.CalledProcessError:
                print("Topic rejected. Trying another topic...")

        if not topic_ready:
            raise RuntimeError("No usable topic found after all attempts.")

        start_index = len(research_steps) + 1

        for offset, (name, relative_path) in enumerate(production_steps, start=start_index):
            run_step(name, relative_path, offset, len(PIPELINE_STEPS))

    except subprocess.CalledProcessError as error:
        elapsed = time.perf_counter() - start_time
        print(f"\nPipeline stopped after failure in step: {error.cmd}")
        print(f"Total execution time: {elapsed:.2f} seconds")
        raise SystemExit(error.returncode) from error

    except RuntimeError as error:
        elapsed = time.perf_counter() - start_time
        print(f"\nPipeline stopped: {error}")
        print(f"Total execution time: {elapsed:.2f} seconds")
        raise SystemExit(1) from error

    elapsed = time.perf_counter() - start_time
    print("\nPipeline completed successfully.")
    print(f"Total execution time: {elapsed:.2f} seconds")
    print(f"Final video path: {FINAL_VIDEO_PATH}")


if __name__ == "__main__":
    video_number = 0
    if len(sys.argv) > 1:
        video_number = int(sys.argv[1])
    run(video_number)
