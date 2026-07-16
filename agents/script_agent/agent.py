"""Generic script agent for Vice Studio."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from services.llm.service import generate as generate_llm



ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT_DIR / path


def clean_text(value: str) -> str:
    value = str(value or "")
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def load_knowledge(config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_path(str(config["knowledge_path"]))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("knowledge.json must contain an object")
    return data


def fact_lines(knowledge: dict[str, Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for key in ["facts", "key_facts"]:
        items = knowledge.get(key, [])

        if not isinstance(items, list):
            continue

        for item in items:
            if isinstance(item, dict):
                fact = clean_text(str(item.get("fact", "")))
            else:
                fact = clean_text(str(item))

            if not fact:
                continue

            key_text = fact.lower()

            if key_text in seen:
                continue

            seen.add(key_text)
            output.append(fact)

    if not output:
        title = clean_text(str(knowledge.get("title", "")))
        summary = clean_text(str(knowledge.get("summary", "")))

        if title:
            output.append(title)

        if summary:
            output.append(summary)

    return output


def build_prompt(knowledge: dict[str, Any], config: dict[str, Any]) -> str:
    facts = "\n".join(f"- {fact}" for fact in fact_lines(knowledge))
    avoid_items = knowledge.get("avoid", [])
    if isinstance(avoid_items, list):
        avoid = "\n".join(f"- {clean_text(str(item))}" for item in avoid_items if clean_text(str(item)))
    else:
        avoid = ""
    cta = str(config["cta"])

    return f"""
You are writing a YouTube Shorts voiceover.

Return ONLY the spoken script.
No labels. No bullets. No numbering.
Use ONLY the verified knowledge below.
Do not invent facts.
Do not add source names unless they are in the facts.
Write {config["min_lines"]} to {config["max_lines"]} lines.
Each line must be a complete sentence.
Each line must be {config["max_words_per_line"]} words or fewer.
Do not cut a sentence in half.
If a sentence is too long, rewrite it shorter.
End exactly with this final line:
{cta}

Niche:
{config.get("niche", "")}

Current date:
{datetime.datetime.now().strftime("%Y-%m-%d")}

Title:
{knowledge.get("title", "")}

Summary:
{knowledge.get("summary", "")}

Verified facts:
{facts}

Avoid saying or implying:
{avoid}

