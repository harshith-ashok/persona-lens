from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import face_recognition
import numpy as np
import pickle
import cv2

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # your Vue app
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


@app.post("/add-face")
async def add_face(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    db = load_db()

    img = await file.read()
    np_img = np.frombuffer(img, np.uint8)

    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if image is None:
        return {"error": "Invalid image"}

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    encodings = face_recognition.face_encodings(rgb_image)

    if len(encodings) == 0:
        return {"error": "No face found"}

    db["encodings"].append(encodings[0])
    db["names"].append(name)

    save_db(db)

    return {"message": "Face added"}


@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    db = load_db()

    img = await file.read()
    np_img = np.frombuffer(img, np.uint8)

    import cv2
    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if image is None:
        return {"error": "Invalid image"}

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_image)
    encodings = face_recognition.face_encodings(rgb_image, face_locations)

    results = []

    for face_encoding, location in zip(encodings, face_locations):

        if len(db["encodings"]) == 0:
            name = "Unknown"
        else:
            matches = face_recognition.compare_faces(
                db["encodings"], face_encoding)
            distances = face_recognition.face_distance(
                db["encodings"], face_encoding)

            best_match = np.argmin(distances)

            if matches[best_match] and distances[best_match] < 0.5:
                name = db["names"][best_match]
            else:
                name = "Unknown"

        results.append({
            "name": name,
            "location": location  # [top, right, bottom, left]
        })

    return results
