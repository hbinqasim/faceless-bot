import sqlite3
import os

os.makedirs("metadata", exist_ok=True)

conn = sqlite3.connect("content.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT id, topic, title, description, hashtags, file_path, created_at
    FROM videos
    ORDER BY id DESC
""")

rows = cursor.fetchall()
conn.close()

for row in rows:
    video_id, topic, title, description, hashtags, file_path, created_at = row

    filename = f"metadata/video_{video_id}.txt"

    with open(filename, "w") as file:
        file.write(f"VIDEO ID: {video_id}\n")
        file.write(f"TOPIC: {topic}\n")
        file.write(f"TITLE: {title}\n\n")
        file.write(f"DESCRIPTION:\n{description}\n\n")
        file.write(f"HASHTAGS:\n{hashtags}\n\n")
        file.write(f"FILE:\n{file_path}\n\n")
        file.write(f"CREATED:\n{created_at}\n")

print("Metadata exported successfully.")
