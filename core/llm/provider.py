"""Generic LLM provider layer for Vice Studio."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_text(prompt: str, config: dict[str, Any]) -> str:
    """Generate text using the configured provider."""
    provider = str(config.get("llm_provider", config.get("provider", "ollama"))).lower()

    if provider == "gemini":
        return generate_with_gemini(prompt, config)

    if provider == "ollama":
        return generate_with_ollama(prompt, config)

    raise ValueError(f"Unsupported LLM provider: {provider}")


def generate_with_gemini(prompt: str, config: dict[str, Any]) -> str:
    """Generate text with Google Gemini."""
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

    from google import genai

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is missing in .env")

    client = genai.Client(api_key=api_key)

    model = str(config.get("model", "gemini-2.5-flash")).strip()

    print("LLM provider: gemini")
    print(f"LLM model: {model}")
    print(f"Gemini key prefix: {api_key[:8]}")

    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )

    return str(getattr(response, "text", "") or "").strip()


def generate_with_ollama(prompt: str, config: dict[str, Any]) -> str:
    """Generate text with local Ollama."""
    payload = {
        "model": config.get("model", "llama3.1:8b"),
        "temperature": float(config.get("temperature", 0.25)),
        "max_tokens": int(config.get("max_tokens", 700)),
        "prompt": prompt,
        "stream": False,
    }

    response = requests.post(str(config.get("ollama_url", OLLAMA_URL)), json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()
    return str(data.get("response", "")).strip()
