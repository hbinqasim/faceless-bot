# Prompt Engineer Agent

## Purpose

The prompt engineer agent first creates deterministic Image Director metadata for every narration scene, then converts that metadata into SDXL-optimized cinematic image prompts.

## Format

Every prompt begins with the reusable quality prefix:

```text
photorealistic, cinematic lighting, Unreal Engine 5, 35mm anamorphic, volumetric lighting, orange-teal grading, ultra detailed, masterpiece, 9:16
```

The prefix is followed by structured visual details from the scene metadata.

## Rules

- Use positive SDXL prompt language.
- Keep prompts as one paragraph.
- Include subject, environment, lighting, camera, composition, atmosphere, color grading, and realism.
- Emphasize concrete visual objects over abstract descriptions.
- Do not include production instructions.
- Do not include narration timing.
- Do not include editing instructions.
- Do not include phrases like `create a 3-second shot`, `hard cut`, `transition`, or `camera pans`.

Save structured metadata to:

```text
channels/gta6/storyboards/latest_storyboard.json
```

The reusable negative prompt is:

```text
office, desk, computer, monitor, camera equipment, studio, filming equipment, text, watermark, logo, blurry, low quality, duplicate, cropped, deformed, ugly, extra limbs, bad anatomy
```
