import whisper
from moviepy import TextClip

MODEL = None

IMPORTANT_WORDS = {
    "MONEY",
    "WEALTH",
    "SUCCESS",
    "DISCIPLINE",
    "FOCUS",
    "CONFIDENCE",
    "BUSINESS",
    "DOPAMINE",
    "ACTION",
    "DREAMS",
    "FEAR",
    "FAILURE",
    "MOTIVATION",
    "GROWTH",
    "MINDSET",
}


def get_model():
    global MODEL

    if MODEL is None:
        MODEL = whisper.load_model("base")

    return MODEL


def transcribe_words(audio_path):
    model = get_model()

    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        verbose=False
    )

    words = []

    for segment in result["segments"]:
        for word in segment.get("words", []):
            text = word["word"].strip()
            start = word["start"]
            end = word["end"]

            if text:
                words.append({
                    "text": text,
                    "start": start,
                    "end": end
                })

    return words


def clean_word(text):
    return (
        text.upper()
        .replace(".", "")
        .replace(",", "")
        .replace("!", "")
        .replace("?", "")
        .replace("'", "")
        .replace('"', "")
    )


def make_word_caption_clips(audio_path):
    words = transcribe_words(audio_path)

    clips = []

    for word in words:
        raw_text = word["text"]
        display_text = clean_word(raw_text)

        duration = max(word["end"] - word["start"], 0.18)

        is_important = display_text in IMPORTANT_WORDS

        font_size = 96 if is_important else 82
        color = "yellow" if is_important else "white"

        clip = TextClip(
            text=display_text,
            font_size=font_size,
            color=color,
            stroke_color="black",
            stroke_width=6,
            size=(900, 220),
            method="caption",
        )

        clip = clip.with_position(("center", 1120))
        clip = clip.with_start(word["start"])
        clip = clip.with_duration(duration)

        clip = clip.resized(
            lambda t: 1.18 - 0.18 * min(t / 0.12, 1)
        )

        clips.append(clip)

    return clips