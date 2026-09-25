"""Guided voice enrollment ("say this sentence"): like setting up a voice assistant.

The app shows a sentence, the user reads it (live captions show what was understood, see /ws/live with
purpose "enroll"), and each recording is checked against the sentence before it is accepted. Once
every sentence is accepted the clips are joined and the host's voice print is built from all of them.
"""
import difflib
import os
import re
import shutil
import tempfile

import numpy as np
import soundfile as sf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import host
import speech
import voice
from auth import get_current_user
from db import supabase

router = APIRouter(prefix="/voice", tags=["voice"])

# Everyday sentences with varied sounds; no digits (a transcript would say "5" for "five").
SENTENCES = [
    "The quick brown fox jumps over the lazy dog near the river.",
    "Please remind me who is visiting this afternoon.",
    "My favorite kind of music is quiet piano in the morning.",
    "Thank you for coming, it is so good to see you again.",
    "I would like a cup of warm tea with a little honey.",
]
MIN_SCORE = 0.75        # share of the sentence's words that must be heard, in order
MIN_SECONDS = 1.0       # shorter than this is not a sentence
GAP_SECONDS = 0.3       # silence inserted between clips when they are joined


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def score(target: str, heard: str) -> float:
    """0..1 similarity of the words heard to the words asked for (order-aware)."""
    a, b = _words(target), _words(heard)
    if not a or not b:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 3)


def _dir(patient_id: str) -> str:
    path = os.path.join(tempfile.gettempdir(), "pl_enroll", patient_id)
    os.makedirs(path, exist_ok=True)
    return path


def _clip_path(patient_id: str, index: int) -> str:
    return os.path.join(_dir(patient_id), f"{index}.wav")


def _done(patient_id: str) -> list[int]:
    return [i for i in range(len(SENTENCES)) if os.path.exists(_clip_path(patient_id, i))]


@router.get("/prompts")
def prompts(user=Depends(get_current_user)):
    return {"sentences": SENTENCES, "min_score": MIN_SCORE, "min_seconds": MIN_SECONDS,
            "done": _done(user["sub"])}


@router.post("/enroll/clip")
async def add_clip(index: int = Form(...), audio: UploadFile = File(...), user=Depends(get_current_user)):
    """Check one recording against sentence `index`. Accepted clips are kept until `finish`."""
    patient_id = user["sub"]
    if not 0 <= index < len(SENTENCES):
        raise HTTPException(400, f"index must be 0..{len(SENTENCES) - 1}")

    src = await speech.save_upload(audio)
    try:
        decoded = voice.load_audio(src)                       # any format -> 16 kHz mono
    finally:
        os.remove(src)
    samples = decoded["waveform"].squeeze(0).numpy()
    seconds = len(samples) / decoded["sample_rate"]

    heard = ""
    if seconds >= MIN_SECONDS:
        tmp = os.path.join(_dir(patient_id), f"check_{index}.wav")
        sf.write(tmp, samples, decoded["sample_rate"], subtype="PCM_16")
        try:
            heard = speech.transcribe(tmp)
        finally:
            os.remove(tmp)

    similarity = score(SENTENCES[index], heard)
    ok = seconds >= MIN_SECONDS and similarity >= MIN_SCORE
    if ok:
        sf.write(_clip_path(patient_id, index), samples, decoded["sample_rate"], subtype="PCM_16")

    return {"index": index, "sentence": SENTENCES[index], "transcript": heard, "score": similarity,
            "ok": ok, "seconds": round(seconds, 1), "done": _done(patient_id),
            "complete": len(_done(patient_id)) == len(SENTENCES)}


@router.post("/enroll/finish")
def finish(user=Depends(get_current_user)):
    """Join the accepted clips and build the host's voice print from all of them."""
    patient_id = user["sub"]
    done = _done(patient_id)
    missing = [i for i in range(len(SENTENCES)) if i not in done]
    if missing:
        raise HTTPException(400, f"Sentences still to read: {[m + 1 for m in missing]}")

    parts, rate = [], 16000
    for i in range(len(SENTENCES)):
        data, rate = sf.read(_clip_path(patient_id, i), dtype="int16")
        parts += [data, np.zeros(int(GAP_SECONDS * rate), dtype="int16")]
    joined = os.path.join(_dir(patient_id), "joined.wav")
    sf.write(joined, np.concatenate(parts), rate, subtype="PCM_16")

    with voice._lock:
        embedding = voice.enroll(joined).tolist()

    host.ensure_self_person(patient_id, user["username"])
    supabase.table("host_voice_profile").upsert({"patient_id": patient_id, "embedding": embedding}).execute()
    host.mirror_voice(patient_id, embedding, user["username"])

    shutil.rmtree(_dir(patient_id), ignore_errors=True)
    return {"enrolled": True, "clips": len(SENTENCES)}