Write the script.
""".strip()


def call_llm(prompt: str, config: dict[str, Any]) -> str:
    return generate_llm(prompt)


def clean_script(raw: str, config: dict[str, Any], knowledge: dict[str, Any]) -> str:
    cta = str(config["cta"]).strip()
    min_lines = int(config["min_lines"])
    max_lines = int(config["max_lines"])
    max_words = int(config["max_words_per_line"])

    lines: list[str] = []

    for raw_line in raw.splitlines():
        line = clean_text(raw_line)
        line = re.sub(r"^[\s\*\-•\d\.\)]+", "", line).strip()

        if not line:
            continue

        if line.lower().startswith("follow for more"):
            line = cta

        if line != cta:
            if "follow" in line.lower():
                continue
            if not is_valid_script_line(line, max_words):
                continue

        lines.append(line)

    content = [line for line in lines if line != cta]
    content = remove_duplicates(content)
    content = content[: max_lines - 1]
    content.append(cta)

    if len(content) < min_lines:
        raise ValueError("Not enough valid script lines")

    score = script_quality_score(content, knowledge, cta)
    minimum_score = float(config.get("minimum_script_quality_score", 0.45))
    if score < minimum_score:
        raise ValueError(f"Script quality too low: {score:.2f}")

    return "\n".join(content[:max_lines])


def is_valid_script_line(line: str, max_words: int) -> bool:
    if not line.endswith((".", "?", "!")):
        return False

    words = line.split()
    if len(words) < 4:
        return False

    if len(words) > max_words:
        return False

    if has_spacing_damage(line):
        return False

    if looks_truncated(line):
        return False

    return True


def has_spacing_damage(line: str) -> bool:
    """Detect broken tokenization without topic-specific hardcoding."""
    words = line.split()
    if len(words) < 2:
        return False

    alpha_lengths = [
        len(re.sub(r"[^A-Za-z]", "", word))
        for word in words
    ]

    short_alpha_tokens = sum(1 for length in alpha_lengths if length == 1)
    if short_alpha_tokens >= 2:
        return True

    for index in range(1, len(words) - 1):
        previous_word = re.sub(r"[^A-Za-z]", "", words[index - 1])
        current_word = re.sub(r"[^A-Za-z]", "", words[index])
        next_word = re.sub(r"[^A-Za-z]", "", words[index + 1])

        if len(previous_word) >= 4 and len(current_word) <= 2 and len(next_word) <= 2:
            return True

    return False


def looks_truncated(line: str) -> bool:
    words = [re.sub(r"[^A-Za-z0-9']", "", word).lower() for word in line.split()]
    words = [word for word in words if word]

    if len(words) < 4:
        return True

    last = words[-1]
    if last in function_words():
        return True

    return False


def function_words() -> set[str]:
    return {
        "a", "an", "and", "are", "as", "at", "be", "been", "being",
        "but", "by", "for", "from", "had", "has", "have", "having",
        "if", "in", "into", "is", "of", "on", "or", "that", "the",
        "their", "this", "to", "was", "were", "will", "with", "would",
    }


def remove_duplicates(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []

    for line in lines:
        key = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
        if key and key not in seen:
            output.append(line)
            seen.add(key)

    return output


def script_quality_score(lines: list[str], knowledge: dict[str, Any], cta: str) -> float:
    content = [line for line in lines if line != cta]
    if not content:
        return 0.0

    valid_ratio = sum(is_valid_script_line(line, 999) for line in content) / len(content)
    knowledge_terms = extract_knowledge_terms(knowledge)
    coverage = coverage_score(content, knowledge_terms)

    return (valid_ratio * 0.55) + (coverage * 0.45)


def extract_knowledge_terms(knowledge: dict[str, Any]) -> set[str]:
    text_parts = [
        str(knowledge.get("title", "")),
        str(knowledge.get("summary", "")),
        " ".join(fact_lines(knowledge)),
        " ".join(str(item) for item in knowledge.get("entities", []) if item),
        " ".join(str(item) for item in knowledge.get("keywords", []) if item),
    ]

    text = " ".join(text_parts).lower()
    words = re.findall(r"[a-z0-9][a-z0-9']+", text)

    return {
        word
        for word in words
        if len(word) >= 4 and word not in function_words()
    }


def coverage_score(lines: list[str], knowledge_terms: set[str]) -> float:
    if not knowledge_terms:
        return 1.0

    script_text = " ".join(lines).lower()
    script_terms = set(re.findall(r"[a-z0-9][a-z0-9']+", script_text))
    matched = knowledge_terms.intersection(script_terms)

    return min(len(matched) / max(len(knowledge_terms), 1), 1.0)


def fallback_script(knowledge: dict[str, Any], config: dict[str, Any]) -> str:
    """Build a generic fallback script from current knowledge only."""
    cta = str(config["cta"])
    max_words = int(config.get("max_words_per_line", 8))
    max_lines = int(config.get("max_lines", 7))

    candidates: list[str] = []
    candidates.extend(build_fallback_candidates(knowledge))

    lines: list[str] = []
    for candidate in candidates:
        line = summarize_to_line(candidate, max_words)
        if line and line not in lines and is_valid_script_line(line, max_words):
            lines.append(line)
        if len(lines) >= max_lines - 1:
            break

    if not lines:
        lines = ["A verified update is now developing."]

    lines = lines[: max_lines - 1]
    lines.append(cta)
    return "\n".join(lines)


def build_fallback_candidates(knowledge: dict[str, Any]) -> list[str]:
    """Return only verified fact text for deterministic fallback."""
    return fact_lines(knowledge)


def summarize_to_line(text: str, max_words: int) -> str:
    text = clean_text(text)
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(r"^[\"'“”]+|[\"'“”]+$", "", text).strip()
    text = text.replace("—", " ")

    words = text.split()
    if len(words) < 4:
        return ""

    short = " ".join(words[:max_words]).strip()
    short = short.rstrip(",:;–-")
    if not short.endswith((".", "?", "!")):
        short += "."

    return short


def generate_script() -> str:
    config = load_config()
    knowledge = load_knowledge(config)
    prompt = build_prompt(knowledge, config)

    for _ in range(int(config.get("max_generation_attempts", 3))):
        raw = call_llm(prompt, config)
        try:
            return clean_script(raw, config, knowledge)
        except ValueError:
            continue

    return fallback_script(knowledge, config)


def save_script(script: str) -> None:
    config = load_config()
    channel = str(config.get("channel", "default"))
    output_path = resolve_path(str(config["output_path"]))
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = ROOT_DIR / "channels" / channel / "scripts" / f"{timestamp}_script.txt"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(script + "\n", encoding="utf-8")
    archive_path.write_text(script + "\n", encoding="utf-8")


def run() -> None:
    script = generate_script()
    save_script(script)
    print(script)


if __name__ == "__main__":
    run()
