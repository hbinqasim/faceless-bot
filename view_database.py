import sqlite3

conn = sqlite3.connect("content.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT id, topic, title, hashtags, file_path, created_at
    FROM videos
    ORDER BY id DESC
""")

rows = cursor.fetchall()

for row in rows:
    print("ID:", row[0])
    print("Topic:", row[1])
    print("Title:", row[2])
    print("Hashtags:", row[3])
    print("File:", row[4])
    print("Created:", row[5])
    print("-" * 40)

conn.close()
