"""Simple timing utilities for Vice Studio engine work."""

from __future__ import annotations

import time


def start_timer() -> float:
    """Start a high-resolution timer."""
    return time.perf_counter()


def stop_timer(start_time: float) -> float:
    """Return elapsed seconds since start_time."""
    return time.perf_counter() - start_time
