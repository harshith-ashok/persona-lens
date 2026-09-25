"""Cloud face identification via a vision model on Ollama (prompt-based matching).

The model is given reference photos of known people plus one query crop and picks which person
(if any) the query shows. Callers fall back to local dlib matching when this raises.
"""
import json
import re
import time

import requests

from config import OLLAMA_URL, VISION_MODEL, VISION_TIMEOUT, VISION_COOLDOWN as COOLDOWN_SECONDS
# after a failure the cloud is skipped for COOLDOWN_SECONDS so a dead endpoint doesn't stall every frame

_down_until = 0.0


def available() -> bool:
    return time.time() >= _down_until


def _parse(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def identify(query_b64: str, candidates: list[dict]) -> tuple[dict | None, float]:
    """candidates: [{"person_id", "name", "images": [b64, ...]}]. Returns (candidate | None, confidence)."""
    global _down_until

    images, labels = [], []
    for i, c in enumerate(candidates, start=1):
        labels.append(f"Person {i}: images {len(images) + 1}-{len(images) + len(c['images'])}"
                      if len(c["images"]) > 1 else f"Person {i}: image {len(images) + 1}")
        images.extend(c["images"])
    images.append(query_b64)

    prompt = (
        "The first images are reference photos of known people.\n"
        + "\n".join(labels)
        + f"\nImage {len(images)} is a new photo. Decide whether the face in it is the same individual "
          "as one of the known people. Compare facial features only; if you are not sure, answer none.\n"
          'Reply with JSON only: {"match": <person number or "none">, "confidence": <0.0-1.0>}'
    )

    try:
        res = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": VISION_MODEL,
            "stream": False,
            "think": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt, "images": images}],
        }, timeout=VISION_TIMEOUT)
        res.raise_for_status()
        out = _parse(res.json()["message"]["content"])
    except Exception:
        _down_until = time.time() + COOLDOWN_SECONDS
        raise

    match = out.get("match")
    try:
        idx = int(match)
    except (TypeError, ValueError):
        return None, 0.0
    if not 1 <= idx <= len(candidates):
        return None, 0.0
    return candidates[idx - 1], float(min(max(out.get("confidence", 0.0), 0.0), 0.99))
