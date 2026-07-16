import os
import random


def get_music_for_topic(topic):
    topic = topic.replace(" ", "_").lower()

    folder = f"music/{topic}"

    if not os.path.exists(folder):
        return None

    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith((".mp3", ".wav", ".m4a"))
    ]

    if not files:
        return None

    return random.choice(files)
