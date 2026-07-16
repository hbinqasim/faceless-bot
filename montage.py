from moviepy import (
    VideoFileClip,
    concatenate_videoclips,
)
import random
import os


def create_montage(duration):
    folder = "backgrounds"

    videos = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith(".mp4")
    ]

    random.shuffle(videos)

    clips = []
    current_duration = 0

    for path in videos:

        clip = VideoFileClip(path)

        clip_length = min(3, clip.duration)

        clip = clip.subclipped(0, clip_length)

        clips.append(clip)

        current_duration += clip.duration

        if current_duration >= duration:
            break

    final = concatenate_videoclips(
        clips,
        method="compose"
    )

    return final.subclipped(
        0,
        min(duration, final.duration)
    )
