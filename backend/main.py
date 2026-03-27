from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from auth import get_current_user
from db import supabase
from face import add_face_logic, recognize_logic
from speech import process_audio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/me")
def me(user=Depends(get_current_user)):
    return {"patient_id": user["sub"]}


# ✅ Ensure patient
@app.post("/ensure-patient")
def ensure_patient(user=Depends(get_current_user)):
    supabase.table("patients").upsert({
        "id": user["sub"],
        "full_name": "Patient"
    }).execute()
    return {"ok": True}


# ✅ Create person
@app.post("/person")
def create_person(name: str = Form(...), user=Depends(get_current_user)):
    try:
        patient_id = user["sub"]

        res = supabase.table("known_persons").insert({
            "patient_id": patient_id,
            "name": name
        }).execute()

        if not res.data:
            raise Exception(res)

        return res.data[0]

    except Exception as e:
        raise HTTPException(500, str(e))


# ✅ Add face
@app.post("/add-face")
async def add_face(
    person_id: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    success = await add_face_logic(file, person_id)

    if not success:
        raise HTTPException(400, "No face found")

    return {"message": "Face added"}


# ✅ Recognize
@app.post("/recognize")
async def recognize(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    patient_id = user["sub"]
    return await recognize_logic(file, patient_id)


# ✅ Speech
@app.post("/process-interaction")
async def process_interaction(
    audio: UploadFile = File(...),
    person_id: str = Form(None),
    user=Depends(get_current_user)
):
    return await process_audio(audio, user["sub"], person_id)
