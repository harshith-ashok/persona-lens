import asyncio
import os
import threading

from fastapi import BackgroundTasks, FastAPI, WebSocket, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from auth import get_current_user
from db import ensure_patient, supabase
from face import InvalidImage, add_face_logic, recognize_logic
from speech import process_audio
import session as sessions
import enrollment
import events
import gallery
import host
import live
import memory
import speech

app = FastAPI()
app.include_router(enrollment.router)
app.include_router(events.router)
app.include_router(gallery.router)
app.include_router(host.router)


def _warmup():
    """Load the heavy models in the background so the first session isn't slow."""
    import config
    if not config.WARMUP:
        return
    try:
        sessions.fail_interrupted()
    except Exception as e:
        print("Startup cleanup failed:", e)
    if config.TRANSCRIBE_BACKEND == "local":
        try:
            from speech import get_whisper
            get_whisper()
        except Exception as e:
            print("Whisper warm-up failed:", e)
    try:
        import voice
        voice.warmup()
    except Exception as e:
        print("Voice warm-up skipped:", e)
    print("Warm-up complete")


@app.on_event("startup")
def on_startup():
    threading.Thread(target=_warmup, daemon=True).start()


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# AUTH DEBUG
# =========================


@app.get('/health')
def health():
    return {'status': 200}


@app.get("/me")
def me(user=Depends(get_current_user)):
    return {"patient_id": user["sub"]}


