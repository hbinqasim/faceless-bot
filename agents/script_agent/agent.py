"""Generic script agent for Vice Studio."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from services.llm.service import generate as generate_llm
from vice_studio.config_loader import load_component_config



ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict[str, Any]:
    return load_component_config(CONFIG_PATH)


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

    target_min_words = int(config.get("target_min_words", 0))
    target_max_words = int(config.get("target_max_words", 0))
    format_name = str(config.get("video_format", "short-form"))
    article_text = str(knowledge.get("article_text", "")).strip()
    word_target = (
        f"Write between {target_min_words} and {target_max_words} words total."
        if target_min_words and target_max_words
        else ""
    )

    return f"""
You are writing a YouTube {format_name} voiceover.

Return ONLY the spoken script.
No labels. No bullets. No numbering.
Use ONLY the verified knowledge below.
Do not invent facts.
Do not add source names unless they are in the facts.
Do not copy calls to comment, visit a link, read an article, or stay tuned from the source material.
Do not promote the source publication; write an original self-contained narration.
Prioritize specific facts and concrete details over generic commentary.
Do not repeat a point in different words and do not praise a company's commitment or dedication.
Cover the concrete bugs, fixes, dates, locations, and gameplay changes in the source before adding any analysis.
Write {config["min_lines"]} to {config["max_lines"]} lines.
{word_target}
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

Verified source material:
{article_text[:12000]}

Avoid saying or implying:
{avoid}

