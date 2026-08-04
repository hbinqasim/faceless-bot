"""Provider-agnostic image generation service."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from vice_studio.config_loader import load_component_config

try:
    from .comfy_provider import ComfyProvider
    from .manual_provider import ManualProvider
    from .pixabay_provider import PixabayProvider
    from .placeholder_provider import PlaceholderProvider
    from .pollinations_provider import PollinationsProvider
    from .gemini_image_provider import GeminiImageProvider
    from .provider_base import ProviderBase
except ImportError:  # pragma: no cover - supports direct script execution.
    from comfy_provider import ComfyProvider
    from manual_provider import ManualProvider
    from pixabay_provider import PixabayProvider
    from placeholder_provider import PlaceholderProvider
    from pollinations_provider import PollinationsProvider
    from gemini_image_provider import GeminiImageProvider
    from provider_base import ProviderBase


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
SCENE_HEADER = re.compile(r"^\s*Scene\s+(\d+)\s*:\s*(.*)\s*$", re.IGNORECASE)


def resolve_project_path(path: str | Path) -> Path:
    """Resolve a project-relative path to an absolute path."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    return PROJECT_ROOT / candidate


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load service configuration."""
    if config_path is not None:
        with Path(config_path).open("r", encoding="utf-8") as file:
            return json.load(file)
    return load_component_config(CONFIG_PATH)


def load_prompts(config: dict[str, Any] | None = None) -> str:
    """Read the configured prompt input file."""
    active_config = config or load_config()
    input_path = resolve_project_path(active_config["input_path"])
    return input_path.read_text(encoding="utf-8")


def load_structured_prompts(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Load final prompts from JSON when available."""
    input_json_path = config.get("input_json_path")
    if not input_json_path:
        return []

    path = resolve_project_path(str(input_json_path))
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("prompts", [])
    if not isinstance(items, list):
        return []

    scenes: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        scene_number = int(item.get("scene_number", len(scenes) + 1))
        scenes.append(
            {
                "scene_number": scene_number,
                "scene_label": f"scene_{scene_number:02d}",
                "prompt": str(item.get("prompt", "")).strip(),
                "negative_prompt": str(item.get("negative_prompt", "")).strip(),
                "script_line": str(item.get("script_line", "")).strip(),
                "source_scene": item.get("source_scene", {}),
            }
        )

    return [scene for scene in scenes if scene["prompt"]]


def load_media_queries(config: dict[str, Any]) -> dict[str, str]:
    """Load scene-specific stock-media search queries when configured."""
    media_queries_path = config.get("media_queries_path")
    if not media_queries_path:
        return {}

    path = resolve_project_path(str(media_queries_path))
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("media_queries", [])
    if not isinstance(items, list):
        return {}

    queries: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue

        scene_label = str(item.get("scene_label", "")).strip()
        search_query = str(item.get("search_query", "")).strip()

        if scene_label and search_query:
            queries[scene_label] = search_query

    return queries


def parse_scene_prompts(text: str) -> list[dict[str, Any]]:
    """Parse final prompts into numbered scene records."""
    scenes: list[dict[str, Any]] = []
    current_scene_number: int | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        match = SCENE_HEADER.match(line)
        if match:
            if current_scene_number is not None:
                scenes.append(_build_scene(current_scene_number, current_lines))

            current_scene_number = int(match.group(1))
            first_line = match.group(2).strip()
            current_lines = [first_line] if first_line else []
            continue

        if current_scene_number is not None:
            stripped = line.strip()
            if stripped:
                current_lines.append(stripped)

    if current_scene_number is not None:
        scenes.append(_build_scene(current_scene_number, current_lines))

    if scenes:
        return scenes

    return [
        _build_scene(index, [prompt])
        for index, prompt in enumerate(_split_prompt_blocks(text), start=1)
    ]


def get_provider(config: dict[str, Any] | None = None) -> ProviderBase:
    """Return the configured image generation provider."""
    active_config = config or load_config()
    provider_name = active_config.get("provider", "manual").lower()

    if provider_name == "manual":
        return ManualProvider()
    if provider_name == "placeholder":
        return PlaceholderProvider()
    if provider_name == "pixabay":
        return PixabayProvider(active_config)
    if provider_name == "comfy":
        return ComfyProvider(active_config)
    if provider_name == "gemini_image":
        return GeminiImageProvider(active_config)
    if provider_name == "pollinations":
        return PollinationsProvider(active_config)

    raise ValueError(f"Unsupported image generation provider: {provider_name}")


