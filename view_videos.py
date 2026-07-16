import sqlite3

conn = sqlite3.connect("content.db")
cursor = conn.cursor()

cursor.execute("""
SELECT id, topic, title, hashtags, file_path, created_at
FROM videos
ORDER BY id DESC
""")

videos = cursor.fetchall()

for video in videos:
    print("-" * 40)
    print("ID:", video[0])
    print("Topic:", video[1])
    print("Title:", video[2])
    print("Hashtags:", video[3])
    print("File:", video[4])
    print("Created:", video[5])

conn.close()
