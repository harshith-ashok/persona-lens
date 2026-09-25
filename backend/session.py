"""Session state machine: open -> processing -> ended -> resolved (or failed).

A session is one encounter (vision or audio-only). It ends with a transcript and
summary; if the other person is unknown it stays `ended` (person_id null) until
`finalize_session` names them, which moves it to `resolved`.
"""
import base64
import io
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from PIL import Image

from db import ensure_patient, supabase
from face import add_face_bytes, add_face_logic
from llm import generate_summary
import events
import host
import config
import memory
import voice
from speech import insert_log, save_upload, transcribe_full, upsert_summary

MODES = ("vision", "audio")

# how much each kind of relationship counts toward "how close is this person"
RELATION_WEIGHT = {"spouse": 6, "daughter": 6, "son": 6, "grandchild": 6, "sibling": 6, "caregiver": 4,
                   "friend": 3, "neighbor": 2}


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_session(session_id: str, patient_id: str) -> dict:
    res = supabase.table("sessions").select("*") \
        .eq("id", session_id).eq("patient_id", patient_id).limit(1).execute()
    if not res.data:
        raise HTTPException(404, "Session not found")
    return res.data[0]


def _parse_vector(v):
    return json.loads(v) if isinstance(v, str) else v


def _load_voices(patient_id: str):
    """Host embedding and all named persons' voice embeddings for this patient."""
    host = supabase.table("host_voice_profile").select("embedding") \
        .eq("patient_id", patient_id).limit(1).execute().data
    host_emb = _parse_vector(host[0]["embedding"]) if host else None

    rows = supabase.table("known_persons").select("id, name, voice_embedding") \
        .eq("patient_id", patient_id).eq("is_self", False) \
        .not_.is_("voice_embedding", "null").execute().data
    known = [{"person_id": r["id"], "name": r["name"],
              "embedding": _parse_vector(r["voice_embedding"])} for r in rows]
    return host_emb, known


def _speaker_lines(lines: list[dict], host_name: str | None = None) -> str:
    def label(speaker):
        if speaker == "host":
            return host_name or "Host"
        return "Other" if speaker == "other" else speaker
    return "\n".join(f"{label(l['speaker'])}: {l['text']}" for l in lines if l["text"])


async def enroll_host(patient_id: str, audio: UploadFile, default_name: str | None = None) -> dict:
    ensure_patient(patient_id)
    path = await save_upload(audio)
    try:
        embedding = voice.enroll(path)
    finally:
        os.remove(path)
    supabase.table("host_voice_profile").upsert({
        "patient_id": patient_id,
        "embedding": embedding.tolist(),
    }).execute()
    host.mirror_voice(patient_id, embedding.tolist(), default_name)   # the host's person carries the voice too
    return {"enrolled": True}


def start_session(patient_id: str, mode: str, person_id: str | None = None) -> dict:
    if mode not in MODES:
        raise HTTPException(400, f"mode must be one of {MODES}")

    # Same behavior as /person: make sure the patient row exists
    ensure_patient(patient_id)

    res = supabase.table("sessions").insert({
        "patient_id": patient_id,
        "mode": mode,
        "person_id": person_id,
    }).execute()
    return res.data[0]


def _streamed_audio_to_wav(session_id: str) -> str:
    """Audio streamed over /ws/live (raw 16 kHz mono PCM16) -> a wav file for processing."""
    import live
    import numpy as np
    import soundfile as sf
    import tempfile

    raw = live.audio_path(session_id)
    if not os.path.exists(raw) or os.path.getsize(raw) == 0:
        raise HTTPException(400, "No audio: upload a recording or stream it over /ws/live first")
    pcm = np.fromfile(raw, dtype="<i2")
    os.remove(raw)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        sf.write(tmp.name, pcm, live.SAMPLE_RATE, subtype="PCM_16")
        return tmp.name


def _thumb_b64(img_bytes: bytes, side: int = 640) -> str:
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


async def save_video(patient_id: str, session_id: str, video: UploadFile) -> str:
    """Store the session's video on this machine; returns the file name."""
    ext = "mp4" if "mp4" in (video.content_type or "") else "webm"
    name = f"{session_id}.{ext}"
    folder = os.path.join(config.VIDEO_DIR, patient_id)
    os.makedirs(folder, exist_ok=True)
    limit, size = int(config.VIDEO_MAX_MB * 1024 * 1024), 0
    path = os.path.join(folder, name)
    with open(path, "wb") as out:
        while chunk := await video.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                os.remove(path)
                raise HTTPException(413, f"Video is larger than {config.VIDEO_MAX_MB:g} MB")
            out.write(chunk)
    _add_duration(path)
    return name


