"""Generate a YouTube thumbnail for the current video."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoFileClip

from services.llm.service import generate as generate_text
from vice_studio.config_loader import load_component_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_config() -> dict[str, Any]:
    return load_component_config(CONFIG_PATH)


def read_text(path_value: str) -> str:
    path = resolve_path(path_value)
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def read_json(path_value: str) -> dict[str, Any]:
    path = resolve_path(path_value)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_thumbnail_prompt(script: str, knowledge: dict[str, Any], storyboard: dict[str, Any], config: dict[str, Any]) -> str:
    title = str(knowledge.get("title", "")).strip()
    summary = str(knowledge.get("summary", "")).strip()

    prompt = f"""
You are a YouTube thumbnail art director.

Create ONE image-generation prompt for a high-CTR YouTube thumbnail.
Use only the story, emotion, and facts provided.
Do not use logos.
Do not use readable text.
Do not mention copyrighted character names.
Do not invent facts.
Make it visually clickable, dramatic, clean, and bold.
Landscape 16:9 thumbnail, strong foreground subject, cinematic lighting, clear focal point, high contrast.

Video title:
{title}

Video summary:
{summary}

Script:
{script}

Storyboard JSON:
{json.dumps(storyboard, ensure_ascii=False)[:3000]}

Return ONLY the final image prompt.
""".strip()

    raw = generate_text(prompt, config)
    return clean_prompt(raw)


def clean_prompt(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.strip("\"'“”")
    text = re.sub(r"^(prompt|thumbnail prompt)\s*:\s*", "", text, flags=re.I)
    return text


def build_thumbnail_design(script: str, knowledge: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    title = str(knowledge.get("title", "")).strip()
    summary = str(knowledge.get("summary", "")).strip()
    max_words = int(config.get("hook_text_max_words", 4))

    prompt = f"""
You are a viral YouTube thumbnail creative director and CTR optimizer.

Return ONLY valid JSON.
No markdown.
No explanation.

Create 10 different thumbnail concepts for this video.
Score each concept for click-through potential from 1 to 10.
Choose the strongest concept as the winner.
Then improve the winning concept once before returning it.

Rules:
- Hook must be maximum {max_words} words.
- Hook must be short, emotional, and clickable.
- The thumbnail must communicate the central conflict within one second.
- Never create generic cinematic artwork.
- Use one dominant subject.
- Use one secondary subject.
- Use one visual contrast.
- Use one obvious emotion.
- Background prompt must leave clear empty space for hook overlay.
- No copyrighted logos.
- No readable text, numbers, currency symbols, logos, UI, signs, labels, or letters inside the background image prompt.
- Do not ask the image model to draw the hook, price, number, or any written symbol.
- Represent numbers/prices visually using contrast, size, crowds, objects, premium items, ordinary items, reactions, arrows, glow, or composition.
- Do not invent facts.
- The image must visually match the hook.
- Prefer clear YouTube-style visual conflict, contrast, curiosity, and scale.

Video title:
{title}

Video summary:
{summary}

Script:
{script}

