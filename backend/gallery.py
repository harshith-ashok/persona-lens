"""Photo gallery: uploaded images are stored, and every face in them is kept with its embedding.

Files live under config.GALLERY_DIR/<patient_id>/ (Supabase Storage is not part of the local stack);
metadata and the 128-d dlib face embeddings live in the database (gallery_images, gallery_faces).
"""
import io
import json
import os
import uuid

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

import config
import face
from auth import get_current_user
from db import ensure_patient, supabase

router = APIRouter(prefix="/gallery", tags=["gallery"])

THUMB_SIDE = 400
CONTENT_TYPES = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}


# ---------- helpers ----------
def _dir(patient_id: str) -> str:
    path = os.path.join(config.GALLERY_DIR, patient_id)
    os.makedirs(path, exist_ok=True)
    return path


def _vec(v) -> list[float]:
    return json.loads(v) if isinstance(v, str) else list(v)


def _get_image(patient_id: str, image_id: str) -> dict:
    rows = supabase.table("gallery_images").select("*") \
        .eq("id", image_id).eq("patient_id", patient_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Image not found")
    return rows[0]


def _person_names(patient_id: str) -> dict:
    """person id -> name; the host's id is also in `_person_names.selfs` semantics via _selves()."""
    rows = supabase.table("known_persons").select("id, name").eq("patient_id", patient_id).execute().data
    return {r["id"]: r["name"] for r in rows}


def _selves(patient_id: str) -> set:
    rows = supabase.table("known_persons").select("id").eq("patient_id", patient_id).eq("is_self", True).execute().data
    return {r["id"] for r in rows}


def _faces_for(image_ids: list[str]) -> dict:
    if not image_ids:
        return {}
    rows = supabase.table("gallery_faces") \
        .select("id, image_id, person_id, box, confidence, source") \
        .in_("image_id", image_ids).execute().data
    out = {}
    for r in rows:
        out.setdefault(r["image_id"], []).append(r)
    return out


def _view(img: dict, faces: list[dict], names: dict, selves: set) -> dict:
    return {
        "id": img["id"],
        "caption": img["caption"],
        "created_at": img["created_at"],
        "width": img["width"],
        "height": img["height"],
        "byte_size": img["byte_size"],
        "image_url": f"/gallery/{img['id']}/image",
        "thumb_url": f"/gallery/{img['id']}/thumb",
        "faces": [{
            "id": f["id"],
            "person_id": f["person_id"],
            "person_name": names.get(f["person_id"]),
            "is_self": f["person_id"] in selves,
            "confidence": f["confidence"],
            "source": f["source"],
            "location": f["box"],          # [top, right, bottom, left] in pixels of the stored image
        } for f in faces],
    }


def _views(patient_id: str, images: list[dict]) -> list[dict]:
    faces = _faces_for([i["id"] for i in images])
    names, selves = _person_names(patient_id), _selves(patient_id)
    return [_view(i, faces.get(i["id"], []), names, selves) for i in images]


# ---------- upload ----------
@router.post("")
async def upload(file: UploadFile = File(...), caption: str = Form(None), user=Depends(get_current_user)):
    """Store an image and identify the faces in it. A superset of `POST /recognize?wait=true`:
    the response has the same per-face answers, plus a permanent `id` and URLs for the image."""
    patient_id = user["sub"]
    data = await file.read()
    if len(data) > config.GALLERY_MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"Image is larger than {config.GALLERY_MAX_MB:g} MB")

    try:
        rgb = face._decode(data)
        fmt = (Image.open(io.BytesIO(data)).format or "JPEG").upper()
    except (face.InvalidImage, OSError):
        raise HTTPException(400, "Invalid image")
    ext, content_type = CONTENT_TYPES.get(fmt, ("jpg", "image/jpeg"))

    ensure_patient(patient_id)

    known = face._load_known(patient_id)
    found = await face.identify_faces(rgb, known)

    image_id = str(uuid.uuid4())
    folder = _dir(patient_id)
    file_name, thumb_name = f"{image_id}.{ext}", f"{image_id}_thumb.jpg"
    with open(os.path.join(folder, file_name), "wb") as f:
        f.write(data)
    thumb = Image.fromarray(rgb)
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE))
    thumb.save(os.path.join(folder, thumb_name), "JPEG", quality=82)

    h, w = rgb.shape[:2]
    try:
        supabase.table("gallery_images").insert({
            "id": image_id, "patient_id": patient_id, "file_name": file_name, "thumb_name": thumb_name,
            "content_type": content_type, "width": w, "height": h, "byte_size": len(data),
            "caption": (caption or "").strip() or None,
        }).execute()
        if found:
            supabase.table("gallery_faces").insert([{
                "image_id": image_id, "patient_id": patient_id, "person_id": f["person_id"],
                "box": [int(x) for x in f["box"]], "embedding": [float(x) for x in f["encoding"]],
                "confidence": f["confidence"], "source": f["source"],
            } for f in found]).execute()
    except Exception:
        for name in (file_name, thumb_name):      # don't leave orphan files behind
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
        raise

    return _views(patient_id, [_get_image(patient_id, image_id)])[0]


