"""Prompt Engineer Agent for Vice Studio.

Converts Visual Director JSON into model-specific image prompts.
This agent is generic. Niche-specific visuals belong in visual_plan/config,
not in code.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT_DIR / path


def load_visual_plan(config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_path(str(config["visual_plan_path"]))
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Visual plan must be a JSON object.")

    return data


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def sentence(label: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"{label}: {text}."


def build_media_query(scene: dict[str, Any]) -> str:
    """Build a concise stock-media search query from visual direction."""
    stop_words = {
        "unmarked",
        "premium",
        "no",
        "readable",
        "cover",
        "text",
        "with",
        "without",
        "blank",
        "label",
        "area",
        "dominant",
        "clearly",
        "visible",
        "cinematic",
        "documentary",
        "photorealistic",
        "realistic",
        "atmosphere",
        "mood",
        "counter",
        "display",
        "case",
        "game",
        "subtle",
    }

    fields = [
        scene.get("foreground"),
        scene.get("midground"),
        scene.get("background"),
        scene.get("visual_world"),
    ]

    words: list[str] = []
    for field in fields:
        text = str(field or "").lower().replace(",", " ").replace(".", " ")
        for part in text.split():
            cleaned = "".join(char for char in part if char.isalnum() or char == "-").strip()
            if cleaned and cleaned not in stop_words:
                words.append(cleaned)

    query = " ".join(words[:8]).strip()
    if len(query) > 95:
        query = query[:95].rsplit(" ", 1)[0].strip()

    return query or "city street night rain"


def build_prompt(scene: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    quality_terms = as_list(config.get("quality_terms"))
    negative_terms = as_list(config.get("negative_prompt"))

    prompt_parts: list[str] = []
    prompt_parts.extend(quality_terms)

    sentences = [
        sentence("Shot type", scene.get("shot_type")),
        sentence("Foreground subject", scene.get("foreground")),
        sentence("Midground", scene.get("midground")),
        sentence("Background", scene.get("background")),
        sentence("Lighting", scene.get("lighting_style")),
        sentence("Visual world", scene.get("visual_world")),
        sentence("Composition", scene.get("composition_style")),
        sentence("Camera style", scene.get("camera_style")),
        sentence("Emotion", scene.get("emotion")),
        sentence("Texture notes", scene.get("texture_notes")),
        "Keep the foreground subject dominant and clearly visible.",
        "Use realistic shadows, believable reflections, imperfect surfaces, and cinematic depth of field.",
        "No readable text, no logos, no UI, no watermark.",
    ]

    prompt = ", ".join(prompt_parts) + ". " + " ".join(item for item in sentences if item)

    return {
        "scene_number": int(scene["scene_number"]),
        "script_line": str(scene.get("script_line", "")).strip(),
        "prompt": prompt.strip(),
        "media_query": build_media_query(scene),
        "negative_prompt": ", ".join(negative_terms),
        "source_scene": scene,
    }


def save_outputs(items: list[dict[str, Any]], config: dict[str, Any]) -> None:
    output_path = resolve_path(str(config["output_path"]))
    output_json_path = resolve_path(str(config["output_json_path"]))
    media_queries_output_path = resolve_path(
        str(config.get("media_queries_output_path", "channels/default/images/latest_media_queries.json"))
    )

    channel = str(config.get("channel", "default"))
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = ROOT_DIR / "channels" / channel / "images" / f"{timestamp}_final_prompts.txt"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    media_queries_output_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    text_content = "\n\n".join(
        f"Scene {item['scene_number']}: {item['prompt']}"
        for item in items
    ) + "\n"

    output_path.write_text(text_content, encoding="utf-8")
    archive_path.write_text(text_content, encoding="utf-8")

    output_json_path.write_text(
        json.dumps(
            {
                "agent_name": config.get("agent_name"),
                "channel": config.get("channel"),
                "niche": config.get("niche"),
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "scene_count": len(items),
                "prompts": items,
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    media_queries_output_path.write_text(
        json.dumps(
            {
                "agent_name": config.get("agent_name"),
                "channel": config.get("channel"),
                "niche": config.get("niche"),
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "scene_count": len(items),
                "media_queries": [
                    {
                        "scene_number": item["scene_number"],
                        "scene_label": f"scene_{int(item['scene_number']):02d}",
                        "search_query": item["media_query"],
                        "script_line": item.get("script_line", ""),
                    }
                    for item in items
                ],
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


def run() -> None:
    config = load_config()

    if not config.get("enabled", True):
        print("Prompt engineer disabled.")
        return

    visual_plan = load_visual_plan(config)
    scenes = visual_plan.get("scenes", [])

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("No scenes found in visual plan.")

    max_scenes = int(config.get("max_scenes", len(scenes)))
    items = [build_prompt(scene, config) for scene in scenes[:max_scenes]]

    save_outputs(items, config)

    print("Prompt Engineer complete.")
    print("Prompts:", len(items))
    for item in items:
        print(f"Scene {item['scene_number']}: {item['prompt']}")


if __name__ == "__main__":
    run()
