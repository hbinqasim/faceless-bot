import os
import shutil
from moviepy import VideoFileClip

from utils import search_and_download_video
from visual_keywords import extract_visual_queries


TEMP_FOLDER = "temp_backgrounds"
MAX_CLIPS = 5


def safe_name(text):
    return text.replace(" ", "_").lower()


def clean_temp_folder():
    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER)

    os.makedirs(TEMP_FOLDER, exist_ok=True)


def get_video_size(video_path):
    try:
        clip = VideoFileClip(video_path)
        width = clip.w
        height = clip.h
        duration = clip.duration
        clip.close()

        return width, height, duration

    except Exception:
        return None, None, None


def is_duplicate(video_path, downloaded_files):
    new_size = os.path.getsize(video_path)

    for old_path in downloaded_files:
        if not os.path.exists(old_path):
            continue

        old_size = os.path.getsize(old_path)

        if abs(new_size - old_size) < 5000:
            return True

    return False


def try_download(query, downloaded_files, clip_number):
    video_path = search_and_download_video(query)

    if not os.path.exists(video_path):
        return None

    width, height, duration = get_video_size(video_path)

    if not width or not height or not duration:
        os.remove(video_path)
        return None

    if duration < 2:
        print("Rejected too-short video:", video_path)
        os.remove(video_path)
        return None

    if is_duplicate(video_path, downloaded_files):
        print("Rejected duplicate video:", video_path)
        os.remove(video_path)
        return None

    new_path = os.path.join(
        TEMP_FOLDER,
        f"clip_{clip_number}.mp4"
    )

    if os.path.exists(new_path):
        os.remove(new_path)

    os.rename(video_path, new_path)

    if height > width:
        print("Saved vertical background:", new_path)
    else:
        print("Saved horizontal backup background:", new_path)

    return new_path


def download_fresh_backgrounds(topic, script):
    clean_temp_folder()

    base_queries = extract_visual_queries(topic, script, max_queries=8)

    search_queries = []

    for query in base_queries:
        search_queries.append(f"vertical video {query}")
        search_queries.append(f"portrait video {query}")
        search_queries.append(f"{query}")
        search_queries.append(f"stock footage {query}")
        search_queries.append(f"4k {query}")

    fallback_queries = [
        "vertical video motivation",
        "portrait video success",
        "business stock footage",
        "people working stock footage",
        "personal growth stock footage",
        "gym motivation stock footage",
        "city lifestyle stock footage",
    ]

    search_queries.extend(fallback_queries)

    downloaded_files = []

    print("Searching backgrounds...")

    for query in search_queries:
        if len(downloaded_files) >= MAX_CLIPS:
            break

        try:
            print("Trying:", query)

            new_file = try_download(
                query,
                downloaded_files,
                len(downloaded_files) + 1
            )

            if new_file:
                downloaded_files.append(new_file)

        except Exception as error:
            print("Failed:", query)
            print("Reason:", error)

    if not downloaded_files:
        raise Exception("No usable background videos found.")

    print("Total usable backgrounds:", len(downloaded_files))

    return downloaded_files


def clear_temp_backgrounds():
    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER)