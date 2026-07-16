import os
import pickle
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "youtube_token.pickle"

# YouTube requires scheduled videos to be private first
PRIVACY_STATUS = "private"

# Space uploads automatically
FIRST_VIDEO_DELAY_MINUTES = 30
HOURS_BETWEEN_VIDEOS = 10


def get_publish_time(video_number):
    publish_time = datetime.now(timezone.utc) + timedelta(
        minutes=FIRST_VIDEO_DELAY_MINUTES,
        hours=video_number * HOURS_BETWEEN_VIDEOS,
    )

    return publish_time.isoformat()


def get_youtube_service():
    credentials = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE,
                SCOPES,
            )
            credentials = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(credentials, token)

    return build("youtube", "v3", credentials=credentials)


def get_latest_unuploaded_video():
    conn = sqlite3.connect("content.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, description, hashtags, file_path
        FROM videos
        WHERE uploaded = 0 OR uploaded IS NULL
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise Exception("No unuploaded videos found.")

    video_id, title, description, hashtags, file_path = row

    if not os.path.exists(file_path):
        raise Exception(f"Video file not found: {file_path}")

    full_description = f"{description}\n\n{hashtags}\n\n#Shorts"

    return video_id, title, full_description, file_path


def mark_uploaded(video_id, youtube_id, publish_time):
    conn = sqlite3.connect("content.db")
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE videos ADD COLUMN publish_time TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        UPDATE videos
        SET uploaded = 1,
            youtube_id = ?,
            publish_time = ?
        WHERE id = ?
    """, (youtube_id, publish_time, video_id))

    conn.commit()
    conn.close()


def upload_video(video_number=0):
    youtube = get_youtube_service()

    video_id, title, description, file_path = get_latest_unuploaded_video()
    publish_time = get_publish_time(video_number)

    print("Uploading video ID:", video_id)
    print("Title:", title)
    print("File:", file_path)
    print("Scheduled publish time:", publish_time)

    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [
                "shorts",
                "motivation",
                "mindset",
                "success",
                "self improvement",
            ],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
            "publishAt": publish_time,
        },
    }

    media = MediaFileUpload(
        file_path,
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    response = None
    retries = 0
    max_retries = 5

    while response is None:
        try:
            status, response = request.next_chunk()

            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")

        except (BrokenPipeError, ConnectionResetError, TimeoutError) as error:
            retries += 1

            if retries > max_retries:
                raise error

            wait_time = retries * 10
            print(f"Upload connection failed. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    youtube_id = response["id"]

    print("Upload complete.")
    print("YouTube video ID:", youtube_id)

    mark_uploaded(video_id, youtube_id, publish_time)
    print("Marked video as uploaded and scheduled.")


if __name__ == "__main__":
    video_number = 0

    if len(sys.argv) > 1:
        video_number = int(sys.argv[1])

    upload_video(video_number)