# ---------- list / detail ----------
@router.get("")
def list_images(person_id: str | None = None, unidentified: bool = False,
                limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                user=Depends(get_current_user)):
    """Newest first. `person_id` = photos that person is in; `unidentified=true` = photos with a face nobody matched."""
    patient_id = user["sub"]
    query = supabase.table("gallery_images").select("id").eq("patient_id", patient_id)

    if person_id or unidentified:
        faces = supabase.table("gallery_faces").select("image_id").eq("patient_id", patient_id)
        faces = faces.eq("person_id", person_id) if person_id else faces.is_("person_id", "null")
        ids = list({r["image_id"] for r in faces.execute().data})
        if not ids:
            return {"images": [], "total": 0}
        query = query.in_("id", ids)

    ordered = [r["id"] for r in query.order("created_at", desc=True).execute().data]
    page = ordered[offset:offset + limit]
    if not page:
        return {"images": [], "total": len(ordered)}

    rows = {r["id"]: r for r in supabase.table("gallery_images").select("*").in_("id", page).execute().data}
    return {"images": _views(patient_id, [rows[i] for i in page if i in rows]), "total": len(ordered)}


@router.get("/{image_id}")
def get_image_detail(image_id: str, user=Depends(get_current_user)):
    patient_id = user["sub"]
    return _views(patient_id, [_get_image(patient_id, image_id)])[0]


