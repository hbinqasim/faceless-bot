import os
import sqlite3
import subprocess

conn = sqlite3.connect("content.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT id, file_path
    FROM videos
    ORDER BY id DESC
    LIMIT 1
""")

row = cursor.fetchone()
conn.close()

if not row:
    print("No videos found.")
    exit()

video_id, file_path = row
metadata_path = f"metadata/video_{video_id}.txt"

if os.path.exists(file_path):
    subprocess.run(["open", file_path])

if os.path.exists(metadata_path):
    subprocess.run(["open", metadata_path])

print("Opened latest video and metadata.")
