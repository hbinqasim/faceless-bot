"""Config-driven trending-news research agent for Vice Studio."""

from __future__ import annotations

import datetime as dt
import email.utils
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from html import unescape
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from services.llm.service import generate as generate_llm
from vice_studio.config_loader import load_component_config


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DB_MODULE_PATH = ROOT_DIR / "database" / "db.py"
SCHEMA_MODULE_PATH = ROOT_DIR / "database" / "schema.py"


@dataclass
class ArticleCandidate:
    title: str
    url: str
    source: str
    authority: float
    published: dt.datetime
    summary: str
    text: str
    key_facts: list[str] = field(default_factory=list)
    why_trending: str = ""
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)


def load_config() -> dict[str, Any]:
    try:
        config = load_component_config(CONFIG_PATH)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid research config.json: {error}") from error

    if not isinstance(config, dict):
        raise ValueError("Research config must be a JSON object.")

    return config


def project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def output_paths(config: dict[str, Any]) -> tuple[Path, Path, Path]:
    channel = str(config.get("channel", "default"))
    output_dir = project_path(str(config.get("output_dir", f"channels/{channel}/research")))
    return output_dir, output_dir / "latest_topic.json", output_dir / "latest_article.md"


def fetch_url(url: str) -> str:
    headers = {
        "User-Agent": "ViceStudioResearchAgent/4.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=8)
    response.raise_for_status()
    return response.text


def discover_links(source: dict[str, Any], config: dict[str, Any]) -> list[str]:
    max_links = int(config.get("max_links_per_source", 12))
    discovered: list[str] = []
    seen: set[str] = set()

    for seed in source.get("seeds", []):
        try:
            html = fetch_url(str(seed))
        except requests.RequestException as exc:
            print(f"Skipping seed {seed}: request failed ({exc})")
            continue

        if is_rss_seed(str(seed), html):
            for item in parse_rss_items(html):
                href = normalize_spaces(str(item.get("link", "")))
                link_text = normalize_spaces(str(item.get("title", "")))

                if not href:
                    continue

                url = normalize_url(urljoin(str(seed), href))
                url = unwrap_google_news_url(url)

                if not url or url in seen:
                    continue

                if not looks_relevant(config, url, link_text):
                    continue

                seen.add(url)
                discovered.append(url)

                if len(discovered) >= max_links:
                    break
        else:
            soup = BeautifulSoup(html, "html.parser")

            for anchor in soup.find_all("a", href=True):
                href = str(anchor.get("href", "")).strip()
                url = normalize_url(urljoin(str(seed), href))

                if url in seen:
                    continue
                if not source_allows_url(url, source):
                    continue

                link_text = normalize_spaces(anchor.get_text(" ", strip=True))

                if not looks_relevant(config, url, link_text):
                    continue

                seen.add(url)
                discovered.append(url)

                if len(discovered) >= max_links:
                    break

        if len(discovered) >= max_links:
            break

    return discovered


def parse_rss_items(content: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    for block in re.findall(r"<item\b.*?</item>", content, flags=re.IGNORECASE | re.DOTALL):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", block, flags=re.IGNORECASE | re.DOTALL)
        link_match = re.search(r"<link[^>]*>(.*?)</link>", block, flags=re.IGNORECASE | re.DOTALL)

        title = clean_rss_value(title_match.group(1)) if title_match else ""
        link = clean_rss_value(link_match.group(1)) if link_match else ""

        if title or link:
            items.append({"title": title, "link": link})

    return items


def clean_rss_value(value: str) -> str:
    value = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", value or "", flags=re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    return normalize_spaces(unescape(value))

def is_rss_seed(seed: str, content: str) -> bool:
    lower_seed = seed.lower()
    sample = content[:300].lower()
    return (
        lower_seed.endswith(".rss")
        or "/rss/" in lower_seed
        or "rss/search" in lower_seed
        or "<rss" in sample
        or "<feed" in sample
    )


def unwrap_google_news_url(url: str) -> str:
    parsed = urlparse(url)

    if "news.google.com" not in parsed.netloc:
        return url

    query = parse_qs(parsed.query)

    for key in ("url", "u"):
        values = query.get(key)
        if values:
            return normalize_url(values[0])

    return url

def collect_candidates(config: dict[str, Any]) -> list[ArticleCandidate]:
    lookback_days = int(config.get("lookback_days", 14))
    cutoff = now_utc() - dt.timedelta(days=lookback_days)
    min_text_length = int(config.get("min_text_length", 300))

    candidates: list[ArticleCandidate] = []
    seen_urls: set[str] = set()

    for source in config.get("sources", []):
        for url in discover_links(source, config):
            if url in seen_urls:
                continue

            seen_urls.add(url)
            candidate = fetch_candidate(url, source, config, cutoff, lookback_days, min_text_length)

            if candidate is not None:
                candidates.append(candidate)

    return candidates


def fetch_candidate(
    url: str,
    source: dict[str, Any],
    config: dict[str, Any],
    cutoff: dt.datetime,
    lookback_days: int,
    min_text_length: int,
) -> ArticleCandidate | None:
    try:
        html = fetch_url(url)
    except requests.RequestException as exc:
        print(f"Skipping {url}: request failed ({exc})")
        return None

    candidate = parse_article(url, html, source, config)

    if candidate is None:
        print(f"Skipping {url}: no publication date found")
        return None

    if candidate.published < cutoff:
        print(f"Skipping {url}: older than {lookback_days} days")
        return None

    if len(candidate.text) < min_text_length:
        print(f"Skipping {url}: text too short ({len(candidate.text)} characters)")
        return None

    if not looks_relevant(config, candidate.title, candidate.summary, candidate.text[:2000]):
        print(f"Skipping {url}: not relevant to niche")
        return None

    return candidate


def parse_article(
    url: str,
    html: str,
    source: dict[str, Any],
    config: dict[str, Any],
) -> ArticleCandidate | None:
    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "noscript", "svg", "form", "nav", "footer", "aside"]):
        element.extract()

    title = extract_title(soup) or url
    published = extract_published_date(soup)

    if published is None:
        return None

    text = extract_article_body_text(soup)
    if not text:
        text = normalize_spaces(soup.get_text(" ", strip=True))
    text = trim_article_boilerplate(text)

    summary = extract_summary(soup, text)
    key_facts = extract_key_facts(text, config)

    return ArticleCandidate(
        title=title,
        url=url,
        source=str(source.get("name", "Unknown Source")),
        authority=float(source.get("authority", 0.5)),
        published=published,
        summary=summary,
        text=text,
        key_facts=key_facts,
    )


