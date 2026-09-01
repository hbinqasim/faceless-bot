"""YouTube Upload Agent for Vice Studio."""

from __future__ import annotations

import datetime as dt
import json
import sys
from datetime import datetime, timedelta, timezone
import pickle
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from vice_studio.config_loader import load_component_config


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]


def load_config() -> dict[str, Any]:
    return load_component_config(CONFIG_PATH)


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT_DIR / path


def get_publish_time(config: dict, video_number: int) -> str | None:
    if not config.get("schedule_upload", False):
        return None

    first_delay = int(config.get("first_video_delay_minutes", 30))
    spacing = int(config.get("hours_between_videos", 10))

    publish_time = datetime.now(timezone.utc) + timedelta(
        minutes=first_delay,
        hours=video_number * spacing,
    )

    return publish_time.isoformat().replace("+00:00", "Z")


def get_youtube_service(config: dict[str, Any]):
    token_path = resolve_path(str(config["token_file"]))
    client_secret_path = resolve_path(str(config["client_secret_file"]))

    credentials = None

    if token_path.exists():
        with token_path.open("rb") as file:
            credentials = pickle.load(file)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                print(
                    "Stored YouTube authorization is no longer valid; "
                    "starting browser reauthorization.",
                    flush=True,
                )
                credentials = authorize_with_browser(client_secret_path)
        else:
            credentials = authorize_with_browser(client_secret_path)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        with token_path.open("wb") as file:
            pickle.dump(credentials, file)

    return build("youtube", "v3", credentials=credentials)


def authorize_with_browser(client_secret_path: Path, scopes: list[str] | None = None):
    """Obtain fresh user authorization after a missing or revoked token."""
    if not client_secret_path.exists():
        raise FileNotFoundError(
            f"YouTube OAuth client secret not found: {client_secret_path}"
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_path),
        scopes or SCOPES,
    )
    return flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )


def load_metadata(config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_path(str(config["metadata_path"]))
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Metadata must be a JSON object.")

    return data


def build_description(metadata: dict[str, Any]) -> str:
    description = str(metadata.get("description", "")).strip()
    hashtags = metadata.get("hashtags", [])

    if isinstance(hashtags, list):
        hashtag_text = " ".join(str(tag).strip() for tag in hashtags if str(tag).strip())
        if hashtag_text and hashtag_text not in description:
            description = f"{description}\n\n{hashtag_text}"

    if config_add_shorts_hashtag(metadata) and "#Shorts" not in description and "#shorts" not in description:
        description = f"{description}\n\n#Shorts"

    return description.strip()


def config_add_shorts_hashtag(metadata: dict[str, Any]) -> bool:
    """Keep legacy Shorts behavior unless metadata explicitly marks long-form."""
    return str(metadata.get("video_format", "short-form")).lower() != "long-form"


def build_publish_time(config: dict[str, Any]) -> str | None:
    if not config.get("schedule_upload", False):
        return None

    delay = int(config.get("first_video_delay_minutes", 30))
    publish_time = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=delay)
    return publish_time.isoformat()


def upload_video(youtube, config: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    video_path = resolve_path(str(config["video_path"]))

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    title = str(metadata.get("title", "Untitled Vice Studio Video")).strip()[:100]
    description = build_description(metadata)

    tags = metadata.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    publish_time = build_publish_time(config)

    status = {
        "privacyStatus": str(config.get("privacy_status", "private")),
        "selfDeclaredMadeForKids": bool(config.get("made_for_kids", False)),
    }

    if publish_time:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_time

    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [str(tag) for tag in tags][:50],
            "categoryId": str(config.get("category_id", "20")),
            "defaultLanguage": str(metadata.get("language", "en")),
        },
        "status": status,
    }

    media = MediaFileUpload(
        str(video_path),
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

    while response is None:
        status_progress, response = request.next_chunk()
        if status_progress:
            print(f"Uploaded {int(status_progress.progress() * 100)}%")

    return {
        "video_id": response["id"],
        "title": title,
        "publish_time": publish_time,
        "video_path": str(video_path),
    }


def set_thumbnail(youtube, config: dict[str, Any], video_id: str) -> str | None:
    thumbnail_path = resolve_path(str(config["thumbnail_path"]))

    if not thumbnail_path.exists():
        print(f"Thumbnail not found, skipping: {thumbnail_path}")
        return None

    media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")

    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()

    return str(thumbnail_path)


def save_manifest(config: dict[str, Any], result: dict[str, Any]) -> Path:
    manifest_path = resolve_path(str(config["upload_manifest_path"]))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "agent_name": config.get("agent_name"),
        "channel": config.get("channel"),
        "status": "uploaded",
        "uploaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "video_id": result["video_id"],
        "youtube_url": f"https://youtu.be/{result['video_id']}",
        "title": result["title"],
        "publish_time": result.get("publish_time"),
        "video_path": result.get("video_path"),
        "thumbnail_path": result.get("thumbnail_path"),
        "privacy_status": config.get("privacy_status"),
    }

    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return manifest_path


def run(video_number: int = 0) -> None:
    config = load_config()

    if not config.get("enabled", True):
        print("Upload agent disabled.")
        return

    metadata = load_metadata(config)
    youtube = get_youtube_service(config)

    result = upload_video(youtube, config, metadata)
    thumbnail_path = set_thumbnail(youtube, config, result["video_id"])
    result["thumbnail_path"] = thumbnail_path

    manifest_path = save_manifest(config, result)

    print("Upload complete.")
    print("YouTube URL:", f"https://youtu.be/{result['video_id']}")
    print("Manifest:", manifest_path)


if __name__ == "__main__":
    video_number = 0
    if len(sys.argv) > 1:
        video_number = int(sys.argv[1])
    run(video_number)
