import os
import random
from utils import search_and_download_video

TOPIC_QUERIES = {
    "money": [
        "money counting",
        "cash bills",
        "financial success",
        "luxury lifestyle",
        "business finance",
    ],
    "wealth": [
        "luxury house",
        "luxury car",
        "rich lifestyle",
        "investing",
        "financial freedom",
    ],
    "business": [
        "business meeting",
        "office work",
        "entrepreneur laptop",
        "startup team",
        "corporate building",
    ],
    "entrepreneurship": [
        "startup founder",
        "working on laptop",
        "small business owner",
        "business planning",
        "entrepreneur office",
    ],
    "psychology": [
        "thinking person",
        "brain animation",
        "mindset concept",
        "person reflecting",
        "mental health",
    ],
    "dopamine": [
        "phone addiction",
        "social media scrolling",
        "person using phone",
        "digital distraction",
        "screen addiction",
    ],
    "focus": [
        "deep work",
        "studying alone",
        "focused work",
        "desk productivity",
        "concentration",
    ],
    "self improvement": [
        "morning routine",
        "journaling",
        "reading book",
        "personal growth",
        "gym training",
    ],
    "discipline": [
        "early morning workout",
        "runner training",
        "gym discipline",
        "hard work",
        "focused athlete",
    ],
    "productivity": [
        "desk setup",
        "typing laptop",
        "planning schedule",
        "notebook productivity",
        "work routine",
    ],
    "confidence": [
        "confident walking",
        "public speaking",
        "successful person",
        "leader speaking",
        "self confidence",
    ],
    "mindset": [
        "thinking alone",
        "mountain view",
        "person reflecting",
        "growth mindset",
        "calm focus",
    ],
    "sales": [
        "sales meeting",
        "business handshake",
        "client meeting",
        "presentation",
        "closing deal",
    ],
    "marketing": [
        "social media marketing",
        "content creation",
        "digital marketing",
        "analytics dashboard",
        "creative team",
    ],
}


def safe_name(text):
    return text.replace(" ", "_").lower()


for topic, queries in TOPIC_QUERIES.items():
    folder = f"backgrounds/{safe_name(topic)}"
    os.makedirs(folder, exist_ok=True)

    print(f"\nDownloading videos for: {topic}")

    for i, query in enumerate(queries):
        try:
            video_path = search_and_download_video(query)

            new_path = f"{folder}/{safe_name(topic)}_{i + 1}.mp4"

            if os.path.exists(video_path):
                if os.path.exists(new_path):
                    os.remove(new_path)

                os.rename(video_path, new_path)
                print("Saved:", new_path, "from query:", query)

        except Exception as error:
            print("Failed:", topic, query, error)

print("\nBackground download completed.")