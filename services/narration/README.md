# Vice Studio Narration Service

## Purpose

The narration service reads the latest GTA 6 script and generates a voiceover MP3 using `edge-tts`.

## Input

The default script path is configured in `config.json`:

```text
channels/gta6/scripts/latest_script.txt
```

## Output

The service writes audio and a manifest to:

```text
channels/gta6/audio/
```

Default outputs:

```text
voice.mp3
narration_manifest.json
```

## Voice

The default voice is:

```text
en-US-GuyNeural
```

## Manifest

`narration_manifest.json` includes the input script path, output audio path, voice, creation timestamp, script line count, and the exact script text used for generation.

## Running

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python services/narration/service.py
```

The service uses Python standard library plus `edge-tts`.
