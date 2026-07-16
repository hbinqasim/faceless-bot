import asyncio
import os
import subprocess
from datetime import datetime
import random

import edge_tts
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
    concatenate_audioclips,
)
from moviepy import vfx
from music_selector import get_music_for_topic
from database import setup_database, save_video
from script_generator import generate_script
from metadata_generator import generate_metadata
from utils import search_and_download_video
from word_captions import make_word_caption_clips
from fresh_backgrounds import download_fresh_backgrounds, clear_temp_backgrounds


WIDTH = 1080
HEIGHT = 1920
VOICE_FILE = "output/voice.mp3"
MUSIC_FOLDER = "music"
BACKGROUND_FOLDER = "backgrounds"
CLIP_LENGTH = 3

VOICES = [
    "en-US-GuyNeural",
    "en-US-ChristopherNeural",
    "en-US-EricNeural",
    "en-US-BrianNeural",
    "en-US-RogerNeural",
]


async def generate_voice(text):
    voice = random.choice(VOICES)
    print("Voice:", voice)

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(VOICE_FILE)


def get_random_music():
    if not os.path.exists(MUSIC_FOLDER):
        return None

    music_files = [
        os.path.join(MUSIC_FOLDER, file)
        for file in os.listdir(MUSIC_FOLDER)
        if file.lower().endswith((".mp3", ".wav", ".m4a"))
    ]

    if not music_files:
        return None

    return random.choice(music_files)


def loop_audio(audio, duration):
    clips = []

    while sum(c.duration for c in clips) < duration:
        remaining = duration - sum(c.duration for c in clips)

        if remaining >= audio.duration:
            clips.append(audio.subclipped(0, audio.duration))
        else:
            clips.append(audio.subclipped(0, remaining))

    return concatenate_audioclips(clips)


def make_vertical_background(video):
    video_ratio = video.w / video.h
    target_ratio = WIDTH / HEIGHT

    def slow_zoom(clip):
        return clip.resized(lambda t: 1 + 0.025 * t)

    # If already vertical
    if video_ratio <= target_ratio:
        bg = video.resized(width=WIDTH)

        bg = bg.cropped(
            x_center=bg.w / 2,
            y_center=bg.h / 2,
            width=WIDTH,
            height=HEIGHT,
        )

        bg = slow_zoom(bg)

        bg = bg.cropped(
            x_center=bg.w / 2,
            y_center=bg.h / 2,
            width=WIDTH,
            height=HEIGHT,
        )

        return bg

    # If horizontal
    background = video.resized(height=HEIGHT)

    background = background.cropped(
        x_center=background.w / 2,
        y_center=background.h / 2,
        width=WIDTH,
        height=HEIGHT,
    )

    background = slow_zoom(background)

    foreground = video.resized(width=WIDTH)

    if foreground.h > HEIGHT:
        foreground = foreground.resized(height=HEIGHT)

    foreground = foreground.with_position(
        lambda t: (
            "center",
            int((HEIGHT - foreground.h) / 2 + 18 * __import__("math").sin(t * 1.2))
        )
    )

    final = CompositeVideoClip(
        [
            background.with_opacity(0.55),
            foreground,
        ],
        size=(WIDTH, HEIGHT),
    )

    return final


def get_topic_background_files(topic, script):
    return download_fresh_backgrounds(topic, script)


def create_topic_montage(topic, duration, current_script):
    video_files = get_topic_background_files(topic, current_script)

    if not video_files:
        fallback_topics = TOPIC_FALLBACKS.get(topic.lower(), []) # type: ignore

        for fallback_topic in fallback_topics:
            video_files = get_topic_background_files(fallback_topic)

            if video_files:
                print(f"No videos for {topic}. Using {fallback_topic} videos instead.")
                break

    if not video_files:
        print("No local videos found. Downloading one background video...")

        try:
            video_path = search_and_download_video(topic)
        except Exception:
            print("Topic download failed. Using self improvement instead.")
            video_path = search_and_download_video("self improvement")

        video = VideoFileClip(video_path)
        return loop_single_video(video, duration)

    print(f"Using {len(video_files)} local background videos for topic:", topic)

    random.shuffle(video_files)

    clips = []
    current_duration = 0
    opened_clips = []

    while current_duration < duration:
        for path in video_files:
            if current_duration >= duration:
                break

            try:
                raw_clip = VideoFileClip(path)
                opened_clips.append(raw_clip)

                usable_duration = min(CLIP_LENGTH, raw_clip.duration)
                remaining = duration - current_duration
                final_clip_duration = min(usable_duration, remaining)

                start_time = 0

                if raw_clip.duration > final_clip_duration + 1:
                    start_time = random.uniform(
                        0,
                        raw_clip.duration - final_clip_duration
                    )

                clip = raw_clip.subclipped(
                    start_time,
                    start_time + final_clip_duration
                )

                clip = make_vertical_background(clip)
                clip = clip.with_duration(final_clip_duration)

                if len(clips) > 0:
                    clip = clip.with_effects([vfx.FadeIn(0.25)])

                clip = clip.with_effects([vfx.FadeOut(0.25)])

                clips.append(clip)
                current_duration += final_clip_duration

            except Exception as error:
                print("Skipping bad video:", path)
                print("Reason:", error)

    montage = concatenate_videoclips(clips, method="compose")
    montage.opened_clips = opened_clips

    return montage.with_duration(duration)


def loop_single_video(video, duration):
    vertical = make_vertical_background(video)

    clips = []

    while sum(c.duration for c in clips) < duration:
        remaining = duration - sum(c.duration for c in clips)

        if remaining >= vertical.duration:
            clips.append(vertical.subclipped(0, vertical.duration))
        else:
            clips.append(vertical.subclipped(0, remaining))

    return concatenate_videoclips(clips, method="compose").with_duration(duration)


async def main():
    os.makedirs("output", exist_ok=True)

    setup_database()

    topic, script, _, _, _ = generate_script()
    title, description, hashtags = generate_metadata(topic, script)

    print("Topic:", topic)
    print("Script:", script)
    print("Title:", title)
    print("Description:", description)
    print("Hashtags:", hashtags)

    print("Generating voice...")
    await generate_voice(script)

    voice = AudioFileClip(VOICE_FILE)
    duration = voice.duration

    final_audio = voice
    music = None

    music_file = get_random_music()

    if music_file:
        print("Adding background music:", music_file)

        music = AudioFileClip(music_file)

        if music.duration < duration:
            music = loop_audio(music, duration)
        else:
            music = music.subclipped(0, duration)

        music = music.with_volume_scaled(0.12)
        final_audio = CompositeAudioClip([music, voice])

    print("Creating topic montage...")
    background = create_topic_montage(topic, duration, script)

    print("Generating word-by-word captions...")
    captions = make_word_caption_clips(VOICE_FILE)

    final = CompositeVideoClip(
        [background, *captions],
        size=(WIDTH, HEIGHT),
    )

    final = final.with_audio(final_audio)

    safe_topic = topic.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = f"output/{timestamp}_{safe_topic}.mp4"

    final.write_videofile(
        output_file,
        fps=30,
        codec="libx264",
        audio_codec="aac",
    )

    save_video(topic, script, title, description, hashtags, output_file)

    final.close()
    background.close()
    voice.close()

    if hasattr(background, "opened_clips"):
        for clip in background.opened_clips:
            clip.close()

    if music:
        music.close()

    if music and final_audio:
        final_audio.close()
    clear_temp_backgrounds()
    print("Saved as:", output_file)
    # subprocess.run(["open", output_file])
    print("Automatic reel created successfully")



if __name__ == "__main__":
    asyncio.run(main())