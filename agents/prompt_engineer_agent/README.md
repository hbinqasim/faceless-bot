# Prompt Engineer Agent

Generates structured Image Director metadata from valid storyboard scenes, then converts that metadata into SDXL-optimized final image prompts.

## Inputs

- `channels/gta6/storyboards/latest_storyboard.txt`

## Output

- `channels/gta6/storyboards/latest_storyboard.json`
- `channels/gta6/images/latest_final_prompts.txt`

`latest_storyboard.json` stores one deterministic metadata object per valid storyboard scene:

```text
scene_number, subject, environment, action, time_of_day, weather, mood,
camera_angle, focal_length, lighting, color_palette, important_objects,
forbidden_objects
```

Each prompt is saved in `Scene N:` format for downstream image generation.

Non-visual storyboard lines are ignored, including `CUT TO:`, `EXT.`, `INT.`, `FADE`, blank lines, and `Follow for more...` CTA lines. Subjects are derived directly from matching storyboard lines, so a storyboard line about a vintage Vice City sign produces a prompt subject about that sign.

Every prompt starts with:

```text
photorealistic, cinematic lighting, Unreal Engine 5, 35mm anamorphic, volumetric lighting, orange-teal grading, ultra detailed, masterpiece, 9:16
```

Each SDXL prompt includes subject, environment, lighting, camera, composition, atmosphere, color grading, and realism. The generator emphasizes concrete visual objects and removes production language such as shot duration, transition notes, narration timing, and editing instructions.

The reusable negative prompt is:

```text
office, desk, computer, monitor, camera equipment, studio, filming equipment, text, watermark, logo, blurry, low quality, duplicate, cropped, deformed, ugly, extra limbs, bad anatomy
```