def extract_article_body_text(soup: BeautifulSoup) -> str:
    candidates: list[str] = []

    selectors = [
        "article",
        "[itemprop='articleBody']",
        ".entry-content",
        ".post-content",
        ".article-content",
        ".content",
        "main",
    ]

    for selector in selectors:
        for node in soup.select(selector):
            cleaned = clean_article_node_text(node)
            if len(cleaned) > 300:
                candidates.append(cleaned)

    if candidates:
        return max(candidates, key=len)

    paragraphs: list[str] = []
    for paragraph in soup.find_all("p"):
        line = normalize_spaces(paragraph.get_text(" ", strip=True))
        if len(line) >= 40 and not is_article_noise(line):
            paragraphs.append(line)

    return normalize_spaces(" ".join(paragraphs))


def clean_article_node_text(node: Any) -> str:
    for bad in node.select(
        "script, style, noscript, svg, nav, footer, aside, form, "
        ".comments, .comment, .related, .newsletter, .sidebar, "
        ".advertisement, .ad, .ads, .social, .share, .menu"
    ):
        bad.extract()

    parts: list[str] = []

    for element in node.find_all(["p", "li", "h2", "h3", "td", "th"]):
        line = normalize_spaces(element.get_text(" ", strip=True))
        if len(line) >= 25 and not is_article_noise(line):
            parts.append(line)

    return normalize_spaces(" ".join(parts))


def is_article_noise(text: str) -> bool:
    lower = text.lower()

    noise_fragments = [
        "add a comment",
        "join the discussion",
        "community comments",
        "related stories",
        "more from",
        "follow @",
        "get it on google play",
        "privacy policy",
        "terms",
        "newsletter",
        "subscribe",
        "no thanks",
        "loading",
        "checking your",
        "play today",
        "account",
        "topics in this article",
        "tiktok highlights",
        "server explorer",
        "market odds",
        "quick starts",
        "do not sell",
        "raptive partner",
        "copyright",
        "all rights reserved",
    ]

    return any(fragment in lower for fragment in noise_fragments)


def trim_article_boilerplate(text: str) -> str:
    """Stop before reader prompts, author boxes, and appended related stories."""
    normalized = normalize_spaces(text)
    boundary_patterns = [
        r"\bwhat do you think (?:of|about)\b",
        r"\bwill you be (?:watching|playing|buying)\b",
        r"\blet us know (?:down )?in the comment",
        r"\bleave your thoughts (?:down )?in the comments\b",
        r"\byou can pre-order .{0,80}\bwith this link\b",
        r"\busing the link to pre-order\b",
        r"\bdrop a comment\b",
        r"\bcancel reply\b",
        r"\bjoin (?:the|our) (?:discussion|discord)\b",
        r"\blevel up your gaming news\b",
        r"\bmore from [a-z0-9 .'-]+\b",
    ]
    earliest = len(normalized)
    for pattern in boundary_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            earliest = min(earliest, match.start())
    return normalized[:earliest].strip()


