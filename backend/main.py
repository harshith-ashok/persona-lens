from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from auth import get_current_user
from db import supabase
from face import add_face_logic, recognize_logic
from speech import process_audio

app = FastAPI()

# 🌐 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 🔐 AUTH DEBUG
# =========================


@app.get("/me")
def me(user=Depends(get_current_user)):
    return {"patient_id": user["sub"]}


# =========================
# 👤 CREATE PERSON
# =========================
@app.post("/person")
def create_person(
    name: str = Form(...),
    user=Depends(get_current_user)
):
    try:
        patient_id = user["sub"]

        # Ensure patient exists
        supabase.table("patients").upsert({
            "id": patient_id,
            "full_name": "Patient"
        }).execute()

        # Insert person
        res = supabase.table("known_persons").insert({
            "patient_id": patient_id,
            "name": name
        }).execute()

        if not res.data:
            raise Exception("Insert failed")

        return res.data[0]

    except Exception as e:
        print("Create person error:", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# ➕ ADD FACE
# =========================
@app.post("/add-face")
async def add_face(
    person_id: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    try:
        success = await add_face_logic(file, person_id)

        if not success:
            raise HTTPException(status_code=400, detail="No face found")

        return {"message": "Face added successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print("Add face error:", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# 🎥 RECOGNIZE FACE
# =========================
@app.post("/recognize")
async def recognize(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    try:
        patient_id = user["sub"]

        results = await recognize_logic(file, patient_id)

        # Ensure location always exists (frontend safety)
        for r in results:
            if "location" not in r:
                r["location"] = [0, 0, 0, 0]

        return results

    except Exception as e:
        print("Recognize error:", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# 🎤 AUDIO → WHISPER
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

# ✅ Get summary for a person (SAFE)


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
