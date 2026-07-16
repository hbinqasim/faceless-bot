# script_agent

## Purpose

The script agent generates a short GTA 6 YouTube Shorts documentary script. It uses the latest trending topic when available, then falls back to the verified knowledge brief.

## Inputs

- `channels/gta6/research/latest_topic.json`
- `channels/gta6/research/knowledge_brief.md` as fallback
- configuration values from `config.json`

## Outputs

- `channels/gta6/scripts/latest_script.txt`
- timestamped archive copy in `channels/gta6/scripts/`
- printed script to the console

## Accuracy Rules

- use `latest_topic.json` first when it exists
- use the topic title, summary, why-trending note, and key facts
- fall back to the knowledge brief when no latest topic exists
- do not invent facts
- avoid unverified leaks
- avoid generic evergreen hooks unless directly relevant to the topic
- output must be 6 to 7 spoken lines
- each line must be 4 to 8 words
- the first line must be a strong topic-based hook
- end exactly with: Follow for more GTA 6 breakdowns.

## Limitations

- depends on Ollama running locally at `http://localhost:11434/api/generate`
- relies on prompt-based generation and local model output
- no additional fact verification beyond the brief
