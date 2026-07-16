import json
import time
import uuid
import requests

COMFY_URL = "http://127.0.0.1:8188"

PROMPT_TEXT = """
Ultra photorealistic cinematic aerial view of a Miami-inspired coastal metropolis at sunset,
neon reflections on the bay, palm trees, luxury yachts, orange teal color grade,
dramatic clouds, volumetric lighting, vertical 9:16 composition, no text, no logo, no watermark.
"""

workflow = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "FLUX1/flux1-schnell-fp8.safetensors"
        }
    },
    "2": {
        "class_type": "CLIPTextEncodeFlux",
        "inputs": {
            "clip": ["1", 1],
            "clip_l": PROMPT_TEXT,
            "t5xxl": PROMPT_TEXT,
            "guidance": 3.5
        }
    },
    "3": {
        "class_type": "CLIPTextEncodeFlux",
        "inputs": {
            "clip": ["1", 1],
            "clip_l": "text, watermark, logo, blurry, low quality",
            "t5xxl": "text, watermark, logo, blurry, low quality",
            "guidance": 3.5
        }
    },
    "4": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 768,
            "height": 1344,
            "batch_size": 1
        }
    },
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": 123456,
            "steps": 8,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0
        }
    },
    "6": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["5", 0],
            "vae": ["1", 2]
        }
    },
    "7": {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["6", 0],
            "filename_prefix": "vice_studio_test"
        }
    }
}

client_id = str(uuid.uuid4())

response = requests.post(
    f"{COMFY_URL}/prompt",
    json={
        "prompt": workflow,
        "client_id": client_id
    },
    timeout=30
)

print("Status:", response.status_code)
print(response.text)
