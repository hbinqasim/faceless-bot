"""File loading and saving helpers for Vice Studio resources."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError, ResourceNotFoundError


def load_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    resource_path = Path(path)
    if not resource_path.exists():
        raise ResourceNotFoundError(f"JSON resource not found: {resource_path}")

    try:
        with resource_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Invalid JSON in {resource_path}: {error}") from error

    if not isinstance(data, dict):
        raise ConfigurationError(f"Expected JSON object in {resource_path}")

    return data


def load_text(path: str | Path) -> str:
    """Load a UTF-8 text file from disk."""
    resource_path = Path(path)
    if not resource_path.exists():
        raise ResourceNotFoundError(f"Text resource not found: {resource_path}")

    return resource_path.read_text(encoding="utf-8")


def save_text(path: str | Path, content: str) -> Path:
    """Save UTF-8 text content and return the written path."""
    resource_path = Path(path)
    if resource_path.parent != Path("."):
        ensure_directory(resource_path.parent)

    resource_path.write_text(content, encoding="utf-8")
    return resource_path


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if needed and return its Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def timestamped_path(folder: str | Path, prefix: str, suffix: str) -> Path:
    """Build a timestamped path inside folder."""
    directory = ensure_directory(folder)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return directory / f"{prefix}_{timestamp}{normalized_suffix}"
