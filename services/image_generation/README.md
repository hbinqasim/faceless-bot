# Vice Studio Image Generation Service

## Purpose

This service prepares image generation outputs from finalized Vice Studio scene prompts. It is provider-agnostic, so the prompt parsing and manifest logic stay the same while different image generation backends can be added later.

## Inputs

The default input is configured in `config.json`:

```text
channels/gta6/images/latest_final_prompts.txt
```

Prompts are expected to use scene headers like `Scene 1:`. Wrapped prompt lines are supported.

## Outputs

The default output folder is:

```text
channels/gta6/images/generated/
```

For each scene, the manual provider writes:

```text
scene_01_prompt.txt
scene_01_metadata.json
```

The placeholder provider writes test JPG frames:

```text
scene_01.jpg
scene_01_metadata.json
```

The ComfyUI provider writes generated PNG frames:

```text
scene_01.png
scene_01_metadata.json
```

The service also writes:

```text
generation_manifest.json
```

The manifest records the service config, prepared count, scene numbers, prompt paths, metadata paths, and status for each scene.

## Provider System

Providers inherit from `ProviderBase` and implement:

```python
generate_image(prompt, output_path, metadata=None)
```

The service chooses the provider from `config.json`.

## Manual Provider

`ManualProvider` exists so the pipeline can be tested before connecting an external image API. It creates prompt files and metadata files, but does not generate raster images yet. This makes it useful for review, handoff, and validating prompt parsing.

## Placeholder Provider

`PlaceholderProvider` creates simple test JPG images from the prompts. Use it when downstream animation or composition needs real image files but no AI image backend is ready.

## ComfyUI Provider

`ComfyProvider` sends each prompt to a running ComfyUI server and downloads the generated image. The current working provider is SDXL via ComfyUI. The default config expects ComfyUI at:

```text
http://127.0.0.1:8188
```

The default workflow uses:

- `CheckpointLoaderSimple`
- `CLIPTextEncode`
- `EmptyLatentImage`
- `KSampler`
- `VAEDecode`
- `SaveImage`

The default checkpoint is:

```text
sd_xl_base_1.0.safetensors
```

FLUX FP8 failed on Apple MPS because the backend does not support the required FP8 dtype. SDXL is the current Mac-compatible provider for this project. If ComfyUI returns a model or runtime error, switch `"provider"` back to `"placeholder"` to keep testing the rest of the pipeline, or update the ComfyUI model/config later to a checkpoint that runs reliably on the machine.

ComfyUI errors are printed with the scene number, prompt id when available, and the returned error message.

## Adding Future Providers

To add a provider:

1. Create a new provider class that inherits from `ProviderBase`.
2. Implement `generate_image()`.
3. Register it in `get_provider()` in `service.py`.
4. Set `"provider"` in `config.json` to the new provider name.

Future providers can call an image API, save generated images to the requested output path, and return metadata such as API model, seed, dimensions, and final image path.