def generate_images(
    prompts: list[dict[str, Any]],
    provider: ProviderBase | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate or prepare outputs for each parsed scene prompt."""
    active_config = config or load_config()
    active_provider = provider or get_provider(active_config)
    provider_name = active_config.get("provider", "manual").lower()
    output_folder = resolve_project_path(active_config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)

    media_queries = load_media_queries(active_config) if provider_name == "pixabay" else {}

    prepared: list[dict[str, Any]] = []
    for scene in prompts:
        scene_label = scene["scene_label"]
        provider_prompt = media_queries.get(scene_label, scene["prompt"])
        output_path = _output_path_for_provider(output_folder, scene_label, provider_name)
        metadata = {
            "scene_number": scene["scene_number"],
            "scene_label": scene_label,
            "channel": active_config.get("channel"),
            "image_width": active_config.get("image_width"),
            "image_height": active_config.get("image_height"),
            "prompt_length": len(scene["prompt"]),
            "negative_prompt": scene.get("negative_prompt", ""),
            "script_line": scene.get("script_line", ""),
            "source_scene": scene.get("source_scene", {}),
            "provider_prompt": provider_prompt,
        }
        result = active_provider.generate_image(
            provider_prompt,
            output_path,
            metadata=metadata,
        )
        prepared.append({**scene, **result})

    return prepared


def save_manifest(
    prepared: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> Path:
    """Save the generation manifest and return its path."""
    active_config = config or load_config()
    output_folder = resolve_project_path(active_config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)
    manifest_path = output_folder / "generation_manifest.json"

    manifest = {
        "service_name": active_config.get("service_name"),
        "channel": active_config.get("channel"),
        "provider": active_config.get("provider"),
        "input_path": active_config.get("input_path"),
        "output_folder": active_config.get("output_folder"),
        "image_width": active_config.get("image_width"),
        "image_height": active_config.get("image_height"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prepared_count": len(prepared),
        "scenes": prepared,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def run() -> dict[str, Any]:
    """Run the image generation service."""
    config = load_config()
    if not config.get("enabled", True):
        raise RuntimeError("Image generation service is disabled in config.json.")

    prompts = load_structured_prompts(config)
    if not prompts:
        text = load_prompts(config)
        prompts = parse_scene_prompts(text)
    prepared = generate_images(prompts, get_provider(config), config)
    manifest_path = save_manifest(prepared, config)
    output_folder = resolve_project_path(config["output_folder"])

    print(f"Prompts loaded: {len(prompts)}")
    print(f"Prompts prepared: {len(prepared)}")
    print(f"Output folder: {output_folder}")
    print(f"Manifest path: {manifest_path}")
    image_paths = [item["image_path"] for item in prepared if "image_path" in item]
    if image_paths:
        print("Generated image paths:")
        for image_path in image_paths:
            print(f"- {image_path}")

    return {
        "prompts_loaded": len(prompts),
        "prompts_prepared": len(prepared),
        "output_folder": str(output_folder),
        "manifest_path": str(manifest_path),
        "image_paths": image_paths,
    }


def _build_scene(scene_number: int, lines: list[str]) -> dict[str, Any]:
    prompt = " ".join(lines).strip()
    return {
        "scene_number": scene_number,
        "scene_label": f"scene_{scene_number:02d}",
        "prompt": prompt,
    }


def _split_prompt_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _output_path_for_provider(
    output_folder: Path,
    scene_label: str,
    provider_name: str,
) -> Path:
    if provider_name == "placeholder":
        return output_folder / f"{scene_label}.jpg"
    if provider_name == "comfy":
        return output_folder / f"{scene_label}.png"
    if provider_name == "pixabay":
        return output_folder / f"{scene_label}.mp4"

    if provider_name == "pollinations":
        return output_folder / f"{scene_label}.jpg"

    if provider_name == "gemini_image":
        return output_folder / f"{scene_label}.png"

    return output_folder / f"{scene_label}_prompt.txt"


if __name__ == "__main__":
    run()
