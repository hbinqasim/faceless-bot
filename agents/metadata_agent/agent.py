"""Metadata agent for Vice Studio."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


DEFAULT_CONFIG = {
    "enabled": True,
    "agent_name": "metadata_agent",
    "channel": "gta6",
    "niche": "GTA 6",
    "latest_topic_path": "channels/gta6/research/latest_topic.json",
    "script_path": "channels/gta6/scripts/latest_script.txt",
    "output_path": "channels/gta6/metadata/latest_metadata.json",
    "default_category": "Gaming",
    "default_language": "en",
    "hashtags": ["#shorts"],
    "tags": [],
}


def load_config() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()

    if CONFIG_PATH.exists():
        try:
            user_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config.update(user_config)
        except json.JSONDecodeError:
            print("Warning: metadata config is invalid. Using defaults.")

    return config


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path

def normalize_description_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.replace("Selectedfrom", "Selected from")
    text = text.replace("forGrand", "for Grand")
    text = text.replace("Afterall", "After all")
    return text


def is_bad_description_fact(text: str) -> bool:
    lower = text.lower()

    bad_fragments = [
        "related:",
        "thanks to",
        "search menu",
        "newsletter",
        "subscribe",
        "privacy policy",
        "terms of service"
    ]

    if any(fragment in lower for fragment in bad_fragments):
        return True

    if len(text.split()) > 32:
        return True

    return False

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return data


def load_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    return path.read_text(encoding="utf-8").strip()


def clean_title(text: str, max_length: int = 85) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*[-|]\s*[^-|]{0,30}$", "", text).strip()

    if len(text) <= max_length:
        return text

    return text[: max_length - 3].rsplit(" ", 1)[0] + "..."


def make_title(topic: dict[str, Any], niche: str) -> str:
    title = clean_title(str(topic.get("title", "")))

    if not title:
        return f"Latest {niche} Update"

    if niche.lower() not in title.lower():
        return clean_title(f"{niche}: {title}")

    return title


def make_description(
    topic: dict[str, Any],
    script: str,
    config: dict[str, Any],
) -> str:
    niche = str(config.get("niche", ""))
    hashtags = config.get("hashtags", [])

    title = str(topic.get("title", "")).strip()
    # summary = str(topic.get("summary", "")).strip()
    # why_trending = str(topic.get("why_trending", "")).strip()
    summary = normalize_description_text(str(topic.get("summary", "")))
    why_trending = normalize_description_text(str(topic.get("why_trending", "")))
    url = str(topic.get("url", "")).strip()
    source = str(topic.get("source", "")).strip()

    key_facts = topic.get("key_facts", [])
    if not isinstance(key_facts, list):
        key_facts = []

    lines = [
        f"Latest {niche} update.",
        "",
        title,
        "",
    ]

    if summary:
        lines.extend(["Summary:", summary, ""])

    if why_trending:
        lines.extend(["Why this matters:", why_trending, ""])

    if key_facts:
        lines.append("Key facts:")
        for fact in key_facts[:5]:
            fact_text = normalize_description_text(str(fact))
            if fact_text and not is_bad_description_fact(fact_text):
                lines.append(f"- {fact_text}")
        lines.append("")

    if script:
        lines.extend(["Video script:", script, ""])

    if source or url:
        lines.append("Source:")
        if source:
            lines.append(source)
        if url:
            lines.append(url)
        lines.append("")

    if hashtags:
        lines.append(" ".join(str(tag) for tag in hashtags))

    return "\n".join(lines).strip()


def make_keywords(topic: dict[str, Any], config: dict[str, Any]) -> list[str]:
    tags = [str(tag).strip() for tag in config.get("tags", []) if str(tag).strip()]
    title = str(topic.get("title", ""))
    summary = str(topic.get("summary", ""))

    text = f"{title} {summary}".lower()

    discovered = []
    candidate_terms = [
        "gta 6",
        "grand theft auto vi",
        "rockstar games",
        "vice city",
        "gta 6 news",
        "gta 6 update",
        "gaming news",
        "youtube shorts",
    ]

    for term in candidate_terms:
        if term in text and term not in discovered:
            discovered.append(term)

    combined = tags + discovered

    seen = set()
    final = []

    for item in combined:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        final.append(item)

    return final[:20]



def clean_final_description(text: str) -> str:
    replacements = {
        "Selectedfrom": "Selected from",
        "forGrand": "for Grand",
        "Afterall": "After all",
        "inthe": "in the",
    }

    cleaned = text

    for bad, good in replacements.items():
        cleaned = cleaned.replace(bad, good)

    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
    return cleaned


def build_metadata() -> dict[str, Any]:
    config = load_config()

    if not config.get("enabled", True):
        raise RuntimeError("Metadata agent disabled.")

    topic_path = resolve_path(str(config.get("latest_topic_path")))
    script_path = resolve_path(str(config.get("script_path")))

    topic = load_json(topic_path)
    script = load_text(script_path)

    niche = str(config.get("niche", ""))
    title = make_title(topic, niche)
    description = clean_final_description(make_description(topic, script, config))
    tags = make_keywords(topic, config)

    metadata = {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": config.get("hashtags", []),
        "category": config.get("default_category", "Gaming"),
        "language": config.get("default_language", "en"),
        "source_url": topic.get("url", ""),
        "source_name": topic.get("source", ""),
        "topic_title": topic.get("title", ""),
        "published": topic.get("published", ""),
        "generated_at": datetime.datetime.now().isoformat(),
    }

    return metadata


def save_metadata(metadata: dict[str, Any]) -> None:
    config = load_config()
    output_path = resolve_path(str(config.get("output_path")))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run() -> None:
    metadata = build_metadata()
    save_metadata(metadata)

    print("Metadata generated:")
    print(metadata["title"])


if __name__ == "__main__":
    run()
