# Vice Studio Video Composer Service

## Purpose

The video composer service combines animated scene clips into one complete vertical video.

## Input

By default, the service reads scene clips from:

```text
channels/gta6/videos/scenes/
```

It looks for files named:

```text
scene_01.mp4
scene_02.mp4
```

Scene clips are sorted numerically before composition.

## Output

The service writes the latest final video to:

```text
channels/gta6/videos/final/latest_video.mp4
```

It also saves a timestamped copy:

```text
channels/gta6/videos/final/YYYY-MM-DD_HH-MM-SS_gta6_video.mp4
```

The service writes a manifest:

```text
channels/gta6/videos/final/composition_manifest.json
```

## Voiceover

The composer can attach narration audio from:

```text
channels/gta6/audio/voice.mp3
```

When `use_voiceover` is `true` and the audio file exists, the final video audio is replaced with the voiceover. The final duration is matched to the voiceover duration: longer videos are trimmed, and shorter videos are extended by freezing the last scene frame.

If the audio file is missing, the composer prints a warning and writes the silent composition as before.

## Transitions

The configured transition is a short fade between scene clips. The default is `0.25` seconds.

## Running

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python services/video_composer/service.py
```

The service uses Python standard library plus MoviePy.
