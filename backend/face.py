import cv2
import numpy as np
import face_recognition
import ast
from fastapi import UploadFile
from db import supabase


embedding_cache = {}


async def add_face_logic(file: UploadFile, person_id: str):
    img = await file.read()
    np_img = np.frombuffer(img, np.uint8)
    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    if image is None:
        raise Exception("Invalid image")

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(rgb)

    if not encodings:
        return None

    embedding = encodings[0].tolist()

    res = supabase.table("face_embeddings").insert({
        "known_person_id": person_id,
        "embedding": embedding
    }).execute()

    if not res.data:
        raise Exception("DB insert failed")

    # 🔥 invalidate cache
    embedding_cache.clear()

    return True


async def recognize_logic(file: UploadFile, patient_id: str):
    try:

        if patient_id in embedding_cache:
            known_embeddings, names, person_ids = embedding_cache[patient_id]
        else:
            data = supabase.table("face_embeddings") \
                .select("embedding, known_persons(name, id)") \
                .eq("known_persons.patient_id", patient_id) \
                .execute()

            known_embeddings, names, person_ids = [], [], []

            for row in data.data:
                if not row.get("known_persons"):
                    continue

                embedding = row["embedding"]

                if isinstance(embedding, str):
                    embedding = ast.literal_eval(embedding)

                known_embeddings.append(np.array(embedding, dtype=np.float32))
                names.append(row["known_persons"]["name"])
                person_ids.append(row["known_persons"]["id"])

            embedding_cache[patient_id] = (
                known_embeddings, names, person_ids
            )

        img = await file.read()
        np_img = np.frombuffer(img, np.uint8)
        image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if image is None:
            raise Exception("Invalid image")

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        locations = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, locations)

        results = []

        for (top, right, bottom, left), enc in zip(locations, encodings):
            name = "Unknown"
            person_id = None
            confidence = 0

            if known_embeddings:
                distances = face_recognition.face_distance(
                    known_embeddings, enc
                )
                best = np.argmin(distances)

                if distances[best] < 0.6:
                    name = names[best]
                    person_id = person_ids[best]
                    confidence = float(1 - distances[best])

            results.append({
                "name": name,
                "person_id": person_id,
                "confidence": confidence,
                "location": [top, right, bottom, left]
            })

        return results

    except Exception as e:
        print("Error in recognize_logic:", e)
        raise
