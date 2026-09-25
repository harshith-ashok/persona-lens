import os
import tempfile
import threading

import requests

import config
from db import supabase
from llm import generate_summary

_model = None
_model_lock = threading.Lock()
_transcribe_lock = threading.Lock()


def get_whisper():
    """Loads the local Whisper model on first use (or at startup warm-up), not at import."""
    global _model
    with _model_lock:
        if _model is None:
            import whisper
            _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


async def save_upload(file) -> str:
    """Write an uploaded audio file to a temp .wav and return its path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        return tmp.name


def transcribe(path: str) -> str:
    return transcribe_full(path)["text"]


def transcribe_full(path: str) -> dict:
    """Returns {"text", "segments": [{start, end, text}]} from the configured backend."""
    if config.TRANSCRIBE_BACKEND == "openai":
        return _transcribe_openai(path)

    model = get_whisper()
    with _transcribe_lock:
        result = model.transcribe(path, language=config.TRANSCRIBE_LANGUAGE)
    return {
        "text": result.get("text", "").strip(),
        "segments": [{"start": s["start"], "end": s["end"], "text": s["text"]}
                     for s in result.get("segments", [])],
    }


def _transcribe_openai(path: str) -> dict:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("TRANSCRIBE_BACKEND=openai needs OPENAI_API_KEY")
    with open(path, "rb") as f:
        res = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            files={"file": f},
            data={"model": config.OPENAI_TRANSCRIBE_MODEL, "response_format": "verbose_json",
                  "language": config.TRANSCRIBE_LANGUAGE},
            timeout=120,
        )
    res.raise_for_status()
    body = res.json()
    return {
        "text": body.get("text", "").strip(),
        "segments": [{"start": s["start"], "end": s["end"], "text": s["text"]}
                     for s in body.get("segments", [])],
    }


def insert_log(patient_id, person_id, transcript, session_id=None, mode=None) -> str:
    log = supabase.table("interaction_logs").insert({
        "patient_id": patient_id,
        "known_person_id": person_id,
        "transcript": transcript,
        "session_id": session_id,
        "mode": mode,
    }).execute()
    return log.data[0]["id"]


def upsert_summary(person_id, summary, log_id):
    """First interaction sets first_*; every interaction overwrites last_*."""
    existing = supabase.table("interaction_summaries") \
        .select("id") \
        .eq("known_person_id", person_id) \
        .limit(1) \
        .execute()

    if not existing.data:
        supabase.table("interaction_summaries").insert({
            "known_person_id": person_id,
            "first_summary": summary,
            "first_occurred_at": "now()",
            "first_log_id": log_id,
            "last_summary": summary,
            "last_occurred_at": "now()",
            "last_log_id": log_id
        }).execute()
    else:
        supabase.table("interaction_summaries").update({
            "last_summary": summary,
            "last_occurred_at": "now()",
            "last_log_id": log_id
        }).eq("known_person_id", person_id).execute()


async def process_audio(file, patient_id, person_id=None):
    path = None
    try:
        path = await save_upload(file)
        transcript = transcribe(path)

        print("TRANSCRIPT:", transcript)

        summary = generate_summary(transcript) if person_id and transcript else None
        log_id = insert_log(patient_id, person_id, transcript)

        if person_id and summary:
            upsert_summary(person_id, summary, log_id)

        return {
            "transcript": transcript,
            "summary": summary,
            "log_id": log_id
        }

    except Exception as e:
        print("Process audio error:", e)
        return {"error": str(e)}

    finally:
        if path and os.path.exists(path):
            os.remove(path)
