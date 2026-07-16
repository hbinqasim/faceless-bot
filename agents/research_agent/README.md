# research_agent

## Purpose

The research agent is a trending-news researcher for GTA 6. It searches prioritized sources, keeps only articles published within the last 30 days, scores each valid article, and selects one highest-scoring topic for the production pipeline.

## Source Priority

1. Rockstar Games Newswire
2. Take-Two Interactive Investor Relations
3. Rockstar Support
4. IGN
5. GameSpot
6. Eurogamer
7. Insider Gaming
8. Video Games Chronicle (VGC)
9. RockstarINTEL

## Scoring

Each article is scored with:

- freshness: 40%
- authority: 30%
- uniqueness: 20%
- engagement keywords: 10%

Engagement keywords include:

```text
leaked, confirmed, pre-order, preorder, release, trailer, screenshot,
gameplay, Jason, Lucia, Leonida, Rockstar, GTA Online, Take-Two,
billion, record, sales, revealed, discovered, hidden, update
```

## Outputs

The agent selects only the highest-scoring article and writes:

```text
channels/gta6/research/latest_topic.json
channels/gta6/research/latest_article.md
```

`latest_topic.json` contains:

```json
{
  "title": "",
  "url": "",
  "published": "",
  "summary": "",
  "why_trending": "",
  "key_facts": []
}
```

The selected article is also inserted into the database on a best-effort basis for compatibility with downstream fact extraction.

## Console Output

The agent prints:

```text
Selected trending topic:
Publication date:
Source:
```

## Dependencies

- Python standard library
- `requests`
- `beautifulsoup4`
