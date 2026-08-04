"""Generate narration audio from the latest channel script."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import edge_tts
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
        "rate": config.get("rate", "+0%"),
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
    manifest_path = save_manifest(config, script, output_audio_path)

    print(f"Script path: {_resolve_project_path(config['input_script_path'])}")
    print(f"Script lines: {len(script.splitlines())}")
    print(f"Voice: {voice}")
    print(f"Rate: {rate}")
    print(f"Output audio path: {output_audio_path}")
    print(f"Manifest path: {manifest_path}")

    return {
        "input_script_path": str(_resolve_project_path(config["input_script_path"])),
        "output_audio_path": str(output_audio_path),
        "voice": voice,
        "manifest_path": str(manifest_path),
        "script_line_count": len(script.splitlines()),
    }


def _resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    return PROJECT_ROOT / candidate


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
