import random
import requests
import re


MODEL = "llama3.1:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"


def clean_script(text):
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("Narrator:", "")
    text = text.replace("Voiceover:", "")
    text = text.replace("VO:", "")
    text = text.replace('"', "")
    text = text.replace("“", "")
    text = text.replace("”", "")

    lines = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        low = line.lower()

        bad_phrases = [
            "here's",
            "here is",
            "motivational script",
            "youtube shorts",
            "topic:",
            "script:",
            "style example",
            "rules:",
        ]

        if any(phrase in low for phrase in bad_phrases):
            continue

        if "visual" in low:
            continue

        if "music" in low:
            continue

        if "scene" in low:
            continue

        if "#" in line:
            continue

        line = line.replace("-", "").strip()
        line = line.rstrip(".")

        if line:
            lines.append(line)

    cleaned_lines = []

    for line in lines:
        words = line.split()

        if len(words) > 10:
            line = " ".join(words[:10])

        cleaned_lines.append(line)

    cleaned_lines = cleaned_lines[:7]

    cleaned_lines.append("Follow for more.")

    return "\n".join(cleaned_lines)


def generate_ai_script(topic):
    prompt = f"""
You are a viral YouTube Shorts script writer.

Topic: {topic}

Write ONLY the spoken script.

Rules:
8 lines total.
Each line must be 3 to 8 words.
First line must be a strong hook.
Use simple powerful English.
Make it emotional.
Make it punchy.
No long sentences.
No commas.
No labels.
No intro.
No explanation.
No scene directions.
No hashtags.
No emojis.

Final line must be exactly:
Subscribe for more.

Style example:
Nobody talks about this
Comfort is stealing your life
You keep waiting for motivation
But motivation always disappears
Discipline stays when feelings leave
Small actions create massive change
Start before you feel ready
Subscribe for more.
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )

    response.raise_for_status()
    data = response.json()

    return clean_script(data["response"])


def generate_script():
    with open("topics.txt", "r") as file:
        topics = [
            line.strip()
            for line in file.readlines()
            if line.strip()
        ]

    topic = random.choice(topics)

    script = generate_ai_script(topic)

    title = f"{topic.title()} Advice That Changes Everything"

    description = (
        f"{script}\n\n"
        "Follow for more daily improvement videos."
    )

    clean_topic = topic.replace(" ", "")

    hashtags = (
        f"#{clean_topic} "
        "#motivation "
        "#mindset "
        "#success "
        "#shorts"
    )

    return topic, script, title, description, hashtags