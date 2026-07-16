import time
import uuid
import requests

COMFY_URL = "http://127.0.0.1:8188"

prompt = """
Ultra photorealistic cinematic aerial view of a Miami-inspired coastal metropolis at sunset,
neon reflections on the bay, palm trees, luxury yachts, orange teal color grade,
dramatic clouds, volumetric lighting, vertical 9:16 composition, no text, no logo, no watermark.
"""

workflow = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "sd_xl_base_1.0.safetensors"
        }
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": prompt,
            "clip": ["1", 1]
        }
    },
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "text, watermark, logo, blurry, low quality",
            "clip": ["1", 1]
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
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
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
            "filename_prefix": "vice_studio_sdxl_test"
        }
    }
}

client_id = str(uuid.uuid4())

r = requests.post(
    f"{COMFY_URL}/prompt",
    json={"prompt": workflow, "client_id": client_id},
    timeout=30
)

print("Status:", r.status_code)
print(r.text)
