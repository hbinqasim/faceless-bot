"""Generic LLM service for Vice Studio.

All agents should call this service instead of calling Gemini, Groq,
OpenRouter, or Ollama directly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")


class LLMError(RuntimeError):
    pass


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def generate(prompt: str, config: dict[str, Any] | None = None) -> str:
    active_config = resolve_generation_config(config)

    if not active_config.get("enabled", True):
        raise LLMError("LLM service is disabled.")

    errors: list[str] = []

    for provider_name in active_config.get("provider_order", []):
        provider_config = active_config.get(provider_name, {})

        if not provider_config.get("enabled", False):
            continue

        try:
            if provider_name == "gemini":
                return generate_gemini(prompt, active_config, provider_config)

            if provider_name == "groq":
                return generate_openai_compatible(
                    prompt,
                    active_config,
                    provider_config,
                    api_key_env="GROQ_API_KEY",
                    endpoint="https://api.groq.com/openai/v1/chat/completions",
                )

            if provider_name == "openrouter":
                return generate_openai_compatible(
                    prompt,
                    active_config,
                    provider_config,
                    api_key_env="OPENROUTER_API_KEY",
                    endpoint="https://openrouter.ai/api/v1/chat/completions",
                )

            if provider_name == "ollama":
                return generate_ollama(prompt, active_config, provider_config)

            errors.append(f"{provider_name}: unsupported provider")

        except Exception as error:
            errors.append(f"{provider_name}: {error}")

    raise LLMError("All LLM providers failed:\n" + "\n".join(errors))


def resolve_generation_config(overrides: dict[str, Any] | None) -> dict[str, Any]:
    """Merge lightweight agent settings into the shared provider configuration."""
    if not overrides:
        return load_config()
    if overrides.get("provider_order"):
        return overrides

    config = load_config()
    for key in ("enabled", "temperature", "max_tokens", "timeout_seconds"):
        if key in overrides:
            config[key] = overrides[key]

    preferred = str(overrides.get("llm_provider", "")).strip().lower()
    if preferred and preferred in config.get("provider_order", []):
        config["provider_order"] = [
            preferred,
            *[name for name in config["provider_order"] if name != preferred],
        ]

    model = str(overrides.get("model", "")).strip()
    if model and preferred and isinstance(config.get(preferred), dict):
        config[preferred] = {**config[preferred], "model": model}

    return config


def generate_gemini(
    prompt: str,
    global_config: dict[str, Any],
    provider_config: dict[str, Any],
) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise LLMError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")

    model = provider_config.get("model", "gemini-2.5-flash")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": float(global_config.get("temperature", 0.4)),
            "maxOutputTokens": int(global_config.get("max_tokens", 500)),
        },
    }

    response = requests.post(
        endpoint,
        json=payload,
        timeout=float(global_config.get("timeout_seconds", 60)),
    )

    if not response.ok:
        raise LLMError(f"Gemini failed {response.status_code}: {response.text[:500]}")

    data = response.json()
    candidates = data.get("candidates", [])

    if not candidates:
        raise LLMError(f"Gemini returned no candidates: {data}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts).strip()

    if not text:
        raise LLMError("Gemini returned empty text")

    return text


def generate_openai_compatible(
    prompt: str,
    global_config: dict[str, Any],
    provider_config: dict[str, Any],
    api_key_env: str,
    endpoint: str,
) -> str:
    api_key = os.getenv(api_key_env)

    if not api_key:
        raise LLMError(f"Missing {api_key_env}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": provider_config["model"],
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": float(global_config.get("temperature", 0.4)),
        "max_tokens": int(global_config.get("max_tokens", 500)),
    }

    response = requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=float(global_config.get("timeout_seconds", 60)),
    )

    if not response.ok:
        raise LLMError(f"{endpoint} failed {response.status_code}: {response.text[:500]}")

    data = response.json()
    choices = data.get("choices", [])

    if not choices:
        raise LLMError(f"OpenAI-compatible provider returned no choices: {data}")

    text = choices[0].get("message", {}).get("content", "").strip()

    if not text:
        raise LLMError("OpenAI-compatible provider returned empty text")

    return text


def generate_ollama(
    prompt: str,
    global_config: dict[str, Any],
    provider_config: dict[str, Any],
) -> str:
    base_url = str(provider_config.get("base_url", "http://localhost:11434")).rstrip("/")
    model = str(provider_config.get("model", "llama3.1:8b"))

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": float(global_config.get("temperature", 0.4)),
            "num_predict": int(global_config.get("max_tokens", 500)),
        },
    }

    response = requests.post(
        f"{base_url}/api/generate",
        json=payload,
        timeout=float(global_config.get("timeout_seconds", 60)),
    )

    if not response.ok:
        raise LLMError(f"Ollama failed {response.status_code}: {response.text[:500]}")

    data = response.json()
    text = str(data.get("response", "")).strip()

    if not text:
        raise LLMError("Ollama returned empty text")

    return text


if __name__ == "__main__":
    print(generate("Write one short sentence about AI video automation."))
