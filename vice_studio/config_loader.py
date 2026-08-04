"""Shared component config loading with optional isolated profile overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_OVERRIDE_ENV = "VICE_STUDIO_CONFIG_PATH"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_component_config(default_path: str | Path) -> dict[str, Any]:
    """Load a component config, honoring an explicit per-process override."""
    override = os.getenv(CONFIG_OVERRIDE_ENV, "").strip()
    path = Path(override) if override else Path(default_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return _load_config(path.resolve(), set())


def _load_config(path: Path, loading: set[Path]) -> dict[str, Any]:
    if path in loading:
        raise ValueError(f"Circular config inheritance detected at: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Component config not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Component config must be a JSON object: {path}")

    parent_value = data.pop("extends", None)
    if not parent_value:
        return data

    parent_path = Path(str(parent_value))
    if not parent_path.is_absolute():
        parent_path = (path.parent / parent_path).resolve()

    parent = _load_config(parent_path, loading | {path})
    return _deep_merge(parent, data)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
