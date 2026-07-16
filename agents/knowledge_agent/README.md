# knowledge_agent

## Purpose

The knowledge agent reads facts from the Vice Studio database, filters and deduplicates them, groups them by category, and generates a readable knowledge brief for the GTA 6 channel.

## Inputs

- facts from `database/vice.db`
- related articles and sources joined from the database
- configuration values from `config.json`

## Outputs

- markdown brief saved to `channels/gta6/research/knowledge_brief.md`
- console summary of facts loaded and deduplicated

## Confidence Filtering

Only facts with confidence >= `min_confidence` are included. This threshold helps keep the brief focused on higher-confidence observations.

## Limitations

- only uses existing facts stored in the database
- does not infer new claims or generate new knowledge beyond stored facts
- deduplication is based on normalized text comparison
- category grouping is rule-based and limited to predefined labels
