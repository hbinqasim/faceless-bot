import sqlite3
from datetime import datetime


def setup_database():
    conn = sqlite3.connect("content.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            script TEXT,
            title TEXT,
            description TEXT,
            hashtags TEXT,
            file_path TEXT,
            created_at TEXT
        )
    """)

    # Add new columns if they don't exist
    try:
        cursor.execute(
            "ALTER TABLE videos ADD COLUMN uploaded INTEGER DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE videos ADD COLUMN youtube_id TEXT"
        )
    except sqlite3.OperationalError:
        pass

    # Old migration support
    for column in ["title", "description", "hashtags"]:
        try:
            cursor.execute(
                f"ALTER TABLE videos ADD COLUMN {column} TEXT"
            )
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def save_video(topic, script, title, description, hashtags, file_path):
    conn = sqlite3.connect("content.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO videos (
            topic,
            script,
            title,
            description,
            hashtags,
            file_path,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        topic,
        script,
        title,
        description,
        hashtags,
        file_path,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()