Write the script.
""".strip()


def call_llm(prompt: str, config: dict[str, Any]) -> str:
    return generate_llm(prompt, config)


def clean_script(raw: str, config: dict[str, Any], knowledge: dict[str, Any]) -> str:
    cta = str(config["cta"]).strip()
    min_lines = int(config["min_lines"])
    max_lines = int(config["max_lines"])
    max_words = int(config["max_words_per_line"])

    lines: list[str] = []

    for raw_line in raw.splitlines():
        cleaned_line = clean_text(raw_line)
        cleaned_line = re.sub(r"^[\s\*\-•\d\.\)]+", "", cleaned_line).strip()
        if not cleaned_line:
            continue

        protected_line = re.sub(r"(?<=\d)\.(?=\d)", "<DECIMAL>", cleaned_line)
        sentence_matches = re.findall(r"[^.!?]+[.!?](?:[\"']|$)?", protected_line)
        candidates = sentence_matches or [cleaned_line]

        for candidate in candidates:
            line = clean_text(candidate.replace("<DECIMAL>", "."))
            if line.lower().startswith("follow for more"):
                line = cta

            if line != cta and "follow" in line.lower():
                continue
            if line != cta and ("subscribe" in line.lower() or "subscriber" in line.lower()):
                continue
            excluded_fragments = [
                str(fragment).lower()
                for fragment in config.get("excluded_script_fragments", [])
            ]
            if line != cta and any(fragment in line.lower() for fragment in excluded_fragments):
                continue
            if line != cta and not is_valid_script_line(line, max_words):
                continue

            lines.append(line)

    content = [line for line in lines if line != cta]
    content = remove_duplicates(content)
    content = content[: max_lines - 1]
    content.append(cta)

    if len(content) < min_lines:
        raise ValueError("Not enough valid script lines")

    word_count = sum(len(line.split()) for line in content)
    target_min_words = int(config.get("target_min_words", 0))
    target_max_words = int(config.get("target_max_words", 0))
    if target_min_words and word_count < target_min_words:
        raise ValueError(f"Script is too short: {word_count} words")
    if target_max_words and word_count > target_max_words:
        raise ValueError(f"Script is too long: {word_count} words")

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
    target_min_words = int(config.get("target_min_words", 0))

    candidates: list[str] = []
    candidates.extend(build_fallback_candidates(knowledge))
    if target_min_words:
        candidates.extend(structured_knowledge_sentences(knowledge))
        candidates.extend(source_material_sentences(knowledge))

    lines: list[str] = []
    for candidate in candidates:
        line = clean_text(candidate)
        line = re.sub(r"\s+\|\s+[^|]+$", "", line).strip()
        if is_source_promotion(line, config, knowledge):
            continue
        if len(line.split()) > max_words:
            line = ""
        elif line and not line.endswith((".", "?", "!")):
            line += "."
        if line and line not in lines and is_valid_script_line(line, max_words):
            lines.append(line)
        current_words = sum(len(item.split()) for item in lines) + len(cta.split())
        if target_min_words and current_words >= target_min_words:
            break
        if len(lines) >= max_lines - 1:
            break

    # Some source sentences may exceed the per-line cap. Use concise, extractive
    # versions only when intact sentences were not enough to meet long-form length.
    if target_min_words and sum(len(item.split()) for item in lines) + len(cta.split()) < target_min_words:
        for candidate in source_material_sentences(knowledge):
            if len(lines) >= max_lines - 1:
                break
            if is_source_promotion(candidate, config, knowledge):
                continue
            line = summarize_to_line(candidate, max_words)
            if line and line not in lines and is_valid_script_line(line, max_words):
                lines.append(line)
            current_words = sum(len(item.split()) for item in lines) + len(cta.split())
            if current_words >= target_min_words or len(lines) >= max_lines - 1:
                break

    if not lines:
        lines = ["A verified update is now developing."]

    lines = lines[: max_lines - 1]
    lines.append(cta)
    return "\n".join(lines)


def build_fallback_candidates(knowledge: dict[str, Any]) -> list[str]:
    """Return only verified fact text for deterministic fallback."""
    return fact_lines(knowledge)


def source_material_sentences(knowledge: dict[str, Any]) -> list[str]:
    """Extract complete sentences from already-verified source material."""
    article_text = repair_extracted_text(clean_text(str(knowledge.get("article_text", ""))))
    if not article_text:
        return []

    # Some article extractors append comment widgets and related-story cards.
    # They are not part of the verified report and must not enter narration.
    article_text = re.split(
        r"\bPer\s+\d+\s+established\s+Helpful\s+marks\b",
        article_text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DECIMAL>", article_text)
    matches = re.findall(r"[^.!?]+[.!?](?:[\"']|$)?", protected)
    return [clean_text(match.replace("<DECIMAL>", ".")) for match in matches]


def structured_knowledge_sentences(knowledge: dict[str, Any]) -> list[str]:
    """Turn research claims and approved angles into attributed narration lines."""
    sentences: list[str] = []
    for item in knowledge.get("claims", []):
        if not isinstance(item, dict):
            continue
        claim = repair_extracted_text(clean_text(str(item.get("claim", ""))))
        if claim:
            sentences.append(f"The available reporting says {claim[0].lower() + claim[1:]}")

    for angle in knowledge.get("script_angles", []):
        cleaned = repair_extracted_text(clean_text(str(angle)))
        if cleaned:
            sentences.append(cleaned)
    return sentences


def repair_extracted_text(text: str) -> str:
    """Repair recurring word splits introduced by the article text extractor."""
    repairs = {
        r"\bcus\s+to\s+mers\b": "customers",
        r"\bhis\s+to\s+ry\b": "history",
        r"\bs\s+to\s+ry\b": "story",
        r"\boc\s+to\s+ber\b": "October",
    }
    for pattern, replacement in repairs.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def is_source_promotion(
    line: str,
    config: dict[str, Any],
    knowledge: dict[str, Any],
) -> bool:
    """Keep subscriptions, giveaways, and source calls-to-action out of fallbacks."""
    lowered = line.lower()
    blocked = [
        "subscribe",
        "follow for",
        "giveaway",
        "giving away",
        "one entry per person",
        "full copy of",
        "site action",
        "enter with your email",
        "join in",
        "are you the kind of player",
        "captures players",
        "visit our",
        "click the link",
        "read the full",
        "stay tuned",
    ]
    blocked.extend(str(item).lower() for item in config.get("excluded_script_fragments", []))
    blocked.extend(str(item).lower() for item in knowledge.get("avoid", []))
    return any(fragment and fragment in lowered for fragment in blocked)


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

    last_error = ""
    for attempt in range(int(config.get("max_generation_attempts", 3))):
        raw = call_llm(prompt, config)
        try:
            return clean_script(raw, config, knowledge)
        except ValueError as error:
            last_error = str(error)
            prompt = (
                build_prompt(knowledge, config)
                + "\n\nYour previous response was rejected: "
                + last_error
                + ". Correct the length and formatting while using only the verified material."
            )
            print(
                f"Script generation attempt {attempt + 1} rejected: {last_error}",
                flush=True,
            )
            continue

    fallback = fallback_script(knowledge, config)
    target_min_words = int(config.get("target_min_words", 0))
    if target_min_words and len(fallback.split()) < target_min_words:
        raise ValueError(
            "Could not generate a fact-grounded long-form script of at least "
            f"{target_min_words} words. Last LLM rejection: {last_error or 'unknown'}."
        )
    return fallback


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
