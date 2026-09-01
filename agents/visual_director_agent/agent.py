"""Generic AI visual director agent for Vice Studio."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from services.llm.service import generate as generate_text
from vice_studio.config_loader import load_component_config


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict[str, Any]:
    return load_component_config(CONFIG_PATH)


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT_DIR / path


def load_json(path_value: str) -> dict[str, Any]:
    path = resolve_path(path_value)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_prompt(storyboard: dict[str, Any], knowledge: dict[str, Any], config: dict[str, Any]) -> str:
    aspect_ratio = str(config.get("aspect_ratio", "vertical 9:16"))
    return f"""
You are the visual director for an autonomous faceless video studio.

Return ONLY valid JSON.
No markdown.
No explanation.

Create a fresh visual plan for the video scenes.

Rules:
- Do not reuse fixed visual anchors.
- Do not default to retail shelves, game cases, boxes, or product shots unless the story truly requires it.
- Each scene must visually match its script line.
- Keep it generic and scalable for any niche.
- No readable text, logos, UI, watermarks, signs, labels, or brand marks.
- Avoid real people faces unless essential; silhouettes, hands, screens, objects, environments, and symbolic visuals are preferred.
- Make every scene visually distinct.
- Use cinematic {aspect_ratio} composition.
- Use realistic, documentary-style imagery.
- Use concrete, real-world, topic-relevant objects whenever possible.
- Avoid purely abstract glowing networks, abstract particles, portals, digital tendrils, or fantasy visuals unless the story has no concrete visual option.
- Prefer objects, devices, locations, screens without readable UI, hands, silhouettes, crowds, rooms, streets, maps, cameras, phones, microphones, controllers, consoles, documents, dashboards without text, or symbolic real-world props.
- Use topic-relevant visual metaphors only when they are still visually concrete.
- The foreground must be a clear real-world subject.
- Midground and background must support the story.

Video title:
{knowledge.get("title", "")}

Video summary:
{knowledge.get("summary", "")}

Verified facts:
{json.dumps(knowledge.get("facts", []), ensure_ascii=False)[:2500]}

Storyboard:
{json.dumps(storyboard, ensure_ascii=False)[:int(config.get("storyboard_prompt_max_chars", 4000))]}

