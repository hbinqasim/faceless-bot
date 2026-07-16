# storyboard_agent

## Purpose

The storyboard agent reads the latest GTA 6 script and generates 6 to 8 visual scene descriptions optimized for AI image generation of a vertical YouTube Short. Each scene describes cinematic visuals only, without voiceover or text.

## Inputs

- latest script from `channels/gta6/scripts/latest_script.txt`
- configuration values from `config.json`

## Outputs

- `channels/gta6/storyboards/latest_storyboard.txt`
- timestamped archive copy in `channels/gta6/storyboards/`
- printed scene list to console

## Visual Safety Rules

- no voiceover, text overlays, subtitles, or logos in scene descriptions
- no GTA logo or exact copyrighted game UI
- no claim that it is official footage
- use "GTA-inspired", "Miami-inspired", "open-world crime game aesthetic" language
- modern Miami crime drama visual style
- neon, humidity, luxury, cinematic documentary feel
- vertical 9:16 aspect ratio composition

## Limitations

- depends on Ollama running locally at `http://localhost:11434/api/generate`
- relies on prompt-based generation and local model output
- visual descriptions are text-based; actual image generation happens downstream
- no direct integration with image generation APIs
