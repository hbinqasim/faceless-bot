"""Config-driven knowledge agent for Vice Studio."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Knowledge config not found: {CONFIG_PATH}")

    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Knowledge config must be a JSON object.")

    return data


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def load_verified_topic(config: dict[str, Any]) -> dict[str, Any]:
    input_path = resolve_path(str(config.get("input_path", "")))

    if not input_path.exists():
        raise FileNotFoundError(f"Verified topic not found: {input_path}")

    data = json.loads(input_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Verified topic must be a JSON object.")

    return data


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-z])of\b", r"\1 of", text)
    text = re.sub(r"([a-z])in\b", r"\1 in", text)
    text = re.sub(r"([a-z])to\b", r"\1 to", text)
    text = re.sub(r"([a-z])have\b", r"\1 have", text)
    text = re.sub(r"([a-z])launch\b", r"\1 launch", text)
    text = re.sub(r"([a-z])release\b", r"\1 release", text)
    return re.sub(r"\s+", " ", text).strip()


def verified_facts(topic: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    facts = topic.get("verified_facts", [])

    if not isinstance(facts, list):
        return []

    minimum_confidence = float(config.get("min_confidence", 0.6))
    max_facts = int(config.get("max_facts", 6))

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in facts:
        if not isinstance(item, dict):
            continue

        fact = clean_text(str(item.get("fact", "")))

        if not fact:
            continue

        if fact.lower() in seen:
            continue

        confidence = float(item.get("confidence", 0.0))

        if confidence < minimum_confidence:
            continue

        seen.add(fact.lower())

        cleaned.append(
            {
                "fact": fact,
                "category": str(item.get("category", "unclassified")),
                "confidence": confidence,
                "source": str(item.get("source", topic.get("source", ""))),
                "source_url": str(item.get("source_url", topic.get("url", ""))),
            }
        )

        if len(cleaned) >= max_facts:
            break

    return cleaned


def build_knowledge_json(topic: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    facts = verified_facts(topic, config)

    return {
        "agent_name": config.get("agent_name", "knowledge_agent"),
        "channel": config.get("channel", topic.get("channel", "")),
        "niche": topic.get("niche", config.get("niche", "")),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "title": topic.get("title", ""),
        "summary": clean_text(str(topic.get("summary", ""))),
        "topic_type": topic.get("topic_type", ""),
        "confidence": topic.get("confidence", 0.0),
        "verification_status": topic.get("verification_status", "unknown"),
        "why_trending": clean_text(str(topic.get("why_trending", ""))),
        "facts": facts,
        "entities": topic.get("entities", []),
        "keywords": topic.get("keywords", []),
        "sources": topic.get("sources", []),
        "source_url": topic.get("url", ""),
        "source_name": topic.get("source", "")
    }


def build_markdown_brief(knowledge: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Knowledge Brief: {knowledge.get('title', '')}",
        "",
        f"Topic type: {knowledge.get('topic_type', '')}",
        f"Confidence: {knowledge.get('confidence', '')}",
        f"Verification status: {knowledge.get('verification_status', '')}",
        "",
        "## Summary",
        "",
        str(knowledge.get("summary", "")),
        "",
        "## Why Trending",
        "",
        str(knowledge.get("why_trending", "")),
        "",
        "## Verified Facts",
        "",
    ]

    facts = knowledge.get("facts", [])

    if isinstance(facts, list) and facts:
        for item in facts:
            if isinstance(item, dict):
                fact = item.get("fact", "")
                confidence = item.get("confidence", "")
                category = item.get("category", "")
                source = item.get("source", "")
                lines.append(f"- {fact} [{category}, confidence {confidence}, source: {source}]")
    else:
        lines.append("- No verified facts available.")

    lines.extend(["", "## Sources", ""])

    sources = knowledge.get("sources", [])

    if isinstance(sources, list) and sources:
        for source in sources:
            if isinstance(source, dict):
                name = source.get("name", "Source")
                url = source.get("url", "")
                lines.append(f"- {name}: {url}")
    elif knowledge.get("source_url"):
        lines.append(f"- {knowledge.get('source_name', 'Source')}: {knowledge.get('source_url')}")

    return "\n".join(lines) + "\n"


def save_outputs(knowledge: dict[str, Any], config: dict[str, Any]) -> None:
    json_path = resolve_path(str(config.get("output_json_path", "")))
    md_path = resolve_path(str(config.get("output_path", "")))

    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(knowledge, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown_brief(knowledge), encoding="utf-8")


def run() -> None:
    config = load_config()

    if not config.get("enabled", True):
        print("Knowledge agent disabled.")
        return

    topic = load_verified_topic(config)
    knowledge = build_knowledge_json(topic, config)
    save_outputs(knowledge, config)

    fact_count = len(knowledge.get("facts", []))

    print("Knowledge generated.")
    print("Facts:", fact_count)
    print("Output:", resolve_path(str(config.get("output_json_path", ""))))

    minimum_facts = int(config.get("minimum_facts_required", 1))
    if fact_count < minimum_facts:
        raise RuntimeError(
            f"Not enough verified facts to continue: {fact_count}/{minimum_facts}"
        )


if __name__ == "__main__":
    run()
