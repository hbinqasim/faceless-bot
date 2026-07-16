import os
import sqlite3
from moviepy import VideoFileClip

conn = sqlite3.connect("content.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT id, file_path, title, hashtags
    FROM videos
    ORDER BY id DESC
    LIMIT 10
""")

rows = cursor.fetchall()
conn.close()

for video_id, file_path, title, hashtags in rows:
    print("-" * 40)
    print("ID:", video_id)
    print("File:", file_path)

    if not os.path.exists(file_path):
        print("❌ Missing file")
        continue

    video = VideoFileClip(file_path)

    print("Duration:", round(video.duration, 2), "seconds")
    print("Size:", video.w, "x", video.h)
    print("Title:", title)
    print("Hashtags:", hashtags)

    if video.w != 1080 or video.h != 1920:
        print("❌ Not vertical 1080x1920")
    elif video.duration < 8:
        print("⚠️ Too short")
    elif video.duration > 60:
        print("⚠️ Too long for Shorts")
    else:
        print("✅ Looks good")

    video.close()
