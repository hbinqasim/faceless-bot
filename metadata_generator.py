import requests

MODEL = "llama3.1:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"


def clean_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def generate_metadata(topic, script):
    prompt = f"""
You are a YouTube Shorts growth expert.

Topic: {topic}

Script:
{script}

Create:
1. One viral title under 60 characters
2. One short description
3. 8 relevant hashtags

Rules:
No emojis.
No quotes.
Return exactly this format:

TITLE:
...

DESCRIPTION:
...

HASHTAGS:
...
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
    text = response.json()["response"]

    title = ""
    description = ""
    hashtags = ""

    current = None

    for line in clean_lines(text):
        low = line.lower()

        if low.startswith("title"):
            current = "title"
            continue

        if low.startswith("description"):
            current = "description"
            continue

        if low.startswith("hashtags"):
            current = "hashtags"
            continue

        if current == "title":
            title = line

        elif current == "description":
            description += line + " "

        elif current == "hashtags":
            hashtags += line + " "

    if not title:
        title = f"{topic.title()} Advice That Changes Everything"

    if not description:
        description = f"{script}\n\nFollow for more daily improvement videos."

    if not hashtags:
        hashtags = f"#{topic.replace(' ', '')} #motivation #mindset #success #shorts"

    return title.strip(), description.strip(), hashtags.strip()