def _add_duration(path: str) -> None:
    """Browser-recorded video has no length or seek index, so players can't show or seek it.
    Re-packaging (no re-encoding) writes them in. Best effort: the original is kept on any failure."""
    fixed = path + ".fixed"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-c", "copy",
                        "-f", "mp4" if path.endswith(".mp4") else "webm", fixed],
                       check=True, timeout=120)
        os.replace(fixed, path)
    except Exception as e:
        print("Video remux skipped:", e)
        if os.path.exists(fixed):
            os.remove(fixed)


def video_path(patient_id: str, session: dict) -> str | None:
    name = session.get("video_name")
    path = os.path.join(config.VIDEO_DIR, patient_id, name) if name else None
    return path if path and os.path.exists(path) else None


async def end_session(session_id: str, patient_id: str, audio: UploadFile | None,
                      person_id: str | None = None, face_image: UploadFile | None = None,
                      video: UploadFile | None = None) -> dict:
    """Accepts the recording and returns immediately; transcription, diarization and the summary
    run in `process_session` (see `get_result` for polling)."""
    session = get_session(session_id, patient_id)
    if session["status"] != "open":
        raise HTTPException(409, f"Session is already {session['status']}")

    if audio is not None:
        path = await save_upload(audio)
        try:  # an upload wins over anything streamed; drop the leftover stream
            import live
            os.remove(live.audio_path(session_id))
        except (FileNotFoundError, ImportError):
            pass
    else:
        path = _streamed_audio_to_wav(session_id)
    update = {"status": "processing", "ended_at": _now()}
    if face_image is not None:
        update["face_image_b64"] = _thumb_b64(await face_image.read())
    if video is not None:
        update["video_name"] = await save_video(patient_id, session_id, video)
    supabase.table("sessions").update(update).eq("id", session_id).execute()
    return {"session_id": session_id, "status": "processing", "path": path,
            "person_id": person_id or session["person_id"], "mode": session["mode"]}


def process_session(session_id: str, patient_id: str, path: str, mode: str,
                    person_id: str | None) -> None:
    """Background job: transcribe + diarize (in parallel), summarize, persist, mark the session done."""
    timings = {}
    try:
        t0 = time.perf_counter()
        host_name = host.display_name(patient_id)

        def timed(name, fn):
            def run():
                t = time.perf_counter()
                try:
                    return fn()
                finally:
                    timings[name] = round(time.perf_counter() - t, 2)
            return run

        def diarize():
            host_emb, known = _load_voices(patient_id)
            return voice.label_speakers(path, host_emb, known)

        with ThreadPoolExecutor(max_workers=2) as pool:
            transcription = pool.submit(timed("transcribe", lambda: transcribe_full(path)))
            diarization = pool.submit(timed("diarize", diarize))
            result = transcription.result()

            other_embedding, lines = None, None
            try:  # speaker labelling is best-effort: without HF_TOKEN/pyannote we keep the plain transcript
                labelled = diarization.result()
                lines = voice.assign_transcript(result["segments"], labelled["segments"])
                for line in lines:   # a display name for every line: the host's own, or a known person's
                    line["name"] = host_name if line["speaker"] == "host" else (
                        None if line["speaker"] == "other" else line["speaker"])
                other_embedding = labelled["other_embedding"]
                person_id = person_id or labelled["matched_person_id"]  # recognized by voice
            except Exception as e:
                print("Diarization skipped:", e)

        transcript = _speaker_lines(lines, host_name) if lines else result["text"]

        t = time.perf_counter()
        summary = generate_summary(transcript) if transcript else None
        timings["summary"] = round(time.perf_counter() - t, 2)

        log_id = insert_log(patient_id, person_id, transcript, session_id=session_id, mode=mode)
        if person_id and summary:
            upsert_summary(person_id, summary, log_id)

        timings["total"] = round(time.perf_counter() - t0, 2)
        supabase.table("sessions").update({
            "status": "resolved" if person_id else "ended",
            "person_id": person_id,
            "summary": summary,
            "transcript_segments": lines,
            "other_voice_embedding": other_embedding.tolist() if other_embedding is not None else None,
            "timings": timings,
        }).eq("id", session_id).execute()
        started_at = _now()
        try:  # searchable memory is best-effort; a failure here must not fail the session
            started = supabase.table("sessions").select("started_at").eq("id", session_id).limit(1).execute().data
            started_at = started[0]["started_at"] if started else _now()
            memory.index_session(patient_id, session_id, person_id, started_at, transcript, summary)
        except Exception as e:
            print("Memory indexing skipped:", e)
        try:  # decisions, activities, events, money and to-dos found in what was said
            events.save_session_events(patient_id, session_id, person_id,
                                       events.extract(transcript, host_name, memory._parse_dt(started_at)))
        except Exception as e:
            print("Timeline extraction skipped:", e)
        print(f"Session {session_id} processed: {timings}")

    except Exception as e:
        print("Session processing failed:", e)
        supabase.table("sessions").update({"status": "failed", "error": str(e)[:500], "timings": timings}) \
            .eq("id", session_id).execute()
    finally:
        if os.path.exists(path):
            os.remove(path)


