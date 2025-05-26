import os
import base64
import io
import json
import logging

# Disable any network calls for Google GenAI and HF Hub
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
# Transformers no longer respects TRANSFORMERS_CACHE; use HF_HOME instead
cache_dir = os.environ.get("TRANSFORMERS_CACHE")
if cache_dir:
    os.environ.setdefault("HF_HOME", cache_dir)
else:
    os.environ.setdefault(
        "HF_HOME", os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    )

logger = logging.getLogger(__name__)


def extract_display_object(item: dict, source_map: dict) -> dict:
    """
    Convert a raw display object into a standardized structure.
    """
    # Input must be a dict with a 'type'
    if not isinstance(item, dict) or "type" not in item:
        return {"invalid": True}

    # If content is missing, try using 'text' or 'image_url'
    if "content" not in item:
        if "text" in item:
            item["content"] = item["text"]
        elif "image_url" in item:
            item["content"] = item["image_url"]
        else:
            return {"invalid": True}

    obj = {
        "type": item["type"],
        "source": item.get("source", "agent-response"),
        "content": item["content"],
    }
    # Preserve caption for images if provided
    if obj["type"] == "image" and "caption" in item:
        obj["caption"] = item["caption"]
    # If this image has a known source, replace content with the source chunk content
    if obj["type"] == "image" and obj["source"] in source_map:
        obj["content"] = source_map[obj["source"]].get("content", obj["content"])
    return obj



def parse_json(json_output: str) -> str:
    """
    Extract JSON payload from markdown-fenced response.
    """
    lines = json_output.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "```json":
            payload = lines[i+1:]
            # join until closing fence
            joined = []
            for l in payload:
                if l.strip().startswith("```"):
                    break
                joined.append(l)
            return "\n".join(joined)
    return json_output


def scale_and_clamp(val1: float, val2: float, current_scale: float,
                    desired_scale: float, padding_percent: float) -> tuple[int, int]:
    """
    Scale values from one range to another with padding.
    """
    pad_min = 1 - padding_percent/200
    pad_max = 1 + padding_percent/200
    start = int((val1/current_scale) * desired_scale * pad_min)
    end   = int((val2/current_scale) * desired_scale * pad_max)
    return max(start, 0), min(end, int(desired_scale))


def process_single_image(base64_image: str, description: str) -> str:
    """
    Offline stub: return the original image without cropping.
    """
    # We cannot perform bounding-box cropping offline; return unmodified
    logger.debug("process_single_image stub: returning original image content")
    # Strip any data URI prefix
    if base64_image.startswith("data:image/"):
        return base64_image.split(",", 1)[1]
    return base64_image


def crop_images_in_display_objects(display_objects: list) -> list:
    """
    For offline mode, do not attempt network cropping; pass images through as-is.
    """
    for obj in display_objects:
        if obj.get("type") == "image" and "content" in obj:
            # description may be in caption or elsewhere
            desc = obj.get("caption", "")
            obj["content"] = process_single_image(obj["content"], desc)
    return display_objects
