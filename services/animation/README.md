# Vice Studio Animation Service

## Purpose

The animation service turns generated scene images into short MP4 clips for downstream video composition.

## Input

By default, the service reads generated PNG scene frames from:

```text
channels/gta6/images/generated/
```

It looks for files named:

```text
scene_01.png
scene_02.png
```

## Output

The service writes animated clips to:

```text
channels/gta6/videos/scenes/
```

Each input image creates one MP4:

```text
scene_01.mp4
scene_02.mp4
```

It also writes:

```text
animation_manifest.json
```

The manifest records each input image, output video, duration, scene number, and motion type.

## Motion

Motion varies per scene while keeping the same subtle cinematic pan/zoom effect:

- scene 1: `slow_push`
- scene 2: `pan_right`
- scene 3: `slow_zoom_in`
- scene 4: `pan_left`
- scene 5: `handheld_subtle`
- scene 6: `fast_push`
- scene 7+: `slow_push`

The service applies small zoom and slight x/y pan, with safe overscan so the output does not crop outside the image frame.

## Running

```bash
/Users/hbinqasim/Projects/faceless-bot/venv/bin/python services/animation/service.py
```

The service uses Python standard library plus MoviePy.