Return JSON with this exact structure:
{{
  "concepts": [
    {{
      "name": "...",
      "central_conflict": "...",
      "dominant_subject": "...",
      "secondary_subject": "...",
      "visual_contrast": "...",
      "emotion": "...",
      "hook": "...",
      "background_prompt": "...",
      "placement": "top|bottom|left|right|center",
      "font_color": "#FFD400",
      "stroke_color": "#000000",
      "accent_color": "#FF2E88",
      "style": "viral_gaming|warning|luxury|breaking_news|mystery",
      "ctr_score": 9.1,
      "ctr_reasoning": "..."
    }}
  ],
  "winner_index": 0,
  "improved_winner": {{
    "name": "...",
    "central_conflict": "...",
    "dominant_subject": "...",
    "secondary_subject": "...",
    "visual_contrast": "...",
    "emotion": "...",
    "hook": "...",
    "background_prompt": "...",
    "placement": "top|bottom|left|right|center",
    "font_color": "#FFD400",
    "stroke_color": "#000000",
    "accent_color": "#FF2E88",
    "style": "viral_gaming|warning|luxury|breaking_news|mystery",
    "ctr_score": 9.5,
    "ctr_reasoning": "..."
  }}
}}
""".strip()

    raw = generate_text(prompt, config)

    try:
        data = json.loads(extract_json_text(raw))
    except Exception:
        return fallback_thumbnail_design(script, knowledge)

    concepts = data.get("concepts", [])
    if not isinstance(concepts, list) or not concepts:
        return fallback_thumbnail_design(script, knowledge)

    winner_index = data.get("winner_index", 0)
    try:
        winner_index = int(winner_index)
    except Exception:
        winner_index = 0

    if winner_index < 0 or winner_index >= len(concepts):
        winner_index = 0

    winner = data.get("improved_winner") or concepts[winner_index]
    if not isinstance(winner, dict):
        return fallback_thumbnail_design(script, knowledge)

    design = normalize_thumbnail_design(winner, script, knowledge)
    design["concepts"] = concepts
    design["winner_index"] = winner_index
    design["concept_name"] = str(winner.get("name", "")).strip()
    design["ctr_score"] = winner.get("ctr_score", "")
    design["central_conflict"] = str(winner.get("central_conflict", "")).strip()
    design["dominant_subject"] = str(winner.get("dominant_subject", "")).strip()
    design["secondary_subject"] = str(winner.get("secondary_subject", "")).strip()
    design["visual_contrast"] = str(winner.get("visual_contrast", "")).strip()
    design["emotion"] = str(winner.get("emotion", "")).strip()

    return design


def extract_json_text(raw: str) -> str:
    raw = (raw or "").strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    return match.group(0) if match else raw


def normalize_thumbnail_design(data: dict[str, Any], script: str, knowledge: dict[str, Any]) -> dict[str, Any]:
    fallback = fallback_thumbnail_design(script, knowledge)

    hook = clean_hook_text(str(data.get("hook", ""))) or fallback["hook"]
    background_prompt = clean_prompt(str(data.get("background_prompt", ""))) or fallback["background_prompt"]

    placement = str(data.get("placement", fallback["placement"])).lower().strip()
    if placement not in {"top", "bottom", "left", "right", "center"}:
        placement = fallback["placement"]

    return {
        "background_prompt": background_prompt,
        "hook": hook,
        "placement": placement,
        "font_color": normalize_hex_color(str(data.get("font_color", fallback["font_color"])), fallback["font_color"]),
        "stroke_color": normalize_hex_color(str(data.get("stroke_color", fallback["stroke_color"])), fallback["stroke_color"]),
        "accent_color": normalize_hex_color(str(data.get("accent_color", fallback["accent_color"])), fallback["accent_color"]),
        "style": str(data.get("style", fallback["style"])).strip() or fallback["style"],
        "ctr_reasoning": str(data.get("ctr_reasoning", "")).strip(),
    }


def fallback_thumbnail_design(script: str, knowledge: dict[str, Any]) -> dict[str, Any]:
    return {
        "background_prompt": fallback_prompt(script, knowledge),
        "hook": fallback_hook_text(knowledge),
        "placement": "top",
        "font_color": "#FFD400",
        "stroke_color": "#000000",
        "accent_color": "#FF2E88",
        "style": "viral_gaming",
        "ctr_reasoning": "Fallback design based on available video topic.",
    }


def clean_hook_text(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9$%!?\s]", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip().upper()
    words = text.split()
    return " ".join(words[:5])


def fallback_hook_text(knowledge: dict[str, Any]) -> str:
    title = str(knowledge.get("title", "")).upper()
    summary = str(knowledge.get("summary", "")).upper()

    combined = f"{title} {summary}"

    if "$100" in combined:
        return "THE $100 EDITION?!"
    if "$80" in combined:
        return "$80 SHOCK"
    if re.search(r"\bAI\b", combined):
        return "AI CONTROL?"
    if "HEIST" in combined or "PATCH" in combined:
        return "HEIST FIXED?"
    if "TRAILER" in combined:
        return "NEW TRAILER?"
    if "RELEASE" in combined:
        return "RELEASE UPDATE"
    return "BIG UPDATE"


def normalize_hex_color(value: str, fallback: str) -> str:
    value = value.strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return value.upper()
    return fallback


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def add_hook_text(image_path: Path, design: dict[str, Any], config: dict[str, Any]) -> None:
    hook_text = str(design.get("hook", "")).strip()
    if not hook_text:
        return

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    width, height = image.size
    font = load_font(int(height * 0.14), bold=True)

    text = hook_text.upper()
    max_width = int(width * 0.88)

    while draw.textbbox((0, 0), text, font=font, stroke_width=8)[2] > max_width and font.size > 40:
        font = load_font(font.size - 6, bold=True)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=8)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    placement = str(design.get("placement", "top")).lower()
    margin = int(height * 0.08)

    if placement == "bottom":
        x = int((width - text_width) / 2)
        y = height - text_height - margin
    elif placement == "left":
        x = int(width * 0.06)
        y = int((height - text_height) / 2)
    elif placement == "right":
        x = width - text_width - int(width * 0.06)
        y = int((height - text_height) / 2)
    elif placement == "center":
        x = int((width - text_width) / 2)
        y = int((height - text_height) / 2)
    else:
        x = int((width - text_width) / 2)
        y = margin

    font_color = hex_to_rgb(str(design.get("font_color", "#FFD400")))
    stroke_color = hex_to_rgb(str(design.get("stroke_color", "#000000")))
    accent_color = hex_to_rgb(str(design.get("accent_color", "#FF2E88")))

    shadow_offset = max(6, int(height * 0.012))

    draw.text(
        (x + shadow_offset, y + shadow_offset),
        text,
        font=font,
        fill=(0, 0, 0),
        stroke_width=12,
        stroke_fill=(0, 0, 0),
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=font_color,
        stroke_width=8,
        stroke_fill=stroke_color,
    )

    underline_y = y + text_height + int(height * 0.025)
    draw.rounded_rectangle(
        [x, underline_y, x + text_width, underline_y + max(10, int(height * 0.02))],
        radius=8,
        fill=accent_color,
    )

    image.save(image_path, quality=95)


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)

    return ImageFont.load_default()


def fallback_prompt(script: str, knowledge: dict[str, Any]) -> str:
    title = str(knowledge.get("title", "")).strip()
    summary = str(knowledge.get("summary", "")).strip()
    subject = title or summary or script[:120]
    return (
        "cinematic high-contrast YouTube thumbnail, landscape 16:9, "
        "dramatic foreground subject, bold composition, emotional visual tension, "
        "premium documentary style, realistic lighting, clean background, "
        f"visual story inspired by: {subject}, "
        "no readable text, no logos, no watermark"
    )


def generate_image(prompt: str, config: dict[str, Any]) -> Path:
    output_path = resolve_path(config["output_image_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if str(config.get("provider", "pollinations")).lower() == "video_frame":
        return generate_video_frame_thumbnail(output_path, config)

    base_url = str(config.get("pollinations_base_url", "https://image.pollinations.ai/prompt")).rstrip("/")
    model = str(config.get("pollinations_model", "flux"))
    width = int(config.get("width", 1280))
    height = int(config.get("height", 720))
    timeout = int(config.get("timeout_seconds", 180))
    seed = random.randint(1, 2_147_483_647)

    url = f"{base_url}/{quote(prompt)}"
    params = {
        "model": model,
        "width": width,
        "height": height,
        "seed": seed,
        "nologo": "true",
        "enhance": "false",
    }

    response = requests.get(url, params=params, timeout=timeout)

    if not response.ok:
        raise RuntimeError(f"Thumbnail image request failed: {response.status_code} {response.text[:500]}")

    output_path.write_bytes(response.content)
    return output_path


def generate_video_frame_thumbnail(output_path: Path, config: dict[str, Any]) -> Path:
    """Create a thumbnail background from the current video's own stock footage."""
    source_path = resolve_path(str(config["source_video_path"]))
    if not source_path.exists():
        raise FileNotFoundError(f"Thumbnail source video not found: {source_path}")

    width = int(config.get("width", 1280))
    height = int(config.get("height", 720))
    with VideoFileClip(str(source_path)) as video:
        duration = float(video.duration or 0)
        frame_ratio = min(max(float(config.get("frame_position_ratio", 0.2)), 0.0), 1.0)
        frame_time = max(0.0, min(duration * frame_ratio, max(duration - 0.05, 0.0)))
        image = Image.fromarray(video.get_frame(frame_time)).convert("RGB")

    source_ratio = image.width / image.height
    target_ratio = width / height
    if source_ratio > target_ratio:
        crop_width = int(image.height * target_ratio)
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    else:
        crop_height = int(image.width / target_ratio)
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))

    image.resize((width, height), Image.Resampling.LANCZOS).save(output_path, quality=95)
    return output_path