def score_candidates(candidates: list[ArticleCandidate], config: dict[str, Any]) -> None:
    keywords = [str(k) for k in config.get("engagement_keywords", [])]
    weights = config.get("score_weights", {})

    max_keyword_hits = max((keyword_hits(candidate, keywords) for candidate in candidates), default=1)
    all_token_sets = [token_set(candidate.title + " " + candidate.summary) for candidate in candidates]

    for index, candidate in enumerate(candidates):
        age_days = max((now_utc() - candidate.published).total_seconds() / 86400, 0)
        lookback_days = max(int(config.get("lookback_days", 14)), 1)

        freshness_score = max(0.0, 1.0 - (age_days / lookback_days))
        authority_score = max(0.0, min(candidate.authority, 1.0))
        engagement_score = keyword_hits(candidate, keywords) / max(max_keyword_hits, 1)
        uniqueness_score = uniqueness(index, all_token_sets)

        candidate.score = (
            freshness_score * float(weights.get("freshness", 0.35))
            + authority_score * float(weights.get("authority", 0.25))
            + engagement_score * float(weights.get("engagement", 0.25))
            + uniqueness_score * float(weights.get("uniqueness", 0.15))
        )

        candidate.score_breakdown = {
            "freshness_score": freshness_score,
            "authority_score": authority_score,
            "engagement_score": engagement_score,
            "uniqueness_score": uniqueness_score,
            "final_score": candidate.score,
        }

        candidate.why_trending = build_why_trending(candidate, config)


def choose_highest_scoring_article(
    candidates: list[ArticleCandidate],
    config: dict[str, Any],
) -> ArticleCandidate:
    if not candidates:
        niche = config.get("niche", "this niche")
        raise RuntimeError(f"No trending articles found for {niche}.")

    fresh_candidates = []
    blocked_candidates = []

    for candidate in candidates:
        if is_recently_used(candidate, config):
            blocked_candidates.append(candidate)
        else:
            fresh_candidates.append(candidate)

    if not fresh_candidates:
        raise RuntimeError(
            "No fresh unused topics found. Add more sources, increase max_links_per_source, "
            "or clear the used_topics file."
        )

    return max(fresh_candidates, key=lambda candidate: candidate.score)



