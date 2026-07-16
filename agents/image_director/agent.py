"""Image director agent for Vice Studio."""

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
        "agent_name": "image_director",
        "channel": "gta6",
        "model": "llama3.1:8b",
        "input_path": "channels/gta6/storyboards/latest_storyboard.txt",
        "output_path": "channels/gta6/images/latest_image_prompts.txt",
        "style_suffix": "vertical 9:16 composition, cinematic open-world crime drama aesthetic, Miami-inspired neon atmosphere, ultra detailed, dramatic lighting, realistic textures, no text, no logo, no watermark",
    }


def load_storyboard() -> list[str]:
    if not STORYBOARD_PATH.exists():
        raise FileNotFoundError(f"Storyboard not found: {STORYBOARD_PATH}")
    text = STORYBOARD_PATH.read_text(encoding="utf-8").strip()
    scenes = [line.strip() for line in text.splitlines() if line.strip()]
    return scenes


def build_prompt(scene: str) -> str:
    return (
        "You are a professional AI image prompt engineer specializing in cinematic vertical visuals for YouTube Shorts. "
        "Convert the following storyboard scene into a detailed, polished AI image prompt. "
        "The prompt must be suitable for AI image generation and describe only visual elements. "
        "Use specific lighting, mood, composition, and atmosphere descriptions. "
        "Avoid exact GTA logos, official UI, copyrighted branding, or claims of official footage. "
        "Avoid text overlays, watermarks, and real celebrities. "
        "Return ONLY the image prompt. No intro. No explanation.\n\n"
        f"Storyboard scene:\n{scene}\n\n"
        "Generate the detailed image prompt now."
    )


def generate_image_prompt(scene: str) -> str:
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


def clean_prompt(text: str) -> str:
    remove_phrases = ["here is", "image prompt:", "prompt:", "ai image prompt:"]
    line = text.strip()
    lower = line.lower()
    if any(phrase in lower for phrase in remove_phrases):
        idx = next(
            (lower.find(phrase) for phrase in remove_phrases if phrase in lower), -1
        )
        if idx != -1:
            phrase_len = max(len(p) for p in remove_phrases if p in lower)
            line = line[idx + phrase_len :].strip()
    line = re.sub(r'^[\*\-\u2022]\s*', "", line)
    line = re.sub(r'^"', "", line)
    line = re.sub(r'"$', "", line)
    line = re.sub(r"^'"  , "", line)
    line = re.sub(r"'$", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def save_image_prompts(prompts: dict[int, str]) -> None:
    config = load_config()
    output_path = ROOT_DIR / config.get("output_path", "channels/gta6/images/latest_image_prompts.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = ROOT_DIR / "channels" / "gta6" / "images" / f"{timestamp}_image_prompts.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for scene_num, prompt in sorted(prompts.items()):
        lines.append(f"Scene {scene_num}: {prompt}")
    content = "\n\n".join(lines) + "\n"
    output_path.write_text(content, encoding="utf-8")
    archive_path.write_text(content, encoding="utf-8")


def run() -> None:
    config = load_config()
    style_suffix = config.get(
        "style_suffix",
        "vertical 9:16 composition, cinematic open-world crime drama aesthetic, Miami-inspired neon atmosphere, ultra detailed, dramatic lighting, realistic textures, no text, no logo, no watermark",
    )

    scenes = load_storyboard()
    prompts: dict[int, str] = {}

    for i, scene in enumerate(scenes, 1):
        raw_prompt = generate_image_prompt(scene)
        cleaned = clean_prompt(raw_prompt)
        final_prompt = f"{cleaned}. {style_suffix}"
        prompts[i] = final_prompt

    save_image_prompts(prompts)
    for scene_num, prompt in sorted(prompts.items()):
        print(f"Scene {scene_num}: {prompt}")
        print()


if __name__ == "__main__":
    run()
