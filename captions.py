from moviepy import TextClip

def make_caption_clips(script, total_duration):
    lines = [line.strip() for line in script.splitlines() if line.strip()]

    caption_clips = []
    current_time = 0
    total_chars = sum(len(line) for line in lines)

    for line in lines:
        line_duration = total_duration * (len(line) / total_chars)
        line_duration = max(line_duration, 1.25)

        caption = TextClip(
            text=line.upper(),
            font_size=58,
            color="white",
            stroke_color="black",
            stroke_width=5,
            size=(920, 320),
            method="caption",
        )

        caption = caption.with_position(("center", 1120))
        caption = caption.with_start(current_time)
        caption = caption.with_duration(line_duration)

        caption_clips.append(caption)
        current_time += line_duration

    return caption_clips