# =========================
# CREATE PERSON
# =========================
def _owned_person(patient_id: str, person_id: str) -> dict:
    rows = supabase.table("known_persons").select("*") \
        .eq("id", person_id).eq("patient_id", patient_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Person not found")
    return rows[0]


@app.post("/person")
async def create_person(
    name: str = Form(...),
    relationship: str = Form(None),
    file: UploadFile = File(None),
    user=Depends(get_current_user)
):
    """Create a person. With a photo (`file`) their face is enrolled in the same call; if the photo
    has no usable face nothing is created."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="A name is required")
    try:
        patient_id = user["sub"]

        # Ensure patient exists
        ensure_patient(patient_id)

        # Insert person
        res = supabase.table("known_persons").insert({
            "patient_id": patient_id,
            "name": name.strip(),
            "relationship": relationship or None,
        }).execute()

        if not res.data:
            raise Exception("Insert failed")
        person = res.data[0]

        if file is not None:
            try:
                enrolled = await add_face_logic(file, person["id"])
            except Exception:
                supabase.table("known_persons").delete().eq("id", person["id"]).execute()
                raise
            if not enrolled:
                supabase.table("known_persons").delete().eq("id", person["id"]).execute()
                raise HTTPException(status_code=400, detail="No face found in the photo")
            person["face_added"] = True

        return person

    except HTTPException:
        raise
    except InvalidImage as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("Create person error:", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# ADD FACE
# =========================
@app.post("/add-face")
async def add_face(
    person_id: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """Enroll a photo of an existing person (the largest face in the photo is used)."""
    try:
        _owned_person(user["sub"], person_id)

        success = await add_face_logic(file, person_id)

        if not success:
            raise HTTPException(status_code=400, detail="No face found")

        return {"message": "Face added successfully", "person_id": person_id}

    except HTTPException:
        raise
    except InvalidImage as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("Add face error:", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# RECOGNIZE FACE
# =========================


@app.post("/recognize")
async def recognize(
    file: UploadFile = File(...),
    wait: bool = False,
    rotate: int = 0,
    mirror: bool = False,
    user=Depends(get_current_user)
):
    """Identify faces in an image.

    `rotate` (0, 90, 180, 270 = degrees clockwise) and `mirror` (flip left-right, applied after the
    rotation) let a phone send camera frames as they come off the sensor. The returned `location`,
    `image_width` and `image_height` refer to the image after that transform.

    Live video (default): answers immediately; `identifying: true` means the cloud model is still
    verifying and a later frame of the same face gets the final answer.
    Still photo (`?wait=true`): waits for the cloud model, so every face is final in one response.
    """
    try:
        patient_id = user["sub"]

        if rotate not in (0, 90, 180, 270):
            raise HTTPException(status_code=400, detail="rotate must be 0, 90, 180 or 270")

        results = await recognize_logic(file, patient_id, wait=wait, rotate=rotate, mirror=mirror)

        # Ensure location always exists (frontend safety)
        for r in results:
            if "location" not in r:
                r["location"] = [0, 0, 0, 0]

        return results

    except HTTPException:
        raise
    except InvalidImage as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("Recognize error:", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# WHISPER
# =========================
@app.post("/process-interaction")
async def process_interaction(
    audio: UploadFile = File(...),
    person_id: str = Form(None),
    user=Depends(get_current_user)
):
    try:
        patient_id = user["sub"]

        return await process_audio(
            audio,
            patient_id,   # ✅ REQUIRED
            person_id     # ✅ OPTIONAL
        )

    except Exception as e:
        print(f"Process interaction error: {str(e)}")
        raise HTTPException(500, str(e))


@app.get("/summary/{person_id}")
def get_summary(person_id: str, user=Depends(get_current_user)):
    try:
        res = supabase.table("interaction_summaries") \
            .select("*") \
            .eq("known_person_id", person_id) \
            .limit(1) \
            .execute()

        # ✅ NO ROW → return empty instead of crashing
        if not res.data or len(res.data) == 0:
            return {
                "first_summary": None,
                "last_summary": None
            }

        row = res.data[0]

        return {
            "first_summary": row.get("first_summary"),
            "last_summary": row.get("last_summary")
        }

    except Exception as e:
        print("Summary fetch error:", e)
        raise HTTPException(500, str(e))


@app.get("/relation/{person_id}")
def get_relation(person_id: str, user=Depends(get_current_user)):
    try:
        res = supabase.table("known_persons") \
            .select("relationship") \
            .eq("id", person_id) \
            .limit(1) \
            .execute()

        if not res.data or len(res.data) == 0:
            return {"relation": None}

        return {
            "relation": res.data[0]["relationship"]
        }

    except Exception as e:
        print("Relation fetch error:", e)
        raise HTTPException(500, str(e))


# =========================
# SESSIONS
# =========================
@app.post("/session/start")
def session_start(
    mode: str = Form(...),
    person_id: str = Form(None),
    user=Depends(get_current_user)
):
    host.ensure_self_person(user["sub"], user["username"])   # the host is a named person from the first session
    return sessions.start_session(user["sub"], mode, person_id)


@app.post("/session/{session_id}/end")
async def session_end(
    session_id: str,
    background: BackgroundTasks,
    audio: UploadFile = File(None),
    person_id: str = Form(None),
    face_image: UploadFile = File(None),
    video: UploadFile = File(None),
    user=Depends(get_current_user)
):
    """Returns immediately with status "processing"; poll GET /session/{id} for the result."""
    try:
        job = await sessions.end_session(session_id, user["sub"], audio, person_id, face_image, video)
        background.add_task(sessions.process_session, session_id, user["sub"],
                            job["path"], job["mode"], job["person_id"])
        return {"session_id": session_id, "status": "processing"}
    except HTTPException:
        raise
    except Exception as e:
        print("Session end error:", e)
        raise HTTPException(500, str(e))


@app.get("/session/{session_id}")
def session_get(session_id: str, include_face: bool = False, user=Depends(get_current_user)):
    return sessions.get_result(session_id, user["sub"], include_face)


@app.post("/person/finalize")
async def person_finalize(
    session_id: str = Form(...),
    name: str = Form(None),
    relationship: str = Form(None),
    person_id: str = Form(None),
    use_session_face: bool = Form(False),
    face_image: UploadFile = File(None),
    user=Depends(get_current_user)
):
    try:
        return await sessions.finalize_session(
            session_id, user["sub"], name, relationship, face_image, person_id, use_session_face)
    except HTTPException:
        raise
    except Exception as e:
        print("Finalize error:", e)
        raise HTTPException(500, str(e))


# =========================
# VOICE ENROLLMENT
# =========================
@app.post("/voice/enroll")
async def voice_enroll(
    audio: UploadFile = File(...),
    user=Depends(get_current_user)
):
    try:
        return await sessions.enroll_host(user["sub"], audio, user["username"])
    except Exception as e:
        print("Voice enroll error:", e)
        raise HTTPException(500, str(e))


@app.get("/voice/status")
def voice_status(user=Depends(get_current_user)):
    res = supabase.table("host_voice_profile").select("patient_id") \
        .eq("patient_id", user["sub"]).limit(1).execute()
    return {"enrolled": bool(res.data)}


# =========================
# PEOPLE & HISTORY
# =========================
@app.get("/people")
def people(user=Depends(get_current_user)):
    return sessions.list_people(user["sub"])


@app.get("/sessions")
def session_history(user=Depends(get_current_user)):
    return sessions.list_sessions(user["sub"])


# =========================
# LIVE CAPTIONS
# =========================
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await live.handle(ws)


# =========================
# ASK YOUR MEMORY
# =========================
@app.post("/ask")
async def ask_memory(
    question: str = Form(None),
    audio: UploadFile = File(None),
    user=Depends(get_current_user)
):
    """Answer a question from past conversations. Send the question as text, or as a short audio clip."""
    patient_id = user["sub"]
    try:
        if not (question and question.strip()):
            if audio is None:
                raise HTTPException(400, "Send a question (text) or audio")
            path = await speech.save_upload(audio)
            try:
                question = (await asyncio.to_thread(speech.transcribe_full, path))["text"]
            finally:
                os.remove(path)
            if not question:
                raise HTTPException(400, "I couldn't hear a question")

        result = await asyncio.to_thread(memory.ask, patient_id, question)
        return {"question": question.strip(), **result}
    except HTTPException:
        raise
    except Exception as e:
        print("Ask error:", e)
        raise HTTPException(500, str(e))


@app.post("/memory/reindex")
async def memory_reindex(user=Depends(get_current_user)):
    """Index conversations recorded before Ask your memory existed."""
    return await asyncio.to_thread(memory.reindex_all, user["sub"])


# =========================
# SESSION VIDEO (optional, opt-in from the app)
# =========================
@app.get("/session/{session_id}/video")
def session_video(session_id: str, user=Depends(get_current_user)):
    session = sessions.get_session(session_id, user["sub"])
    path = sessions.video_path(user["sub"], session)
    if not path:
        raise HTTPException(404, "No video for this session")
    return FileResponse(path, media_type="video/mp4" if path.endswith(".mp4") else "video/webm")


@app.delete("/session/{session_id}/video")
def delete_session_video(session_id: str, user=Depends(get_current_user)):
    session = sessions.get_session(session_id, user["sub"])
    path = sessions.video_path(user["sub"], session)
    if path:
        os.remove(path)
    supabase.table("sessions").update({"video_name": None}).eq("id", session_id).execute()
    return {"deleted": bool(path)}