def get_result(session_id: str, patient_id: str, include_face: bool = False) -> dict:
    """Current state of a session; once processing finishes it carries the full result."""
    session = get_session(session_id, patient_id)
    out = {"session_id": session_id, "status": session["status"], "mode": session["mode"]}

    if session["status"] == "failed":
        out["error"] = session.get("error")
    if session["status"] not in ("ended", "resolved"):
        return out

    person_id, person_name = session["person_id"], None
    if person_id:
        row = supabase.table("known_persons").select("name").eq("id", person_id).limit(1).execute().data
        person_name = row[0]["name"] if row else None

    log = supabase.table("interaction_logs").select("id, transcript") \
        .eq("session_id", session_id).order("occurred_at", desc=True).limit(1).execute().data
    lines = session.get("transcript_segments")

    started, ended = _parse_ts(session["started_at"]), _parse_ts(session["ended_at"])
    return {**out,
        "person_id": person_id,
        "person_name": person_name,
        "needs_naming": person_id is None,
        # True/False once diarization ran; None when it was unavailable
        "other_speaker_detected": (session.get("other_voice_embedding") is not None) if lines is not None else None,
        "transcript": log[0]["transcript"] if log else "",
        "summary": session["summary"],
        "log_id": log[0]["id"] if log else None,
        "segments": lines,
        "durationSec": int((ended - started).total_seconds()) if started and ended else None,
        "timings": session.get("timings"),
        "has_face": bool(session.get("face_image_b64")),
        "has_video": bool(session.get("video_name")),
        **({"face_image_b64": session.get("face_image_b64")} if include_face else {}),
    }


def fail_interrupted() -> None:
    """Sessions left in `processing` by a restart will never finish."""
    supabase.table("sessions").update({"status": "failed", "error": "Server restarted during processing"}) \
        .eq("status", "processing").execute()


async def finalize_session(session_id: str, patient_id: str, name: str | None,
                           relationship: str | None, face_image: UploadFile | None = None,
                           person_id: str | None = None, use_session_face: bool = False) -> dict:
    """Attach an unidentified session to a person: a new one (name) or an existing one (person_id).
    Back-fills the session's logs and summary, and saves the voice (and optionally face) for next time."""
    session = get_session(session_id, patient_id)
    if session["status"] != "ended" or session["person_id"]:
        raise HTTPException(409, "Session is not waiting for a name")

    if person_id:
        rows = supabase.table("known_persons").select("*") \
            .eq("id", person_id).eq("patient_id", patient_id).limit(1).execute().data
        if not rows:
            raise HTTPException(404, "Person not found")
        person = rows[0]
        if person.get("is_self"):
            raise HTTPException(400, "That person is you")
    else:
        if not name or not name.strip():
            raise HTTPException(400, "A name is required")
        person = supabase.table("known_persons").insert({
            "patient_id": patient_id,
            "name": name.strip(),
            "relationship": relationship,
        }).execute().data[0]
        person_id = person["id"]

    logs = supabase.table("interaction_logs") \
        .update({"known_person_id": person_id}) \
        .eq("session_id", session_id).execute().data

    if session.get("summary") and logs:
        upsert_summary(person_id, session["summary"], logs[-1]["id"])

    supabase.table("sessions").update({
        "person_id": person_id,
        "status": "resolved",
    }).eq("id", session_id).execute()
    try:
        memory.set_person(session_id, person_id)
    except Exception as e:
        print("Memory update skipped:", e)

    # keep the first voice print we have for someone; an existing one isn't overwritten
    if session.get("other_voice_embedding") and not person.get("voice_embedding"):
        supabase.table("known_persons").update({
            "voice_embedding": _parse_vector(session["other_voice_embedding"]),
        }).eq("id", person_id).execute()

    face_added = None
    if face_image is not None:
        face_added = bool(await add_face_logic(face_image, person_id))
    elif use_session_face and session.get("face_image_b64"):
        face_added = bool(add_face_bytes(base64.b64decode(session["face_image_b64"]), person_id))

    return {"person": person, "session_id": session_id, "face_added": face_added}

