from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import face_recognition
import pickle

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "faces.pkl"


def load_db():
    try:
        with open(DB_FILE, "rb") as f:
            return pickle.load(f)
    except:
        return {"encodings": [], "names": []}


def save_db(data):
    with open(DB_FILE, "wb") as f:
        pickle.dump(data, f)


# ✅ ADD FACE
@app.post("/add-face")
async def add_face(name: str = Form(...), file: UploadFile = File(...)):
    db = load_db()

    img = await file.read()
    np_img = np.frombuffer(img, np.uint8)

    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if image is None:
        return {"error": "Invalid image"}

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    encodings = face_recognition.face_encodings(rgb)

    if len(encodings) == 0:
        return {"error": "No face found"}

    db["encodings"].append(encodings[0])
    db["names"].append(name)

    save_db(db)

    return {"message": "Face added"}


# ✅ MULTI FACE RECOGNITION
@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    db = load_db()

    img = await file.read()
    np_img = np.frombuffer(img, np.uint8)

    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if image is None:
        return {"error": "Invalid image"}

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # 🔥 downscale for speed
    small = cv2.resize(rgb, (0, 0), fx=0.5, fy=0.5)

    locations = face_recognition.face_locations(small)
    encodings = face_recognition.face_encodings(small, locations)

    results = []

    for (top, right, bottom, left), enc in zip(locations, encodings):

        name = "Unknown"

        if len(db["encodings"]) > 0:
            matches = face_recognition.compare_faces(db["encodings"], enc)
            distances = face_recognition.face_distance(db["encodings"], enc)

            best = np.argmin(distances)

            if matches[best] and distances[best] < 0.6:
                name = db["names"][best]

        # scale back
        top *= 2
        right *= 2
        bottom *= 2
        left *= 2

        results.append({
            "name": name,
            "location": [top, right, bottom, left]
        })

    return results
