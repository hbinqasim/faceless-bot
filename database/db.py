"""SQLite database helpers for the Vice Studio platform."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

try:
    from database.schema import CREATE_TABLES
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from schema import CREATE_TABLES

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "vice.db"


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    try:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as exc:
        raise RuntimeError(f"Unable to open database connection: {exc}") from exc


def initialize_database() -> None:
    """Create the database file and all required tables."""
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        connection = get_connection()
        try:
            for statement in CREATE_TABLES:
                connection.execute(statement)
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Database initialization failed: {exc}") from exc


def insert_source(name: str, url: Optional[str], source_type: Optional[str]) -> int:
    """Insert a source record and return its row id."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO sources (name, url, source_type) VALUES (?, ?, ?)",
            (name, url, source_type),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        connection.rollback()
        raise RuntimeError(f"Failed to insert source: {exc}") from exc
    finally:
        connection.close()


def insert_article(
    source_id: int,
    title: str,
    url: Optional[str],
    published_at: Optional[str],
    raw_text: Optional[str],
) -> int:
    """Insert an article record and return its row id."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO articles (source_id, title, url, published_at, raw_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_id, title, url, published_at, raw_text),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        connection.rollback()
        raise RuntimeError(f"Failed to insert article: {exc}") from exc
    finally:
        connection.close()


def insert_fact(article_id: int, fact_text: str, confidence: float, category: Optional[str]) -> int:
    """Insert a fact record and return its row id."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO facts (article_id, fact_text, confidence, category)
            VALUES (?, ?, ?, ?)
            """,
            (article_id, fact_text, confidence, category),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        connection.rollback()
        raise RuntimeError(f"Failed to insert fact: {exc}") from exc
    finally:
        connection.close()


def insert_topic(name: str, channel: Optional[str]) -> int:
    """Insert a topic record and return its row id."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO topics (name, channel) VALUES (?, ?)",
            (name, channel),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        connection.rollback()
        raise RuntimeError(f"Failed to insert topic: {exc}") from exc
    finally:
        connection.close()


def list_tables() -> list[str]:
    """Return the names of all tables in the database."""
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [row["name"] for row in rows]
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to list tables: {exc}") from exc
    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()
    print(list_tables())
