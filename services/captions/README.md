# Vice Studio Caption Service

## Purpose

The caption service adds animated Shorts-style captions to the final GTA 6 video using the latest script.

## Inputs

Default inputs are configured in `config.json`:

```text
channels/gta6/videos/final/latest_video.mp4
channels/gta6/scripts/latest_script.txt
```

Empty script lines are ignored.

## Timing

Script lines are split into short caption segments of roughly 3-5 words. Timing is distributed across the video duration based on each segment's character length, so long sentences become several quick captions instead of one large sentence on screen.

## Style

Captions are rendered as uppercase bold white text with a thick black outline and subtle shadow. Each segment is limited to a maximum of two lines and is centered in the lower third, around 78% of the 1080x1920 frame height, with safe margins to prevent clipping.

## Outputs

The latest captioned video is written to:

```text
channels/gta6/videos/final/latest_video_captioned.mp4
```

A timestamped copy is also saved:

```text
channels/gta6/videos/final/YYYY-MM-DD_HH-MM-SS_gta6_captioned.mp4
```

The service also writes:

```text
channels/gta6/videos/final/captions_manifest.json
```

The input video's audio is preserved.

## Running

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python services/captions/service.py
```

The service uses Python standard library plus MoviePy.
