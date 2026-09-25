import asyncio
import base64
import io
import itertools
import threading
import time

import ast
import cv2
import numpy as np
import face_recognition
from fastapi import UploadFile
from PIL import Image

import vision
from db import supabase

from config import VISION_BACKEND  # "cloud": Ollama Cloud identifies faces, dlib on any error; "local": dlib only
MAX_CANDIDATES = 6      # people sent to the cloud model per query
REFS_PER_PERSON = 2
CLOUD_TRUST = 15.0      # seconds a cloud identity is trusted for a tracked face
TRACK_LIFETIME = 5.0    # seconds a track survives without a matching detection
TRACK_IOU = 0.3
LOCAL_THRESHOLD = 0.6
MAX_DETECT_SIDE = 1024  # longest image side used for face detection

embedding_cache = {}
_tracks = {}            # patient_id -> [{id, box, result, at, cloud_at, pending}]
_track_ids = itertools.count(1)
_lock = threading.RLock()


class InvalidImage(ValueError):
    """The upload is not a decodable image."""


# ---------- helpers ----------
def _decode(img_bytes: bytes):
    """Bytes -> RGB array. OpenCV applies the EXIF orientation, so phone photos come out upright."""
    image = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise InvalidImage("Invalid image")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _orient(rgb, rotate: int = 0, mirror: bool = False):
    """Rotate clockwise by `rotate` degrees (0/90/180/270), then optionally flip left-right.
    Lets a phone send camera frames in sensor orientation; returned boxes match the result."""
    if rotate:
        rgb = np.rot90(rgb, k=-(rotate // 90))
    if mirror:
        rgb = rgb[:, ::-1]
    return np.ascontiguousarray(rgb)


def _detect(rgb):
    """-> [(box, encoding)] with boxes in the coordinates of `rgb`.

    Big photos are shrunk for detection (dlib's cost grows with pixel count; a 11 MP photo took
    ~2.7 s) and the boxes are scaled back, so callers always get full-size coordinates."""
    h, w = rgb.shape[:2]
    scale = min(1.0, MAX_DETECT_SIDE / max(h, w))
    small = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else rgb

    locations = face_recognition.face_locations(small)
    encodings = face_recognition.face_encodings(small, locations)

    def back(v, limit):
        return min(limit, max(0, round(v / scale)))

    return [((back(t, h), back(r, w), back(b, h), back(l, w)), enc)
            for (t, r, b, l), enc in zip(locations, encodings)]


def _crop_b64(rgb, box, margin=0.4, side=256) -> str:
    top, right, bottom, left = box
    h, w = rgb.shape[:2]
    mv, mh = int((bottom - top) * margin), int((right - left) * margin)
    crop = rgb[max(0, top - mv):min(h, bottom + mv), max(0, left - mh):min(w, right + mh)]
    im = Image.fromarray(crop)
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _iou(a, b) -> float:
    ta, ra, ba, la = a
    tb, rb, bb, lb = b
    iw = max(0, min(ra, rb) - max(la, lb))
    ih = max(0, min(ba, bb) - max(ta, tb))
    inter = iw * ih
    union = (ra - la) * (ba - ta) + (rb - lb) * (bb - tb) - inter
    return inter / union if union else 0.0


# ---------- enrollment ----------
async def add_face_logic(file: UploadFile, person_id: str):
    return add_face_bytes(await file.read(), person_id)


def add_face_bytes(img_bytes: bytes, person_id: str):
    rgb = _decode(img_bytes)

    faces = _detect(rgb)
    if not faces:
        return None

    # the largest face in the frame is the one being enrolled
    box, encoding = max(faces, key=lambda f: (f[0][2] - f[0][0]) * (f[0][1] - f[0][3]))

    enroll_encoding(person_id, encoding, _crop_b64(rgb, box))
    return True


def enroll_encoding(person_id: str, encoding, image_b64: str | None) -> None:
    """Store one face encoding (and reference photo) for a person and drop the caches."""
    res = supabase.table("face_embeddings").insert({
        "known_person_id": person_id,
        "embedding": [float(x) for x in encoding],
        "image_b64": image_b64,
    }).execute()

    if not res.data:
        raise Exception("DB insert failed")

    # 🔥 invalidate cache
    embedding_cache.clear()
    with _lock:
        _tracks.clear()


# ---------- recognition ----------
def _load_known(patient_id: str):
    """-> (encodings, names, person_ids, images_by_person, host_person_ids) for this patient."""
    if patient_id in embedding_cache:
        return embedding_cache[patient_id]

    data = supabase.table("face_embeddings") \
        .select("embedding, image_b64, captured_at, known_persons(name, id, is_self)") \
        .eq("known_persons.patient_id", patient_id) \
        .order("captured_at", desc=True) \
        .execute()

    encodings, names, person_ids = [], [], []
    images = {}   # person_id -> [b64, ...] newest first
    selfs = set()  # person ids that are the host ("you")

    for row in data.data:
        person = row.get("known_persons")
        if not person:
            continue

        embedding = row["embedding"]
        if isinstance(embedding, str):
            embedding = ast.literal_eval(embedding)

        encodings.append(np.array(embedding, dtype=np.float32))
        names.append(person["name"])
        person_ids.append(person["id"])
        if person.get("is_self"):
            selfs.add(person["id"])
        if row.get("image_b64") and len(images.setdefault(person["id"], [])) < REFS_PER_PERSON:
            images[person["id"]].append(row["image_b64"])

    embedding_cache[patient_id] = (encodings, names, person_ids, images, selfs)
    return embedding_cache[patient_id]


def _is_self(known, person_id) -> bool:
    """True when this person is the host (the account owner), not a visitor."""
    return bool(person_id) and person_id in known[4]


def _match_local(known, enc):
    """dlib: -> (result dict, distances per known encoding)."""
    encodings, names, person_ids, _, _selfs = known
    result = {"name": "Unknown", "person_id": None, "confidence": 0.0}
    if not encodings:
        return result, None

    distances = face_recognition.face_distance(encodings, enc)
    best = int(np.argmin(distances))
    if distances[best] < LOCAL_THRESHOLD:
        result = {"name": names[best], "person_id": person_ids[best],
                  "confidence": float(1 - distances[best])}
    return result, distances


def _cloud_candidates(known, distances):
    """Nearest-by-dlib people that have reference photos, capped at MAX_CANDIDATES."""
    encodings, names, person_ids, images, _selfs = known
    order = np.argsort(distances) if distances is not None else range(len(person_ids))
    seen, out = set(), []
    for i in order:
        pid = person_ids[i]
        if pid in seen or pid not in images:
            continue
        seen.add(pid)
        out.append({"person_id": pid, "name": names[i], "images": images[pid]})
        if len(out) == MAX_CANDIDATES:
            break
    return out


def _identify(crop_b64, candidates, local):
    """Cloud identity for one face crop, or the local result if the cloud fails."""
    try:
        match, confidence = vision.identify(crop_b64, candidates)
    except Exception as e:
        print("Cloud vision failed, using dlib:", e)
        return {**local, "source": "local-fallback"}

    if match is None:
        return {"name": "Unknown", "person_id": None, "confidence": 0.0, "source": "cloud"}
    return {"name": match["name"], "person_id": match["person_id"],
            "confidence": confidence, "source": "cloud"}


def _identify_in_background(track, crop_b64, candidates, local):
    result = _identify(crop_b64, candidates, local)
    with _lock:
        track["result"] = result
        track["cloud_at"] = time.time() if result["source"] == "cloud" else 0.0
        track["pending"] = False


async def identify_faces(rgb, known):
    """Detect and identify every face in a still image, waiting for the cloud so answers are final.
    -> [{"box", "encoding", "name", "person_id", "confidence", "source"}]"""
    faces = _detect(rgb)

    async def one(box, enc):
        local, distances = _match_local(known, enc)
        candidates = _cloud_candidates(known, distances)
        if VISION_BACKEND == "cloud" and candidates and vision.available():
            result = await asyncio.to_thread(_identify, _crop_b64(rgb, box), candidates, local)
        else:
            result = {**local, "source": "local"}
        return {**result, "box": box, "encoding": enc, "is_self": _is_self(known, result.get("person_id"))}

    return list(await asyncio.gather(*(one(b, e) for b, e in faces)))


async def _recognize_photo(rgb, known):
    """Still photo: no tracking, and we wait for the cloud so the answer is final."""
    h, w = rgb.shape[:2]
    found = await identify_faces(rgb, known)
    return [{"name": f["name"], "person_id": f["person_id"], "confidence": f["confidence"],
             "source": f["source"], "location": list(f["box"]), "track_id": i, "identifying": False,
             "is_self": f["is_self"], "image_width": w, "image_height": h} for i, f in enumerate(found, start=1)]


async def recognize_logic(file: UploadFile, patient_id: str, wait: bool = False,
                          rotate: int = 0, mirror: bool = False):
    """Detect faces and identify them. Never waits on the cloud: a new face is answered with the
    local (dlib) result flagged `identifying`, while the cloud call runs in the background and
    updates the face's track for the following frames."""
    try:
        known = _load_known(patient_id)
        rgb = _orient(_decode(await file.read()), rotate, mirror)

        if wait:
            return await _recognize_photo(rgb, known)

        faces = _detect(rgb)
        locations = [b for b, _ in faces]
        encodings = [e for _, e in faces]

        now = time.time()
        with _lock:
            tracks = [t for t in _tracks.get(patient_id, []) if now - t["at"] < TRACK_LIFETIME]
            used, out = set(), []

            for box, enc in zip(locations, encodings):
                local, distances = _match_local(known, enc)

                free = [t for t in tracks if id(t) not in used]
                track = max(free, key=lambda t: _iou(t["box"], box), default=None)
                if track is None or _iou(track["box"], box) < TRACK_IOU:
                    track = {"id": next(_track_ids), "result": None, "cloud_at": 0.0, "pending": False}
                    tracks.append(track)
                used.add(id(track))
                track["box"], track["at"] = box, now

                if track["cloud_at"] and now - track["cloud_at"] < CLOUD_TRUST:
                    result = track["result"]
                else:
                    result = {**local, "source": "local"}
                    candidates = _cloud_candidates(known, distances)
                    if (not track["pending"] and VISION_BACKEND == "cloud"
                            and candidates and vision.available()):
                        track["pending"] = True
                        threading.Thread(
                            target=_identify_in_background,
                            args=(track, _crop_b64(rgb, box), candidates, local),
                            daemon=True,
                        ).start()

                out.append({**result, "location": list(box), "track_id": track["id"],
                            "identifying": track["pending"],
                            "is_self": _is_self(known, result.get("person_id")),
                            "image_width": rgb.shape[1], "image_height": rgb.shape[0]})

            _tracks[patient_id] = tracks

        return out

    except Exception as e:
        print("Error in recognize_logic:", e)
        raise