def _file(patient_id: str, image_id: str, thumb: bool) -> FileResponse:
    img = _get_image(patient_id, image_id)
    path = os.path.join(_dir(patient_id), img["thumb_name"] if thumb else img["file_name"])
    if not os.path.exists(path):
        raise HTTPException(404, "Image file is missing")
    return FileResponse(path, media_type="image/jpeg" if thumb else img["content_type"],
                        headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{image_id}/image")
def get_image_file(image_id: str, user=Depends(get_current_user)):
    return _file(user["sub"], image_id, thumb=False)


@router.get("/{image_id}/thumb")
def get_thumbnail(image_id: str, user=Depends(get_current_user)):
    return _file(user["sub"], image_id, thumb=True)


# ---------- delete ----------
@router.delete("/{image_id}")
def delete_image(image_id: str, user=Depends(get_current_user)):
    patient_id = user["sub"]
    img = _get_image(patient_id, image_id)
    supabase.table("gallery_images").delete().eq("id", image_id).execute()   # faces cascade
    for name in (img["file_name"], img["thumb_name"]):
        try:
            os.remove(os.path.join(_dir(patient_id), name))
        except OSError:
            pass
    return {"deleted": image_id}


# ---------- say who a face is ----------
@router.post("/faces/{face_id}/assign")
def assign_face(face_id: str, person_id: str = Form(None), name: str = Form(None),
                relationship: str = Form(None), enroll: bool = Form(True),
                user=Depends(get_current_user)):
    """Say who a face in a stored photo is: an existing person (`person_id`) or a new one (`name`).
    With `enroll` (default) the face is also added to that person's recognition photos, so they are
    recognized better everywhere."""
    patient_id = user["sub"]
    rows = supabase.table("gallery_faces").select("*") \
        .eq("id", face_id).eq("patient_id", patient_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Face not found")
    gface = rows[0]

    if person_id:
        owned = supabase.table("known_persons").select("id, name").eq("id", person_id) \
            .eq("patient_id", patient_id).limit(1).execute().data
        if not owned:
            raise HTTPException(404, "Person not found")
        person = owned[0]
    else:
        if not name or not name.strip():
            raise HTTPException(400, "Send person_id or a name")
        person = supabase.table("known_persons").insert({
            "patient_id": patient_id, "name": name.strip(), "relationship": relationship or None,
        }).execute().data[0]

    supabase.table("gallery_faces").update({
        "person_id": person["id"], "confidence": 1.0, "source": "manual",
    }).eq("id", face_id).execute()

    if enroll:
        img = _get_image(patient_id, gface["image_id"])
        crop = None
        try:
            rgb = face._decode(open(os.path.join(_dir(patient_id), img["file_name"]), "rb").read())
            crop = face._crop_b64(rgb, tuple(gface["box"]))
        except Exception as e:
            print("Gallery enroll crop skipped:", e)
        face.enroll_encoding(person["id"], np.array(_vec(gface["embedding"])), crop)

    return {"face_id": face_id, "person_id": person["id"], "person_name": person["name"], "enrolled": enroll}


# ---------- re-identify after learning new people ----------
@router.post("/reidentify")
def reidentify(user=Depends(get_current_user)):
    """Try the faces nobody matched again with what the app knows now (fast, uses the stored embeddings)."""
    patient_id = user["sub"]
    known = face._load_known(patient_id)
    rows = supabase.table("gallery_faces").select("id, embedding") \
        .eq("patient_id", patient_id).is_("person_id", "null").limit(500).execute().data

    matched = 0
    for r in rows:
        result, _ = face._match_local(known, np.array(_vec(r["embedding"]), dtype=np.float32))
        if result["person_id"]:
            supabase.table("gallery_faces").update({
                "person_id": result["person_id"], "confidence": result["confidence"], "source": "local",
            }).eq("id", r["id"]).execute()
            matched += 1
    return {"checked": len(rows), "matched": matched}


# ---------- find photos by example ----------
@router.post("/search")
async def search_by_face(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload a photo of someone; get the stored photos they appear in (largest face is used)."""
    patient_id = user["sub"]
    try:
        rgb = face._decode(await file.read())
    except face.InvalidImage:
        raise HTTPException(400, "Invalid image")

    faces = face._detect(rgb)
    if not faces:
        return {"images": [], "query_faces": 0}
    box, enc = max(faces, key=lambda f: (f[0][2] - f[0][0]) * (f[0][1] - f[0][3]))

    hits = supabase.rpc("match_gallery_faces", {
        "p_patient": patient_id, "p_query": "[" + ",".join(f"{float(x):.6f}" for x in enc) + "]",
        "p_k": 100, "p_max": face.LOCAL_THRESHOLD,
    }).execute().data

    best = {}
    for h in hits:                       # closest face per image
        if h["image_id"] not in best or h["distance"] < best[h["image_id"]]:
            best[h["image_id"]] = h["distance"]
    if not best:
        return {"images": [], "query_faces": len(faces)}

    images = supabase.table("gallery_images").select("*").in_("id", list(best)).execute().data
    views = _views(patient_id, images)
    for v in views:
        v["distance"] = round(best[v["id"]], 3)
    return {"images": sorted(views, key=lambda v: v["distance"]), "query_faces": len(faces)}
