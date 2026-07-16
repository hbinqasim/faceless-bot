# image_director

## Purpose

The image director reads storyboard scenes and converts each into a polished, detailed AI image prompt. Each prompt describes original cinematic vertical imagery suitable for AI image generation.

## Inputs

- storyboard scenes from `channels/gta6/storyboards/latest_storyboard.txt`
- configuration values from `config.json`

## Outputs

- `channels/gta6/images/latest_image_prompts.txt`
- timestamped archive copy in `channels/gta6/images/`
- printed prompts to console

## Visual Safety Rules

- no exact GTA logos or official UI
- no copyrighted branding or claims of official footage
- no text overlays or watermarks
- no real celebrities
- original cinematic visual descriptions only
- Miami-inspired crime drama atmosphere
- vertical 9:16 composition
- suitable for AI image generation platforms

## Limitations

- depends on Ollama running locally at `http://localhost:11434/api/generate`
- relies on prompt-based generation and local model output
- prompts are text descriptions; actual image generation happens downstream
- no direct integration with image generation APIs
