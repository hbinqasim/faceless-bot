"""ComfyUI provider for Vice Studio image generation."""

from __future__ import annotations

import json
import random
import time
import uuid
from pathlib import Path
from typing import Any

import requests

try:
    from .provider_base import ProviderBase
except ImportError:  # pragma: no cover - supports direct script execution.
    from provider_base import ProviderBase


class ComfyProvider(ProviderBase):
    """Generate scene images through a running ComfyUI server."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.comfy_url = str(config.get("comfy_url", "http://127.0.0.1:8188")).rstrip("/")
        self.checkpoint = str(config.get("checkpoint", "sd_xl_base_1.0.safetensors"))
        self.width = int(config.get("image_width", 768))
        self.height = int(config.get("image_height", 1344))
        self.steps = int(config.get("steps", 20))
        self.cfg = float(config.get("cfg", 7.0))
        self.sampler_name = str(config.get("sampler_name", "euler"))
        self.scheduler = str(config.get("scheduler", "normal"))
        self.denoise = float(config.get("denoise", 1.0))
        self.negative_prompt = str(
            config.get(
                "negative_prompt",
                "office, desk, computer, monitor, camera equipment, studio, filming equipment, text, watermark, logo, blurry, low quality, duplicate, cropped, deformed, ugly, extra limbs, bad anatomy",
            )
        )
        self.poll_interval_seconds = float(config.get("poll_interval_seconds", 1.0))
        self.timeout_seconds = float(config.get("timeout_seconds", 600))
        self.client_id = str(uuid.uuid4())

    def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(metadata or {})
        scene_number = payload.get("scene_number", "unknown")
        scene_label = str(payload.get("scene_label", Path(output_path).stem))
        image_path = Path(output_path).with_suffix(".png")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = self._metadata_path_for(image_path)
        prompt_id = None

        try:
            seed = random.randint(0, 2**63 - 1)
            workflow = self._build_workflow(prompt, scene_label, seed)
            prompt_response = self._queue_prompt(workflow)
            node_errors = prompt_response.get("node_errors")
            if node_errors:
                raise RuntimeError(self._format_node_errors(node_errors))

            prompt_id = prompt_response.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"ComfyUI did not return a prompt_id: {prompt_response}")

            history_item = self._poll_history(str(prompt_id))
            history_error = self._extract_history_error(history_item)
            if history_error:
                raise RuntimeError(history_error)

            image_info = self._find_generated_image(history_item)
            if image_info is None:
                raise RuntimeError("ComfyUI completed but no generated image was found in history.")

            self._download_image(image_info, image_path)

            payload.update(
                {
                    "provider": "comfy",
                    "status": "generated",
                    "image_path": str(image_path),
                    "metadata_path": str(metadata_path),
                    "prompt_id": prompt_id,
                    "comfy_url": self.comfy_url,
                    "checkpoint": self.checkpoint,
                    "width": self.width,
                    "height": self.height,
                    "steps": self.steps,
                    "cfg": self.cfg,
                    "sampler_name": self.sampler_name,
                    "scheduler": self.scheduler,
                    "denoise": self.denoise,
                    "negative_prompt": self.negative_prompt,
                    "seed": seed,
                    "comfy_image": image_info,
                }
            )
            metadata_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            return {
                "image_path": str(image_path),
                "metadata_path": str(metadata_path),
                "prompt_id": prompt_id,
                "status": "generated",
            }
        except Exception as error:
            self._print_comfy_error(scene_number, prompt_id, str(error))
            raise

    def _build_workflow(self, prompt: str, scene_label: str, seed: int) -> dict[str, Any]:
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": self.checkpoint,
                },
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 1],
                },
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": self.negative_prompt,
                    "clip": ["1", 1],
                },
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": self.width,
                    "height": self.height,
                    "batch_size": 1,
                },
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": self.steps,
                    "cfg": self.cfg,
                    "sampler_name": self.sampler_name,
                    "scheduler": self.scheduler,
                    "denoise": self.denoise,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 2],
                },
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": f"vice_studio_{scene_label}",
                    "images": ["6", 0],
                },
            },
        }

    def _queue_prompt(self, workflow: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.comfy_url}/prompt",
            json={"prompt": workflow, "client_id": self.client_id},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"ComfyUI /prompt failed: {response.status_code} {response.text}")
        return response.json()

    def _poll_history(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            response = requests.get(f"{self.comfy_url}/history/{prompt_id}", timeout=30)
            if not response.ok:
                raise RuntimeError(
                    f"ComfyUI /history/{prompt_id} failed: {response.status_code} {response.text}"
                )
            history = response.json()
            history_item = history.get(prompt_id)
            if history_item:
                status = history_item.get("status", {})
                status_text = str(status.get("status_str", "")).lower()
                if (
                    status.get("completed")
                    or history_item.get("outputs")
                    or status_text in {"error", "failed"}
                ):
                    return history_item

            time.sleep(self.poll_interval_seconds)

        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}.")

    def _download_image(self, image_info: dict[str, Any], output_path: Path) -> None:
        params = {
            "filename": image_info.get("filename", ""),
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output"),
        }
        response = requests.get(f"{self.comfy_url}/view", params=params, timeout=120)
        if not response.ok:
            raise RuntimeError(f"ComfyUI /view failed: {response.status_code} {response.text}")

        output_path.write_bytes(response.content)

    @staticmethod
    def _find_generated_image(history_item: dict[str, Any]) -> dict[str, Any] | None:
        outputs = history_item.get("outputs", {})
        for output in outputs.values():
            for image in output.get("images", []):
                if image.get("filename"):
                    return {
                        "filename": image.get("filename"),
                        "subfolder": image.get("subfolder", ""),
                        "type": image.get("type", "output"),
                    }
        return None

    @staticmethod
    def _extract_history_error(history_item: dict[str, Any]) -> str | None:
        status = history_item.get("status", {})
        status_text = str(status.get("status_str", "")).lower()
        if status_text and status_text not in {"success", "completed"}:
            messages = status.get("messages", [])
            details = []
            for message in messages:
                if isinstance(message, list) and len(message) > 1 and isinstance(message[1], dict):
                    item = message[1]
                    if item.get("exception_message"):
                        details.append(str(item["exception_message"]))
                    elif item.get("exception_type"):
                        details.append(str(item["exception_type"]))
            detail_text = "; ".join(details) if details else "No detailed error message returned."
            return f"ComfyUI status {status.get('status_str')}: {detail_text}"
        return None

    @staticmethod
    def _format_node_errors(node_errors: Any) -> str:
        if not node_errors:
            return "ComfyUI returned node validation errors."
        try:
            return "ComfyUI node validation errors: " + json.dumps(
                node_errors,
                indent=2,
                ensure_ascii=False,
            )
        except TypeError:
            return f"ComfyUI node validation errors: {node_errors}"

    @staticmethod
    def _metadata_path_for(image_path: Path) -> Path:
        return image_path.with_name(f"{image_path.stem}_metadata.json")

    @staticmethod
    def _print_comfy_error(scene_number: Any, prompt_id: Any, message: str) -> None:
        print("ComfyUI generation error:")
        print(f"- scene number: {scene_number}")
        print(f"- prompt_id: {prompt_id if prompt_id else 'unavailable'}")
        print(f"- error message: {message}")
        print("- recommendation: switch config.json provider back to placeholder if needed.")