def _parse_ts(value):
    if not value:
        return None
    # Python 3.10's fromisoformat needs exactly 3 or 6 fractional digits; Postgres trims zeros
    value = re.sub(r"\.(\d+)", lambda m: "." + m.group(1).ljust(6, "0")[:6], value.replace("Z", "+00:00"))
    return datetime.fromisoformat(value)


def list_people(patient_id: str) -> list[dict]:
    persons = supabase.table("known_persons").select("id, name, relationship") \
        .eq("patient_id", patient_id).eq("is_self", False).execute().data
    if not persons:
        return []
    ids = [p["id"] for p in persons]

    summaries = {r["known_person_id"]: r for r in supabase.table("interaction_summaries")
                 .select("*").in_("known_person_id", ids).execute().data}
    counts = {}
    for r in supabase.table("sessions").select("person_id").in_("person_id", ids).execute().data:
        counts[r["person_id"]] = counts.get(r["person_id"], 0) + 1

    now = datetime.now(timezone.utc)
    recent = {}
    for r in supabase.table("sessions").select("person_id, started_at").in_("person_id", ids).execute().data:
        if (now - _parse_ts(r["started_at"])).days <= 30:
            recent[r["person_id"]] = recent.get(r["person_id"], 0) + 1

    def relevance(p):
        """How much this person matters in the patient's life: who they are, and how often they show up."""
        base = RELATION_WEIGHT.get((p["relationship"] or "").lower(), 1)
        last = summaries.get(p["id"], {}).get("last_occurred_at")
        days_since = (now - _parse_ts(last)).days if last else None
        recency = 0 if days_since is None else 3 if days_since <= 7 else 1 if days_since <= 30 else 0
        score = base + 3 * min(recent.get(p["id"], 0), 5) + 0.5 * min(counts.get(p["id"], 0), 10) + recency
        label = "Very close" if score >= 16 else "Regular" if score >= 8 else "Occasional"
        return {"label": label, "score": round(score, 1), "sessions_30d": recent.get(p["id"], 0)}

    return [{
        "id": p["id"],
        "name": p["name"],
        "relation": p["relationship"],
        "relevance": relevance(p),
        "firstSummary": summaries.get(p["id"], {}).get("first_summary"),
        "lastSummary": summaries.get(p["id"], {}).get("last_summary"),
        "lastSeen": summaries.get(p["id"], {}).get("last_occurred_at"),
        "sessions": counts.get(p["id"], 0),
    } for p in persons]


def list_sessions(patient_id: str, limit: int = 50) -> list[dict]:
    rows = supabase.table("sessions") \
        .select("id, mode, status, summary, started_at, ended_at, person_id, transcript_segments, video_name, known_persons(name)") \
        .eq("patient_id", patient_id).neq("status", "open") \
        .order("started_at", desc=True).limit(limit).execute().data

    out = []
    for r in rows:
        host = other = 0
        for line in r.get("transcript_segments") or []:
            if line["speaker"] == "host":
                host += len(line["text"])
            else:
                other += len(line["text"])
        total = host + other
        started, ended = _parse_ts(r["started_at"]), _parse_ts(r["ended_at"])
        out.append({
            "id": r["id"],
            "mode": r["mode"],
            "status": r["status"],
            "date": r["started_at"],
            "durationSec": int((ended - started).total_seconds()) if started and ended else None,
            "personId": r["person_id"],
            "personName": (r.get("known_persons") or {}).get("name"),
            "summary": r["summary"],
            "hasVideo": bool(r.get("video_name")),
            "hostPct": round(host / total * 100) if total else None,
        })
    return out
