"""Generate narration audio from the latest channel script."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import edge_tts
from moviepy import AudioFileClip
from vice_studio.config_loader import load_component_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")


def load_config() -> dict[str, Any]:
    """Load narration service configuration."""
    return load_component_config(CONFIG_PATH)


def load_script(config: dict[str, Any] | None = None) -> str:
    """Load the configured script text."""
    active_config = config or load_config()
    script_path = _resolve_project_path(active_config["input_script_path"])
    return script_path.read_text(encoding="utf-8")


async def generate_voice(
    script: str,
    output_path: str | Path,
    voice: str,
    rate: str = "+0%",
) -> Path:
    """Generate voiceover audio with edge-tts."""
    audio_path = Path(output_path)
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    communicate = edge_tts.Communicate(script, voice, rate=rate)
    await communicate.save(str(audio_path))
    return audio_path


def save_manifest(
    config: dict[str, Any],
    script: str,
    output_audio_path: str | Path,
    actual_rate: str | None = None,
    duration_seconds: float | None = None,
    rate_adapted: bool = False,
) -> Path:
    """Save narration generation details and the exact script used."""
    output_folder = _resolve_project_path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)
    manifest_path = output_folder / "narration_manifest.json"
    input_script_path = _resolve_project_path(config["input_script_path"])
    audio_path = Path(output_audio_path)

    manifest = {
        "service_name": config.get("service_name"),
        "channel": config.get("channel"),
        "input_script_path": str(input_script_path),
        "output_audio_path": str(audio_path),
        "voice": config.get("voice"),
        "requested_rate": config.get("rate", "+0%"),
        "rate": actual_rate or config.get("rate", "+0%"),
        "rate_adapted": rate_adapted,
        "duration_seconds": round(duration_seconds, 3) if duration_seconds is not None else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script_line_count": len(script.splitlines()),
        "script": script,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


async def run() -> dict[str, Any]:
    """Run the narration service."""
    config = load_config()
    if not config.get("enabled", True):
        raise RuntimeError("Narration service is disabled in config.json.")

    script = load_script(config)
    output_folder = _resolve_project_path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)
    output_audio_path = output_folder / config.get("output_file", "voice.mp3")
    voice = config.get("voice", "en-US-GuyNeural")
    rate = str(config.get("rate", "+0%"))

    await generate_voice(script, output_audio_path, voice, rate)
    duration = measure_audio_duration(output_audio_path)
    actual_rate = rate
    rate_adapted = False

    minimum_duration = float(config.get("target_min_duration_seconds", 0))
    if minimum_duration and duration < minimum_duration:
        target_duration = minimum_duration + float(
            config.get("duration_safety_margin_seconds", 2.0)
        )
        max_adjustments = max(1, int(config.get("max_rate_adjustments", 2)))
        for _ in range(max_adjustments):
            adjusted_rate = calculate_adaptive_rate(
                duration,
                target_duration,
                actual_rate,
                int(config.get("minimum_adaptive_rate_percent", -5)),
                int(config.get("maximum_adaptive_rate_percent", 15)),
            )
            if adjusted_rate == actual_rate:
                break
            print(
                f"Narration was {duration:.2f}s; regenerating at {adjusted_rate} "
                f"to target at least {minimum_duration:.0f}s."
            )
            actual_rate = adjusted_rate
            rate_adapted = True
            await generate_voice(script, output_audio_path, voice, actual_rate)
            duration = measure_audio_duration(output_audio_path)
            if duration >= minimum_duration:
                break

    manifest_path = save_manifest(
        config,
        script,
        output_audio_path,
        actual_rate=actual_rate,
        duration_seconds=duration,
        rate_adapted=rate_adapted,
    )

    print(f"Script path: {_resolve_project_path(config['input_script_path'])}")
    print(f"Script lines: {len(script.splitlines())}")
    print(f"Voice: {voice}")
    print(f"Rate: {actual_rate}")
    print(f"Narration duration: {duration:.2f} seconds")
    print(f"Output audio path: {output_audio_path}")
    print(f"Manifest path: {manifest_path}")

    return {
        "input_script_path": str(_resolve_project_path(config["input_script_path"])),
        "output_audio_path": str(output_audio_path),
        "voice": voice,
        "rate": actual_rate,
        "duration_seconds": duration,
        "manifest_path": str(manifest_path),
        "script_line_count": len(script.splitlines()),
    }


def measure_audio_duration(audio_path: str | Path) -> float:
    with AudioFileClip(str(audio_path)) as audio:
        return float(audio.duration or 0)


def calculate_adaptive_rate(
    current_duration: float,
    target_duration: float,
    current_rate: str,
    minimum_percent: int = -5,
    maximum_percent: int = 15,
) -> str:
    """Estimate an Edge TTS rate that reaches the requested duration."""
    match = re.fullmatch(r"\s*([+-]?\d+)\s*%\s*", current_rate)
    current_percent = int(match.group(1)) if match else 0
    if current_duration <= 0 or target_duration <= 0:
        return format_rate(current_percent)

    current_speed = 1.0 + current_percent / 100.0
    desired_speed = current_duration * current_speed / target_duration
    desired_percent = round((desired_speed - 1.0) * 100.0)
    desired_percent = max(minimum_percent, min(maximum_percent, desired_percent))
    return format_rate(desired_percent)


def format_rate(percent: int) -> str:
    return f"{percent:+d}%"


def _resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    return PROJECT_ROOT / candidate


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
