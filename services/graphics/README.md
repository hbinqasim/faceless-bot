# Vice Studio Graphics Service

Adds viral gaming Shorts-style graphic captions to the final video.

## Inputs

- `channels/gta6/videos/final/latest_video.mp4`
- `channels/gta6/scripts/latest_script.txt`

## Output

- `channels/gta6/videos/final/latest_video_graphics.mp4`
- timestamped `YYYY-MM-DD_HH-MM-SS_gta6_graphics.mp4`
- `channels/gta6/videos/final/graphics_manifest.json`

## Caption Timing

Segments are timed by word count across the video duration. The default `caption_start_offset_seconds` is `-0.18`, so captions appear slightly before the narration beat. Starts are clamped at zero, and `caption_gap_seconds` adds a small gap between segments.

Protected phrases stay together:

- `GTA 6`
- `VICE CITY`
- `ROCKSTAR`
- `ROCKSTAR GAMES`
- `JASON`
- `LUCIA`
- `LEONIDA`

## Style

Captions use large bold white text, a yellow highlight for the strongest word, thick black outline, subtle shadow, and a rounded translucent box behind the text. The position is consistent at `y_position_ratio: 0.62`, and text dynamically scales down to avoid clipping inside the configured `max_box_width`.