def save_manifest(prompt: str, image_path: Path, config: dict[str, Any]) -> Path:
    output_folder = resolve_path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)

    prompt_path = resolve_path(config["output_prompt_path"])
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")

    manifest_path = output_folder / "thumbnail_manifest.json"
    manifest = {
        "service_name": config.get("service_name"),
        "channel": config.get("channel"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prompt_path": str(prompt_path),
        "image_path": str(image_path),
        "width": config.get("width"),
        "height": config.get("height"),
        "provider": config.get("provider", "pollinations"),
        "model": config.get("pollinations_model"),
        "design": globals().get("_LAST_THUMBNAIL_DESIGN", {}),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def run() -> dict[str, Any]:
    config = load_config()

    if not config.get("enabled", True):
        raise RuntimeError("Thumbnail service is disabled in config.json.")

    script = read_text(str(config["script_path"]))
    knowledge = read_json(str(config["knowledge_path"]))
    storyboard = read_json(str(config["storyboard_path"]))

    try:
        design = build_thumbnail_design(script, knowledge, config)
    except Exception:
        design = fallback_thumbnail_design(script, knowledge)

    global _LAST_THUMBNAIL_DESIGN
    _LAST_THUMBNAIL_DESIGN = design

    prompt = design["background_prompt"]
    image_path = generate_image(prompt, config)

    hook_text = ""
    if config.get("enable_hook_text", True):
        hook_text = design.get("hook", "")
        add_hook_text(image_path, design, config)

    manifest_path = save_manifest(prompt, image_path, config)

    print(f"Thumbnail prompt: {prompt}")
    print(f"Thumbnail hook: {hook_text}")
    print(f"Thumbnail concept: {design.get('concept_name', '')}")
    print(f"Central conflict: {design.get('central_conflict', '')}")
    print(f"Dominant subject: {design.get('dominant_subject', '')}")
    print(f"Secondary subject: {design.get('secondary_subject', '')}")
    print(f"Visual contrast: {design.get('visual_contrast', '')}")
    print(f"Emotion: {design.get('emotion', '')}")
    print(f"Thumbnail style: {design.get('style', '')}")
    print(f"Thumbnail placement: {design.get('placement', '')}")
    print(f"CTR score: {design.get('ctr_score', '')}")
    print(f"CTR reasoning: {design.get('ctr_reasoning', '')}")
    print(f"Thumbnail image: {image_path}")
    print(f"Manifest path: {manifest_path}")

    return {
        "thumbnail_path": str(image_path),
        "manifest_path": str(manifest_path),
    }


if __name__ == "__main__":
    run()
