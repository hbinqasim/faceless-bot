"""Download background music matched to the current video."""

from __future__ import annotations

import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from services.llm.service import generate as generate_text
from vice_studio.config_loader import load_component_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
JAMENDO_TRACKS_URL = "https://api.jamendo.com/v3.0/tracks"


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_config() -> dict[str, Any]:
    return load_component_config(CONFIG_PATH)


def read_text_file(path_value: str) -> str:
    path = resolve_path(path_value)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def read_json_file(path_value: str) -> dict[str, Any]:
    path = resolve_path(path_value)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_music_query(script: str, knowledge: dict[str, Any], config: dict[str, Any]) -> str:
    title = str(knowledge.get("title", "")).strip()
    summary = str(knowledge.get("summary", "")).strip()

    prompt = f"""
You are selecting background music for a short vertical video.

Return ONLY 3 to 5 music search keywords.
No commas if unnecessary.
No explanations.
No artist names.
No copyrighted song names.
Prefer mood, tempo, and genre words.

Video title:
{title}

Video summary:
{summary}

Voiceover script:
{script}

Music search keywords:
""".strip()

    try:
        raw = generate_text(prompt, config)
    except Exception:
        raw = ""

    query = clean_query(raw)
    return query or fallback_query(script, knowledge)


def clean_query(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9\s-]", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    words = [word for word in text.split() if len(word) > 2]
    return " ".join(words[:6]).strip()


def fallback_query(script: str, knowledge: dict[str, Any]) -> str:
    text = f"{knowledge.get('title', '')} {knowledge.get('summary', '')} {script}".lower()

    mood_terms = [
        "cinematic",
        "suspense",
        "trailer",
        "dark",
        "dramatic",
        "technology",
        "news",
        "ambient",
        "energetic",
    ]

    selected = [term for term in mood_terms if term in text]
    if selected:
        return " ".join(selected[:4])

    return "cinematic suspense trailer"


def search_jamendo_music(query: str, config: dict[str, Any]) -> dict[str, Any]:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    client_id = os.getenv("JAMENDO_CLIENT_ID")

    if not client_id:
        raise RuntimeError("JAMENDO_CLIENT_ID is missing in .env")

    fallback_queries = [
        str(item).strip()
        for item in config.get(
            "fallback_queries",
            ["cinematic suspense", "gaming electronic", "dramatic ambient"],
        )
        if str(item).strip()
    ]

    for active_query in dict.fromkeys([query, *fallback_queries]):
        params = {
            "client_id": client_id,
            "format": "json",
            "limit": int(config.get("per_page", 10)),
            "search": active_query,
            "include": "musicinfo",
            "audioformat": "mp32",
            "order": "relevance",
        }
        response = requests.get(
            JAMENDO_TRACKS_URL,
            params=params,
            timeout=int(config.get("timeout_seconds", 60)),
        )
        if not response.ok:
            raise RuntimeError(
                f"Jamendo music request failed: {response.status_code} {response.text[:500]}"
            )

        results = response.json().get("results", [])
        downloadable = [
            item
            for item in results
            if item.get("audiodownload_allowed") and item.get("audiodownload")
        ]
        playable = downloadable or [item for item in results if item.get("audio")]
        if playable:
            selected = random.SystemRandom().choice(playable)
            selected["_selected_query"] = active_query
            return selected

    raise RuntimeError(f"No playable Jamendo track found for query: {query}")


def download_track(hit: dict[str, Any], output_path: Path, config: dict[str, Any]) -> None:
    audio_url = (
        hit.get("audiodownload")
        or hit.get("audio")
        or hit.get("previewURL")
        or hit.get("preview_url")
        or hit.get("downloadURL")
        or hit.get("download_url")
    )

    if not audio_url:
        raise RuntimeError(f"Pixabay music hit has no audio URL: {hit}")

    max_attempts = max(1, int(config.get("download_max_attempts", 3)))
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                str(audio_url), timeout=int(config.get("timeout_seconds", 60))
            )
            if response.ok:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                return
            error = RuntimeError(
                f"Music download failed: {response.status_code} {response.text[:300]}"
            )
        except requests.RequestException as request_error:
            error = request_error

        if attempt < max_attempts:
            time.sleep(float(config.get("download_retry_backoff_seconds", 2)) * attempt)

    if output_path.exists() and config.get("reuse_existing_on_failure", True):
        print(f"Warning: new music download failed; reusing existing track: {error}")
        return
    raise RuntimeError(f"Music download failed after {max_attempts} attempts: {error}")


def save_manifest(payload: dict[str, Any], config: dict[str, Any]) -> Path:
    output_folder = resolve_path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)
    manifest_path = output_folder / "music_manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def run() -> dict[str, Any]:
    config = load_config()

    if not config.get("enabled", True):
        raise RuntimeError("Music service is disabled in config.json.")

    script = read_text_file(str(config["script_path"]))
    knowledge = read_json_file(str(config["knowledge_path"]))
    query = build_music_query(script, knowledge, config)
    output_path = resolve_path(config["output_audio_path"])
    hit: dict[str, Any] = {}
    status = "downloaded"
    failure_reason = ""

    try:
        hit = search_jamendo_music(query, config)
        query = str(hit.pop("_selected_query", query))
        download_track(hit, output_path, config)
    except (RuntimeError, requests.RequestException) as error:
        failure_reason = str(error)
        if output_path.exists() and config.get("reuse_existing_on_failure", True):
            status = "reused_existing"
            print(f"Warning: {failure_reason}; reusing existing music track.")
        elif config.get("allow_no_music_on_failure", False):
            status = "skipped"
            print(f"Warning: {failure_reason}; continuing without background music.")
        else:
            raise

    manifest = {
        "service_name": config.get("service_name"),
        "channel": config.get("channel"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "query": query,
        "status": status,
        "failure_reason": failure_reason or None,
        "output_audio_path": str(output_path) if output_path.exists() else None,
        "music_hit": {
            "id": hit.get("id"),
            "name": hit.get("name") or hit.get("title"),
            "tags": hit.get("tags"),
            "duration": hit.get("duration"),
            "user": hit.get("user"),
            "shareurl": hit.get("shareurl"),
        },
    }

    manifest_path = save_manifest(manifest, config)

    print(f"Music query: {query}")
    print(f"Music status: {status}")
    print(f"Music path: {output_path if output_path.exists() else 'none'}")
    print(f"Manifest path: {manifest_path}")

    return {
        "query": query,
        "music_path": str(output_path) if output_path.exists() else None,
        "status": status,
        "manifest_path": str(manifest_path),
    }


if __name__ == "__main__":
    run()
