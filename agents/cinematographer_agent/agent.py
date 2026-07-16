"""Cinematographer agent for Vice Studio."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
STORYBOARD_PATH = ROOT_DIR / "channels" / "gta6" / "storyboards" / "latest_storyboard.txt"
OLLAMA_URL = "http://localhost:11434/api/generate"


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "enabled": True,
        "agent_name": "cinematographer_agent",
        "channel": "gta6",
        "model": "llama3.1:8b",
        "input_path": "channels/gta6/storyboards/latest_storyboard.txt",
        "output_path": "channels/gta6/storyboards/latest_cinematography.txt",
    }


def load_storyboard() -> list[str]:
    if not STORYBOARD_PATH.exists():
        raise FileNotFoundError(f"Storyboard not found: {STORYBOARD_PATH}")
    text = STORYBOARD_PATH.read_text(encoding="utf-8").strip()
    scenes = [line.strip() for line in text.splitlines() if line.strip()]
    return scenes


def build_prompt(scene: str) -> str:
    return (
        "You are a professional cinematographer specializing in cinematic vertical videos for YouTube Shorts. "
        "Convert the following storyboard scene into EXACTLY ONE cinematography block. "
        "Return ONLY the single block in this exact format: "
        "Shot Type: [type] | Camera: [camera] | Lens: [lens] | Lighting: [lighting] | "
        "Color Grade: [grade] | Weather / Atmosphere: [atmosphere] | Motion: [motion] | "
        "Duration: [2-4 seconds] | Transition: [hard cut/cross dissolve/whip pan/fade/through black]. "
        "Use ARRI Alexa 65, anamorphic lenses, neon reflections, orange-teal color grade, vertical 9:16 framing. "
        "Do not generate multiple shots or alternatives. Generate ONE block only. "
        "Do not include any text before or after the block. "
        "Do not mention GTA logos, official UI, or official footage. "
        "Keep each field concise.\n\n"
        f"Storyboard scene:\n{scene}\n\n"
        "Generate the single cinematography block now. Return ONLY the block."
    )


def generate_cinematography(scene: str) -> str:
    prompt_text = build_prompt(scene)
    config = load_config()

    payload = {
        "model": config.get("model", "llama3.1:8b"),
        "temperature": 0.7,
        "max_tokens": 300,
        "prompt": prompt_text,
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()
    text = response.text.strip()
    lines = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "response" in item and item["response"] is not None:
            lines.append(str(item["response"]))
        elif "text" in item and item["text"] is not None:
            lines.append(str(item["text"]))
    output = "".join(lines).strip()
    if not output:
        raise ValueError("Unexpected Ollama response format")
    return output


def clean_output(text: str) -> str:
    """Extract the first valid cinematography block, ignoring alternatives and extras."""
    lines = text.splitlines()
    filtered_lines: list[str] = []
    in_extra_section = False

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        lower = line_stripped.lower()
        if any(phrase in lower for phrase in ["additional", "plus", "alternative", "also here", "optional", "shot 2", "shot 3"]):
            in_extra_section = True
            continue
        if in_extra_section and any(field in line_stripped for field in ["Shot Type:", "Camera:", "Lens:"]):
            break
        if in_extra_section:
            continue

        filtered_lines.append(line_stripped)

    output = " ".join(filtered_lines).strip()
    output = re.sub(r"\*\*", "", output)
    output = re.sub(r"^Here.*?:", "", output)
    output = re.sub(r"\s+\|", "|", output)
    output = re.sub(r"\|\s+", "| ", output)
    output = re.sub(r"\s+", " ", output).strip()

    if not output:
        raise ValueError("No valid cinematography block found")
    return output


def save_cinematography(shots: dict[int, str]) -> None:
    config = load_config()
    output_path = ROOT_DIR / config.get("output_path", "channels/gta6/storyboards/latest_cinematography.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = ROOT_DIR / "channels" / "gta6" / "storyboards" / f"{timestamp}_cinematography.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for scene_num, shot in sorted(shots.items()):
        lines.append(f"Scene {scene_num}: {shot}")
    content = "\n\n".join(lines) + "\n"
    output_path.write_text(content, encoding="utf-8")
    archive_path.write_text(content, encoding="utf-8")


def run() -> None:
    scenes = load_storyboard()
    shots: dict[int, str] = {}

    for i, scene in enumerate(scenes, 1):
        raw_output = generate_cinematography(scene)
        cleaned = clean_output(raw_output)
        shots[i] = cleaned

    save_cinematography(shots)
    for scene_num, shot in sorted(shots.items()):
        print(f"Scene {scene_num}: {shot}")
        print()


if __name__ == "__main__":
    run()