def build_research_structure(candidate: ArticleCandidate, config: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
You are a strict research editor for a short-form video automation pipeline.

Use ONLY the article body.
Return valid JSON only.
Do not invent facts.
Do not include ads, comments, navigation, related stories, newsletter text, widgets, or sidebars.

Return this exact JSON shape:
{{
  "summary": "one short clean paragraph",
  "key_facts": [
    "complete factual sentence"
  ],
  "context": {{
    "main_conflict": "one sentence",
    "why_it_matters": "one sentence",
    "audience_angle": "one sentence"
  }},
  "claims": [
    {{
      "claim": "specific claim",
      "status": "reported|disputed|confirmed|analysis|unknown",
      "source_type": "article|company_statement|retailer_data|official_source|analysis",
      "confidence": 0.0
    }}
  ],
  "script_angles": [
    "short video angle"
  ],
  "avoid": [
    "thing the script must not say"
  ]
}}

Title:
{candidate.title}

Source:
{candidate.source}

Published:
{candidate.published.isoformat()}

Article body:
{candidate.text[:6000]}
""".strip()

    raw = generate_llm(prompt)
    data = parse_json_object(raw)
    return validate_research_structure(data)

def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")

    return json.loads(cleaned[start:end + 1])



def validate_research_structure(data: dict[str, Any]) -> dict[str, Any]:
    summary = clean_text(str(data.get("summary", "")))

    raw_facts = data.get("key_facts", [])
    if not isinstance(raw_facts, list):
        raw_facts = []

    facts: list[str] = []
    seen: set[str] = set()

    for item in raw_facts:
        fact = clean_text(str(item))

        if not fact:
            continue
        if not fact.endswith((".", "?", "!")):
            continue
        if len(fact.split()) < 6:
            continue
        if len(fact.split()) > 42:
            continue

        key = fact.lower()
        if key in seen:
            continue

        seen.add(key)
        facts.append(fact)

    context = data.get("context", {})
    if not isinstance(context, dict):
        context = {}

    claims = data.get("claims", [])
    if not isinstance(claims, list):
        claims = []

    clean_claims: list[dict[str, Any]] = []

    for claim in claims[:6]:
        if not isinstance(claim, dict):
            continue

        claim_text = clean_text(str(claim.get("claim", "")))
        if not claim_text:
            continue

        try:
            confidence = float(claim.get("confidence", 0.6))
        except (TypeError, ValueError):
            confidence = 0.6

        clean_claims.append({
            "claim": claim_text,
            "status": clean_text(str(claim.get("status", "reported"))) or "reported",
            "source_type": clean_text(str(claim.get("source_type", "article"))) or "article",
            "confidence": max(0.0, min(confidence, 1.0)),
        })

    script_angles = data.get("script_angles", [])
    if not isinstance(script_angles, list):
        script_angles = []

    avoid = data.get("avoid", [])
    if not isinstance(avoid, list):
        avoid = []

    return {
        "summary": summary,
        "key_facts": facts[:8],
        "context": {
            "main_conflict": clean_text(str(context.get("main_conflict", ""))),
            "why_it_matters": clean_text(str(context.get("why_it_matters", ""))),
            "audience_angle": clean_text(str(context.get("audience_angle", ""))),
        },
        "claims": clean_claims,
        "script_angles": [clean_text(str(x)) for x in script_angles if clean_text(str(x))][:6],
        "avoid": [clean_text(str(x)) for x in avoid if clean_text(str(x))][:8],
    }


def fallback_research_structure(candidate: ArticleCandidate, facts: list[str]) -> dict[str, Any]:
    return {
        "summary": clean_text(candidate.summary),
        "why_trending": "This topic is timely because it is part of the current GTA 6 news cycle.",
        "context": {
            "main_conflict": clean_text(candidate.title),
            "why_it_matters": "The story affects how fans understand the latest GTA 6 discussion.",
            "audience_angle": "Viewers care because GTA 6 updates drive platform, release, and buying expectations.",
        },
        "claims": [
            {
                "claim": fact,
                "status": "reported",
                "source_type": "article",
                "confidence": 0.6,
            }
            for fact in facts[:5]
        ],
        "script_angles": [
            "Explain the main GTA 6 claim clearly.",
            "Show what is confirmed, disputed, or still unknown.",
            "Focus on why this matters to players.",
        ],
        "avoid": [
            "Do not present rumors as official confirmation.",
            "Do not invent numbers or dates.",
            "Do not include comments, ads, sidebars, newsletters, or unrelated site content.",
        ],
    }


def save_outputs(candidate: ArticleCandidate, config: dict[str, Any]) -> None:
    output_dir, latest_topic_path, latest_article_path = output_paths(config)
    output_dir.mkdir(parents=True, exist_ok=True)

    topic_type = classify_topic_type(candidate, config)
    confidence = estimate_confidence(candidate, config)

    try:
        structure = build_research_structure(candidate, config)
    except Exception as error:
        print(f"Research structuring fallback used: {error}")
        structure = fallback_research_structure(candidate, candidate.key_facts)
    facts = structure.get("key_facts", [])

    topic = {
        "title": clean_text(candidate.title),
        "url": candidate.url,
        "source": candidate.source,
        "published": candidate.published.isoformat(),
        "summary": clean_text(str(structure.get("summary") or candidate.summary)),
        "why_trending": build_structured_why_trending(candidate, config),
        "key_facts": facts,
        "score": round(candidate.score, 4),
        "score_breakdown": candidate.score_breakdown,

        "niche": str(config.get("niche", "")),
        "topic_type": topic_type,
        "confidence": confidence,
        "is_official": is_official_source(candidate, config),
        "editorial_score": round(editorial_score(candidate, config), 4),
        "sources": [
            {
                "name": candidate.source,
                "url": candidate.url,
                "authority": candidate.authority,
                "published": candidate.published.isoformat(),
                "role": "primary",
            }
        ],
        "facts": facts,
        "context": structure.get("context", {}),
        "claims": structure.get("claims", []),
        "script_angles": structure.get("script_angles", []),
        "avoid": structure.get("avoid", []),
        "entities": extract_entities(candidate, config),
        "keywords": extract_keywords(candidate, config),
        "research_generated_at": now_utc().isoformat(),
    }

    if config.get("include_article_text", False):
        max_chars = int(config.get("article_text_max_chars", 12000))
        topic["article_text"] = clean_text(candidate.text)[:max_chars]

    latest_topic_path.write_text(
        json.dumps(topic, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    latest_article_path.write_text(
        "\n".join(
            [
                f"# {candidate.title}",
                "",
                f"- Source: {candidate.source}",
                f"- URL: {candidate.url}",
                f"- Published: {candidate.published.isoformat()}",
                f"- Score: {candidate.score:.4f}",
                f"- Topic type: {topic_type}",
                f"- Confidence: {confidence}",
                "",
                "## Summary",
                "",
                topic["summary"],
                "",
                "## Key Facts",
                "",
                *[f"- {fact}" for fact in facts],
                "",
                "## Context",
                "",
                json.dumps(topic["context"], indent=2, ensure_ascii=False),
                "",
                "## Claims",
                "",
                json.dumps(topic["claims"], indent=2, ensure_ascii=False),
                "",
            ]
        ),
        encoding="utf-8",
    )

def best_effort_database_insert(candidate: ArticleCandidate, channel: str) -> None:
    if not DB_MODULE_PATH.exists() or not SCHEMA_MODULE_PATH.exists():
        return

    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    try:
        schema_spec = importlib.util.spec_from_file_location("schema", str(SCHEMA_MODULE_PATH))
        if schema_spec is None or schema_spec.loader is None:
            return

        schema_module = importlib.util.module_from_spec(schema_spec)
        sys.modules["schema"] = schema_module
        schema_spec.loader.exec_module(schema_module)

        db_spec = importlib.util.spec_from_file_location("vice_database", str(DB_MODULE_PATH))
        if db_spec is None or db_spec.loader is None:
            return

        vice_database = importlib.util.module_from_spec(db_spec)
        db_spec.loader.exec_module(vice_database)
        vice_database.initialize_database()

        source_id = vice_database.insert_source(
            name=candidate.source,
            url=candidate.url,
            source_type=channel,
        )

        vice_database.insert_article(
            source_id=source_id,
            title=candidate.title,
            url=candidate.url,
            published_at=candidate.published.isoformat(),
            raw_text=candidate.text,
        )

    except Exception as exc:
        print(f"Database insert skipped: {exc}")


def extract_title(soup: BeautifulSoup) -> str:
    for selector in [
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "twitter:title"}),
    ]:
        tag = soup.find(*selector)
        if tag and tag.get("content"):
            return normalize_spaces(str(tag["content"]))

    if soup.title and soup.title.string:
        return normalize_spaces(soup.title.string)

    heading = soup.find("h1")
    return normalize_spaces(heading.get_text(" ", strip=True)) if heading else ""


def extract_summary(soup: BeautifulSoup, text: str) -> str:
    for selector in [
        ("meta", {"name": "description"}),
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "twitter:description"}),
    ]:
        tag = soup.find(*selector)
        if tag and tag.get("content"):
            return trim_sentence(normalize_spaces(str(tag["content"])), 360)

    return trim_sentence(text, 360)


def extract_published_date(soup: BeautifulSoup) -> dt.datetime | None:
    candidates: list[str] = []

    for attrs in [
        {"property": "article:published_time"},
        {"name": "article:published_time"},
        {"name": "pubdate"},
        {"name": "publishdate"},
        {"name": "date"},
        {"itemprop": "datePublished"},
    ]:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            candidates.append(str(tag["content"]))

    for time_tag in soup.find_all("time"):
        if time_tag.get("datetime"):
            candidates.append(str(time_tag["datetime"]))
        elif time_tag.get_text(strip=True):
            candidates.append(time_tag.get_text(strip=True))

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue

        candidates.extend(extract_jsonld_dates(data))

    for value in candidates:
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed

    return None


def extract_jsonld_dates(data: Any) -> list[str]:
    dates: list[str] = []

    if isinstance(data, dict):
        for key in ["datePublished", "dateCreated", "uploadDate"]:
            if data.get(key):
                dates.append(str(data[key]))

        for value in data.values():
            dates.extend(extract_jsonld_dates(value))

    elif isinstance(data, list):
        for item in data:
            dates.extend(extract_jsonld_dates(item))

    return dates


def parse_datetime(value: str) -> dt.datetime | None:
    cleaned = normalize_spaces(value)

    if not cleaned:
        return None

    try:
        parsed = dt.datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        return ensure_utc(parsed)
    except ValueError:
        pass

    try:
        parsed = email.utils.parsedate_to_datetime(cleaned)
        return ensure_utc(parsed)
    except (TypeError, ValueError):
        return None


def ensure_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)

    return value.astimezone(dt.timezone.utc)


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def source_allows_url(url: str, source: dict[str, Any]) -> bool:
    host = urlparse(url).netloc.lower().replace("www.", "")
    domains = [str(domain).lower().replace("www.", "") for domain in source.get("domains", [])]

    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def looks_relevant(config: dict[str, Any], *parts: str) -> bool:
    text = " ".join(parts).lower()
    terms = [str(term).lower() for term in config.get("relevance_terms", [])]

    if not terms:
        niche = str(config.get("niche", "")).lower()
        terms = [niche] if niche else []

    return any(term in text for term in terms)


def keyword_hits(candidate: ArticleCandidate, keywords: list[str]) -> int:
    text = searchable_candidate_text(candidate)
    return sum(1 for keyword in keywords if keyword.lower() in text)


def token_set(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 3}


def uniqueness(index: int, all_token_sets: list[set[str]]) -> float:
    own = all_token_sets[index]

    if not own or len(all_token_sets) == 1:
        return 1.0

    overlaps: list[float] = []

    for other_index, other in enumerate(all_token_sets):
        if other_index == index:
            continue

        union = own | other
        overlaps.append(len(own & other) / len(union) if union else 0.0)

    return max(0.0, 1.0 - (sum(overlaps) / len(overlaps)))


def build_why_trending(candidate: ArticleCandidate, config: dict[str, Any]) -> str:
    keywords = [str(k) for k in config.get("engagement_keywords", [])]
    searchable = f"{candidate.title} {candidate.summary}".lower()
    hits = [keyword for keyword in keywords if keyword.lower() in searchable]

    if hits:
        return (
            f"Selected from {candidate.source} because it is recent, relevant, "
            f"and contains strong engagement signals: {', '.join(hits[:6])}."
        )

    return (
        f"Selected from {candidate.source} because it scored highest for freshness, "
        "source authority, uniqueness, and niche relevance."
    )


def extract_key_facts(text: str, config: dict[str, Any]) -> list[str]:
    sentences = split_complete_sentences(text)
    scored: list[tuple[float, str]] = []

    trigger_terms = [
        str(term).lower()
        for term in config.get("relevance_terms", []) + config.get("engagement_keywords", [])
    ]

    for sentence in sentences:
        cleaned = clean_text(sentence)

        if is_bad_fact(cleaned, config):
            continue

        words = cleaned.split()
        if len(words) < 7:
            continue

        lower = cleaned.lower()
        score = 0.0

        if trigger_terms:
            score += sum(1.0 for term in trigger_terms if term in lower)

        factual_markers = [
            "said", "says", "confirmed", "announced", "reported", "according",
            "claim", "claims", "data", "orders", "sales", "release", "launch",
            "pre-order", "preorder", "record", "official", "statement",
            "neither", "no official", "does not represent"
        ]

        score += sum(0.75 for marker in factual_markers if marker in lower)

        if any(char.isdigit() for char in cleaned):
            score += 0.75

        if len(words) > 32:
            score -= 0.75

        if score <= 0:
            continue

        scored.append((score, cleaned))

    scored.sort(key=lambda item: item[0], reverse=True)

    facts: list[str] = []
    seen: set[str] = set()

    for _, fact in scored:
        key = re.sub(r"[^a-z0-9]+", " ", fact.lower()).strip()
        if key in seen:
            continue

        seen.add(key)
        facts.append(trim_sentence(fact, int(config.get("max_fact_chars", 240))))

        if len(facts) >= int(config.get("max_facts", 5)):
            break

    return facts


def split_complete_sentences(text: str) -> list[str]:
    raw_sentences = re.split(r"(?<=[.!?])\s+", normalize_spaces(text))
    sentences: list[str] = []

    for sentence in raw_sentences:
        sentence = normalize_spaces(sentence)

        if not sentence:
            continue

        if sentence[-1] not in ".?!":
            continue

        sentences.append(sentence)

    return sentences

def is_bad_fact(text: str, config: dict[str, Any]) -> bool:
    lower = text.lower()
    bad_fragments = [str(item).lower() for item in config.get("bad_fact_fragments", [])]

    if any(fragment in lower for fragment in bad_fragments):
        return True

    for pattern in config.get("bad_fact_regexes", []):
        try:
            if re.search(str(pattern), lower, flags=re.IGNORECASE):
                return True
        except re.error:
            continue

    if len(text.split()) > int(config.get("max_fact_words", 36)):
        return True

    generic_bad_patterns = [
        r"\bin other news\b",
        r"\bthese numbers aren.?t surprising\b",
        r"\bhis to ric\b",
        r"\bwe recorded\b.*\bpreorders\b",
        r"\bsomething we.?ve never seen before\b",
        r"\bit.?s historic\b",
        r"\bcomes from our\b",
        r"\bour french colleagues\b",
        r"\bphysical disc edition after all\b",
    ]

    for pattern in generic_bad_patterns:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            return True

    if text.count(" - ") >= int(config.get("max_dash_sections", 2)):
        return True

    generic_bad_patterns = [
        r"\bin other news\b",
        r"\bthere are .?no plans.? to ever print\b",
        r"\bnew report suggests that there are no plans\b",
        r"\bfolks were turning\b",
        r"\bturning feral\b",
        r"\bthis fire was fuelled\b",
        r"\bnetizens worldwide\b",
        r"\bthese numbers aren.?t surprising\b",
        r"\bhis to ric\b",
        r"\bsomething we.?ve never seen before\b",
        r"\bit.?s historic\b",
        r"\bcomes from our\b",
        r"\bour french colleagues\b",
    ]

    for pattern in generic_bad_patterns:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            return True

    return False


def clean_text(text: str) -> str:
    text = normalize_spaces(text)
    text = text.replace("XBOX", "Xbox")
    text = text.replace("Play Station", "PlayStation")
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-z])to([a-z])", r"\1 to \2", text)
    return normalize_spaces(text)

def clean_facts(facts: list[str], config: dict[str, Any]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for fact in facts:
        fact_text = clean_text(str(fact))

        if not fact_text:
            continue

        if is_bad_fact(fact_text, config):
            continue

        key = fact_text.lower()

        if key in seen:
            continue

        seen.add(key)
        cleaned.append(fact_text)

        if len(cleaned) >= int(config.get("max_facts", 5)):
            break

    return cleaned


def is_official_source(candidate: ArticleCandidate, config: dict[str, Any]) -> bool:
    host = urlparse(candidate.url).netloc.lower().replace("www.", "")
    official_domains = [
        str(domain).lower().replace("www.", "")
        for domain in config.get("official_domains", [])
    ]

    return any(host == domain or host.endswith(f".{domain}") for domain in official_domains)


def classify_topic_type(candidate: ArticleCandidate, config: dict[str, Any]) -> str:
    if is_official_source(candidate, config):
        return str(config.get("official_topic_type", "official"))

    text = searchable_candidate_text(candidate)
    rules = config.get("topic_type_rules", {})

    if isinstance(rules, dict):
        for topic_type, terms in rules.items():
            if any(str(term).lower() in text for term in terms):
                return str(topic_type)

    return str(config.get("default_topic_type", "news_update"))


def estimate_confidence(candidate: ArticleCandidate, config: dict[str, Any]) -> float:
    confidence = float(config.get("base_confidence", 0.5))
    confidence += min(candidate.authority * float(config.get("authority_confidence_weight", 0.3)), 0.3)

    if is_official_source(candidate, config):
        confidence += float(config.get("official_confidence_boost", 0.2))

    text = searchable_candidate_text(candidate)

    positive_terms = [str(term).lower() for term in config.get("confidence_positive_terms", [])]
    caution_terms = [str(term).lower() for term in config.get("confidence_caution_terms", [])]

    if any(term in text for term in positive_terms):
        confidence += float(config.get("positive_confidence_boost", 0.1))

    if any(term in text for term in caution_terms):
        confidence -= float(config.get("caution_confidence_penalty", 0.15))

    return round(max(0.0, min(confidence, 1.0)), 2)


def editorial_score(candidate: ArticleCandidate, config: dict[str, Any]) -> float:
    text = searchable_candidate_text(candidate)
    curiosity_terms = [str(term).lower() for term in config.get("curiosity_terms", [])]
    hits = sum(1 for term in curiosity_terms if term in text)
    max_hits = max(int(config.get("curiosity_score_hit_cap", 8)), 1)

    score_weight = float(config.get("editorial_base_score_weight", 0.6))
    confidence_weight = float(config.get("editorial_confidence_weight", 0.25))
    curiosity_weight = float(config.get("editorial_curiosity_weight", 0.15))

    return min(
        1.0,
        candidate.score * score_weight
        + estimate_confidence(candidate, config) * confidence_weight
        + min(hits / max_hits, 1.0) * curiosity_weight,
    )


def extract_entities(candidate: ArticleCandidate, config: dict[str, Any]) -> list[str]:
    text = f"{candidate.title} {candidate.summary} {' '.join(candidate.key_facts)}"
    lower = text.lower()

    entities: list[str] = []

    for entity in config.get("entities", []):
        entity_text = str(entity).strip()
        if entity_text and entity_text.lower() in lower:
            entities.append(entity_text)

    return dedupe_keep_order(entities)[: int(config.get("max_entities", 12))]


def extract_keywords(candidate: ArticleCandidate, config: dict[str, Any]) -> list[str]:
    keywords: list[str] = []
    text = searchable_candidate_text(candidate)

    for term in config.get("relevance_terms", []):
        term_text = str(term).strip()
        if term_text:
            keywords.append(term_text)

    for term in config.get("engagement_keywords", []):
        term_text = str(term).strip()
        if term_text and term_text.lower() in text:
            keywords.append(term_text)

    return dedupe_keep_order(keywords)[: int(config.get("max_keywords", 20))]


def build_structured_why_trending(candidate: ArticleCandidate, config: dict[str, Any]) -> str:
    topic_type = classify_topic_type(candidate, config)
    confidence = estimate_confidence(candidate, config)

    if is_official_source(candidate, config):
        source_note = "an official source"
    else:
        source_note = f"{candidate.source}, weighted by source authority"

    return (
        f"Selected from {source_note} because it scored strongly for freshness, "
        f"relevance, engagement, and uniqueness. Topic type: {topic_type}. "
        f"Confidence: {confidence:.2f}."
    )


def searchable_candidate_text(candidate: ArticleCandidate) -> str:
    return f"{candidate.title} {candidate.summary} {' '.join(candidate.key_facts)} {candidate.text[:2000]}".lower()


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())

    return result


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    clean_query = {
        key: values
        for key, values in query.items()
        if not key.lower().startswith(("utm_", "fbclid", "gclid"))
    }

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            urlencode(clean_query, doseq=True),
            "",
        )
    )


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def trim_sentence(text: str, max_length: int) -> str:
    text = normalize_spaces(text)

    if len(text) <= max_length:
        return text

    clipped = text[:max_length].rsplit(" ", 1)[0].strip()
    sentence_end = max(clipped.rfind("."), clipped.rfind("?"), clipped.rfind("!"))

    if sentence_end > 80:
        return clipped[: sentence_end + 1]

    return clipped


def used_topics_path(config: dict[str, Any]) -> Path:
    channel = str(config.get("channel", "default"))
    return project_path(str(config.get("used_topics_path", f"channels/{channel}/research/used_topics.json")))


def load_used_topics(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = used_topics_path(config)

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def save_used_topic(candidate: ArticleCandidate, config: dict[str, Any]) -> None:
    path = used_topics_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)

    used = load_used_topics(config)
    used.append(
        {
            "title": candidate.title,
            "url": candidate.url,
            "source": candidate.source,
            "published": candidate.published.isoformat(),
            "used_at": now_utc().isoformat(),
        }
    )

    limit = int(config.get("recent_topic_limit", 20))
    used = used[-limit:]

    path.write_text(json.dumps(used, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_recently_used(candidate: ArticleCandidate, config: dict[str, Any]) -> bool:
    used = load_used_topics(config)
    threshold = float(config.get("similarity_block_threshold", 0.82))

    candidate_url = normalize_url(candidate.url)
    candidate_title = normalize_spaces(candidate.title).lower()
    candidate_tokens = token_set(candidate_title)

    for item in used:
        used_url = normalize_url(str(item.get("url", "")))

        if used_url and used_url == candidate_url:
            return True

        used_title = normalize_spaces(str(item.get("title", ""))).lower()

        if used_title and used_title == candidate_title:
            return True

        used_tokens = token_set(used_title)

        if not candidate_tokens or not used_tokens:
            continue

        overlap = len(candidate_tokens & used_tokens) / len(candidate_tokens | used_tokens)

        if overlap >= threshold:
            return True

    return False


def run(topic: str | None = None, channel: str | None = None) -> None:
    config = load_config()

    if topic:
        config["niche"] = topic

    if channel:
        config["channel"] = channel

    if not config.get("enabled", True):
        print("Research agent disabled.")
        return

    candidates = collect_candidates(config)
    score_candidates(candidates, config)

    selected = choose_highest_scoring_article(candidates, config)

    save_outputs(selected, config)
    save_used_topic(selected, config)
    best_effort_database_insert(selected, channel=str(config.get("channel", "default")))

    print("Selected trending topic:")
    print(selected.title)
    print("Publication date:")
    print(selected.published.isoformat())
    print("Source:")
    print(selected.source)
    print("Score breakdown:")

    for key in [
        "freshness_score",
        "authority_score",
        "engagement_score",
        "uniqueness_score",
        "final_score",
    ]:
        print(f"{key}: {selected.score_breakdown.get(key, 0.0):.4f}")


if __name__ == "__main__":
    run()
