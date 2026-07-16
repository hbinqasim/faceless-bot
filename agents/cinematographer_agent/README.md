# cinematographer_agent

## Purpose

The cinematographer agent reads storyboard scenes and generates detailed cinematography directions for each shot. It provides technical specifications including camera, lens, lighting, color grade, atmosphere, motion, and transitions optimized for vertical YouTube Shorts production.

## Inputs

- storyboard scenes from `channels/gta6/storyboards/latest_storyboard.txt`
- configuration values from `config.json`

## Outputs

- `channels/gta6/storyboards/latest_cinematography.txt`
- timestamped archive copy in `channels/gta6/storyboards/`
- printed cinematography directions to console

## Cinematography Specifications

- Camera: ARRI Alexa 65
- Lens: Anamorphic
- Framing: Vertical 9:16
- Color Grade: Orange-teal
- Atmosphere: Neon reflections, humid Miami crime drama
- Style: Documentary trailer feel
- Mood: Cinematic, professional

## Safety Rules

- no exact GTA logos or official UI
- no claims of official footage
- no script lines in directions
- no new story facts created
- visual and technical specifications only

## Limitations

- depends on Ollama running locally at `http://localhost:11434/api/generate`
- relies on prompt-based generation and local model output
- cinematography directions are text descriptions; actual filming/generation happens downstream
- no direct integration with production tools
