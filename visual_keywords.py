import re


KEYWORD_MAP = {
    "money": "money counting",
    "wealth": "luxury lifestyle",
    "business": "business meeting",
    "entrepreneur": "startup founder",
    "success": "successful person walking",
    "discipline": "early morning workout",
    "focus": "focused work desk",
    "productivity": "desk productivity",
    "confidence": "confident person walking",
    "mindset": "person thinking alone",
    "psychology": "person reflecting",
    "dopamine": "phone addiction",
    "phone": "social media scrolling",
    "comfort": "relaxing on couch",
    "motivation": "motivational workout",
    "failure": "person frustrated",
    "fear": "person stressed",
    "dreams": "person looking at city",
    "action": "person working hard",
    "growth": "personal growth",
    "habits": "daily routine",
    "routine": "morning routine",
    "work": "working on laptop",
    "sales": "business handshake",
    "marketing": "digital marketing",
}


def extract_visual_queries(topic, script, max_queries=5):
    text = f"{topic} {script}".lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)

    queries = []

    for keyword, query in KEYWORD_MAP.items():
        if keyword in text and query not in queries:
            queries.append(query)

    if not queries:
        queries.append(topic)

    return queries[:max_queries]
