# fact_checker

## Purpose

The fact checker reads article text from the Vice Studio SQLite database, extracts candidate factual claims, classifies those claims with a basic rule-based model, and stores them in the `facts` table.

## Inputs

- raw article text from `articles.raw_text`
- article metadata from `articles.url`
- configuration values from `config.json`

## Outputs

- inserted records in the `facts` table
- printed summary of articles processed and facts inserted

## Categories

- `confirmed`
- `developer_statement`
- `trailer_observation`
- `release_info`
- `speculation`
- `unknown`

## Limitations

- rule-based classification only
- no external AI or advanced NLP
- only processes articles with no existing fact records
- reliance on exact keyword patterns and simple sentence splitting