Return JSON with this exact structure:
{{
  "scenes": [
    {{
      "scene_number": 1,
      "script_line": "...",
      "purpose": "...",
      "emotion": "...",
      "shot_type": "...",
      "visual_subject": "...",
      "visual_world": "...",
      "camera_style": "...",
      "lighting_style": "...",
      "composition_style": "...",
      "foreground": "...",
      "midground": "...",
      "background": "...",
      "texture_notes": "..."
    }}
  ]
}}
""".strip()


def extract_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("Visual director output must be a JSON object.")

    return data


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_visual_text(value: Any, fallback: str) -> str:
    """Reject visual directions that would render brands or readable text."""
    text = clean_text(value)
    forbidden = [
        r"\blogos?\b",
        r"\bbrand marks?\b",
        r"\bwatermarks?\b",
        r"\breadable (?:text|words?|letters?)\b",
        r"\bsign (?:that )?(?:reads|says|showing)\b",
        r"\b(?:netflix|take[- ]?two|rockstar|gta)\b",
    ]
    if not text or any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in forbidden):
        return fallback
    return text


def normalize_scene(scene: dict[str, Any], fallback: dict[str, Any], index: int, config: dict[str, Any] | None = None) -> dict[str, Any]:
    script_line = clean_text(scene.get("script_line") or fallback.get("script_line"))
    subject = safe_visual_text(
        scene.get("visual_subject") or scene.get("foreground") or fallback.get("subject"),
        "story-relevant real-world object",
    )

    return {
        "scene_number": int(scene.get("scene_number") or fallback.get("scene_number") or index),
        "script_line": script_line,
        "purpose": clean_text(scene.get("purpose") or fallback.get("purpose")),
        "emotion": clean_text(scene.get("emotion") or fallback.get("emotion")),
        "shot_type": clean_text(scene.get("shot_type") or fallback.get("shot_type")),
        "visual_subject": subject,
        "visual_world": safe_visual_text(scene.get("visual_world"), "cinematic real-world documentary scene"),
        "camera_style": clean_text(scene.get("camera_style") or "realistic vertical documentary camera, shallow depth of field"),
        "lighting_style": clean_text(scene.get("lighting_style") or "cinematic natural lighting with realistic shadows"),
        "composition_style": clean_text(scene.get("composition_style") or f"{(config or {}).get('aspect_ratio', 'vertical 9:16')}, clear foreground, layered depth"),
        "foreground": safe_visual_text(scene.get("foreground"), subject),
        "midground": safe_visual_text(scene.get("midground"), "story-relevant supporting environment"),
        "background": safe_visual_text(scene.get("background"), "atmospheric cinematic background"),
        "texture_notes": clean_text(scene.get("texture_notes") or "real surfaces, natural imperfections, believable reflections, no clean AI plastic look"),
    }


def fallback_visual_plan(storyboard: dict[str, Any], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    scenes = storyboard.get("scenes", [])
    output = []

    if not isinstance(scenes, list):
        return output

    for index, scene in enumerate(scenes, start=1):
        line = clean_text(scene.get("script_line", ""))
        subject = clean_text(scene.get("subject") or line or "central symbolic object")
        output.append({
            "scene_number": index,
            "script_line": line,
            "purpose": clean_text(scene.get("purpose", "")),
            "emotion": clean_text(scene.get("emotion", "")),
            "shot_type": clean_text(scene.get("shot_type", "")),
            "visual_subject": subject,
            "visual_world": "cinematic documentary world matching the story topic",
            "camera_style": "realistic vertical documentary frame, strong depth, natural imperfections",
            "lighting_style": "cinematic lighting with realistic shadows and atmosphere",
            "composition_style": f"{(config or {}).get('aspect_ratio', 'vertical 9:16')}, dominant foreground subject, layered midground and background",
            "foreground": subject,
            "midground": "story-relevant environment supporting the scene",
            "background": "atmospheric background connected to the topic",
            "texture_notes": "real surfaces, imperfect details, believable reflections, no clean AI plastic look",
        })

    return output


def build_visual_plan(storyboard: dict[str, Any], knowledge: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    prompt = build_prompt(storyboard, knowledge, config)

    try:
        raw = generate_text(prompt, config)
        data = extract_json(raw)
        generated_scenes = data.get("scenes", [])
    except Exception:
        return fallback_visual_plan(storyboard, config)

    storyboard_scenes = storyboard.get("scenes", [])
    if not isinstance(generated_scenes, list) or not generated_scenes:
        return fallback_visual_plan(storyboard, config)

    max_scenes = int(config.get("max_scenes", len(generated_scenes)))
    target_count = min(max_scenes, len(storyboard_scenes)) if isinstance(storyboard_scenes, list) else max_scenes
    output = []

    for index in range(1, target_count + 1):
        fallback = {}
        if isinstance(storyboard_scenes, list) and index - 1 < len(storyboard_scenes):
            fallback = storyboard_scenes[index - 1]
        scene = generated_scenes[index - 1] if index - 1 < len(generated_scenes) else {}
        if isinstance(scene, dict):
            output.append(normalize_scene(scene, fallback, index, config))

    return output or fallback_visual_plan(storyboard, config)


def run() -> None:
    config = load_config()

    if not config.get("enabled", True):
        print("Visual director disabled.")
        return

    storyboard = load_json(str(config["storyboard_json_path"]))
    knowledge = load_json(str(config.get("knowledge_path", "channels/gta6/research/knowledge.json")))

    visual_scenes = build_visual_plan(storyboard, knowledge, config)

    output = {
        "agent_name": config.get("agent_name"),
        "channel": config.get("channel"),
        "niche": config.get("niche"),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "scene_count": len(visual_scenes),
        "scenes": visual_scenes,
    }

    output_path = resolve_path(str(config["output_json_path"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Visual plan generated.")
    print("Scenes:", len(visual_scenes))
    print("Output:", output_path)


if __name__ == "__main__":
    run()
