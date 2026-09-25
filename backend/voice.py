"""Speaker enrollment, diarization and voice matching (pyannote.audio, runs locally).

Needs HF_TOKEN in the environment (backend/.env) and accepted model terms on Hugging Face for
`pyannote/speaker-diarization-community-1` and `pyannote/wespeaker-voxceleb-resnet34-LM`.
"""
import os
import subprocess
import tempfile
import threading
from collections import defaultdict

import numpy as np
import soundfile as sf
import torch
from dotenv import load_dotenv

import config

MIN_SEGMENT_SECONDS = 0.5

_pipeline = None
_embedder = None
_force_cpu = False
_lock = threading.RLock()  # pyannote models aren't thread-safe; concurrent sessions take turns


def _device() -> torch.device:
    if _force_cpu:
        return torch.device("cpu")
    pref = config.VOICE_DEVICE
    if pref != "auto":
        return torch.device(pref)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _token():
    if not config.HF_TOKEN:
        raise RuntimeError("HF_TOKEN is not set (needed for pyannote.audio models)")
    return config.HF_TOKEN


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from pyannote.audio import Pipeline
        _pipeline = Pipeline.from_pretrained(config.DIARIZATION_MODEL, token=_token())
        _pipeline.to(_device())
    return _pipeline


def _get_embedder():
    global _embedder
    if _embedder is None:
        from pyannote.audio import Model, Inference
        model = Model.from_pretrained(config.EMBEDDING_MODEL, token=_token())
        _embedder = Inference(model, window="whole", device=_device())
    return _embedder


def _on_device_with_cpu_fallback(fn):
    """Run fn on the accelerator; if it fails there (unsupported op etc.), retry once on CPU."""
    global _pipeline, _embedder, _force_cpu
    try:
        return fn()
    except Exception as e:
        if _device().type == "cpu":
            raise
        print(f"Voice models failed on {_device()}, falling back to CPU:", e)
        _force_cpu = True
        _pipeline = _embedder = None
        return fn()


def warmup():
    """Load the models and run them once so the first real session doesn't pay the compile cost."""
    audio = {"waveform": torch.randn(1, 16000 * 5) * 0.01, "sample_rate": 16000}

    def run():
        _get_pipeline()(audio)
        _embed(audio)

    _on_device_with_cpu_fallback(run)


def load_audio(path: str) -> dict:
    """Decode any audio file (browser webm/ogg included) to 16 kHz mono via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-ac", "1", "-ar", "16000", wav],
            check=True,
        )
        data, sr = sf.read(wav, dtype="float32")
    finally:
        os.remove(wav)
    return {"waveform": torch.from_numpy(data).unsqueeze(0), "sample_rate": sr}


def _embed(audio: dict, start: float | None = None, end: float | None = None) -> np.ndarray:
    wf, sr = audio["waveform"], audio["sample_rate"]
    if start is not None:
        wf = wf[:, int(start * sr):int(end * sr)]
    emb = _on_device_with_cpu_fallback(lambda: _get_embedder()({"waveform": wf, "sample_rate": sr}))
    return np.asarray(emb, dtype=np.float32)


def cosine_distance(a, b) -> float:
    a, b = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    return float(1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def enroll(path: str) -> np.ndarray:
    """Audio of one speaker -> speaker embedding."""
    return _embed(load_audio(path))


def diarize(audio: dict) -> list[dict]:
    """Audio -> [{start, end, speaker}] time-stamped segments (speaker labels are per-file)."""
    out = _on_device_with_cpu_fallback(lambda: _get_pipeline()(audio))
    annotation = getattr(out, "speaker_diarization", out)  # pyannote 4 wraps the annotation
    return [
        {"start": float(turn.start), "end": float(turn.end), "speaker": label}
        for turn, _, label in annotation.itertracks(yield_label=True)
    ]


def _classify(emb, host_embedding, known_voices):
    """-> (label, person_id) for one embedding: host, a known person, or other."""
    if host_embedding is not None and cosine_distance(emb, host_embedding) < config.VOICE_MATCH_THRESHOLD:
        return "host", None
    best, best_dist = None, config.VOICE_MATCH_THRESHOLD
    for voice in known_voices or []:
        dist = cosine_distance(emb, voice["embedding"])
        if dist < best_dist:
            best, best_dist = voice, dist
    return (best["name"], best["person_id"]) if best else ("other", None)


def label_speakers(path: str, host_embedding=None, known_voices: list[dict] | None = None) -> dict:
    """Diarize, then name every segment by its own voice.

    Each segment is matched individually (not per diarization cluster) because clustering tends to
    merge speakers on short clips. known_voices: [{"person_id", "name", "embedding"}]. Returns
    {"segments": [{start, end, speaker, label, person_id}], "other_embedding": np.ndarray | None,
     "matched_person_id": str | None}.
    """
    audio = load_audio(path)
    with _lock:
        return _label(audio, host_embedding, known_voices)


def _label(audio, host_embedding, known_voices):
    segments = diarize(audio)

    other = []   # (duration, embedding) of segments nobody matched
    for seg in segments:
        duration = seg["end"] - seg["start"]
        if duration < MIN_SEGMENT_SECONDS:
            seg["label"], seg["person_id"] = "other", None
            continue
        emb = _embed(audio, seg["start"], seg["end"])
        seg["label"], seg["person_id"] = _classify(emb, host_embedding, known_voices)
        if seg["label"] == "other":
            other.append((duration, emb))

    matched = next((s["person_id"] for s in segments if s["person_id"]), None)
    other_embedding = max(other, key=lambda x: x[0])[1] if other else None
    return {"segments": segments, "other_embedding": other_embedding, "matched_person_id": matched}


def assign_transcript(whisper_segments: list[dict], speaker_segments: list[dict]) -> list[dict]:
    """Give each Whisper segment the speaker label with the largest time overlap."""
    lines = []
    for ws in whisper_segments:
        overlap = defaultdict(float)
        for ss in speaker_segments:
            o = min(ws["end"], ss["end"]) - max(ws["start"], ss["start"])
            if o > 0:
                overlap[(ss["label"], ss["person_id"])] += o
        label, pid = max(overlap, key=overlap.get) if overlap else ("other", None)
        lines.append({"start": ws["start"], "end": ws["end"], "speaker": label,
                      "person_id": pid, "text": ws["text"].strip()})
    return lines
