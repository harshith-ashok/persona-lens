"""The host: the account owner as a person, tied to the login username, with a voice print and a face.

Stored as a `known_persons` row flagged `is_self` (so their face embeddings live in the same table
as everyone else's), with the name also on `patients.full_name`. Because it is all account data,
the web app and the Flutter app read and write the same profile.
"""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import face
from auth import get_current_user
from db import ensure_patient, supabase

router = APIRouter(prefix="/host", tags=["host"])

PLACEHOLDER = "Patient"   # what older code stored before the host had a name


def display_name(patient_id: str) -> str | None:
    """The host's name, or None if they have not set one."""
    rows = supabase.table("patients").select("full_name").eq("id", patient_id).limit(1).execute().data
    name = (rows[0]["full_name"] if rows else "") or ""
    return None if not name.strip() or name == PLACEHOLDER else name.strip()


def _self_person(patient_id: str) -> dict | None:
    rows = supabase.table("known_persons").select("*") \
        .eq("patient_id", patient_id).eq("is_self", True).limit(1).execute().data
    return rows[0] if rows else None


def ensure_self_person(patient_id: str, username: str | None = None) -> dict:
    """The host's person row, created on first use and named after the login username (unless the
    host has since chosen a display name). The name is also saved on `patients.full_name`."""
    person = _self_person(patient_id)
    if person:
        return person

    ensure_patient(patient_id)
    name = display_name(patient_id) or (username or "").strip() or "Me"
    supabase.table("patients").update({"full_name": name}).eq("id", patient_id).execute()
    person = supabase.table("known_persons").insert({
        "patient_id": patient_id, "name": name, "relationship": "Me", "is_self": True,
    }).execute().data[0]

    # a voice print enrolled before the host had a person row moves across
    voice = supabase.table("host_voice_profile").select("embedding") \
        .eq("patient_id", patient_id).limit(1).execute().data
    if voice:
        emb = voice[0]["embedding"]
        supabase.table("known_persons").update({
            "voice_embedding": json.loads(emb) if isinstance(emb, str) else emb,
        }).eq("id", person["id"]).execute()
    return person


def mirror_voice(patient_id: str, embedding: list[float], username: str | None = None) -> None:
    """A new voice enrollment also becomes the host person's voice print."""
    person = ensure_self_person(patient_id, username)
    supabase.table("known_persons").update({"voice_embedding": embedding}).eq("id", person["id"]).execute()


def profile(patient_id: str, username: str = "") -> dict:
    person = ensure_self_person(patient_id, username)
    voice = supabase.table("host_voice_profile").select("patient_id") \
        .eq("patient_id", patient_id).limit(1).execute().data

    faces = supabase.table("face_embeddings").select("id, image_b64, captured_at") \
        .eq("known_person_id", person["id"]).order("captured_at", desc=True).execute().data
    photo = next((f["image_b64"] for f in faces if f.get("image_b64")), None)

    return {
        "username": username or None,          # the login; the host's voice and face are tied to it
        "name": person["name"],                # shown as "You": defaults to the username
        "person_id": person["id"],
        "voice_enrolled": bool(voice),
        "face_enrolled": bool(faces),
        "face_count": len(faces),
        "photo_b64": photo,                    # small JPEG of the host, the same on every device
    }


@router.get("")
def get_host(user=Depends(get_current_user)):
    return profile(user["sub"], user["username"])


@router.put("")
def set_host_name(name: str = Form(...), user=Depends(get_current_user)):
    """Optionally give the host a display name other than the username (renames their person row)."""
    name = name.strip()
    if not name:
        raise HTTPException(400, "A name is required")
    patient_id = user["sub"]
    ensure_patient(patient_id)
    supabase.table("patients").update({"full_name": name}).eq("id", patient_id).execute()
    person = ensure_self_person(patient_id, name)
    if person["name"] != name:
        supabase.table("known_persons").update({"name": name}).eq("id", person["id"]).execute()
    face.embedding_cache.clear()          # names are cached with the face embeddings
    return profile(patient_id, user["username"])


@router.post("/face")
async def add_host_face(file: UploadFile = File(...), replace: bool = Form(False),
                        user=Depends(get_current_user)):
    """Enroll a photo of the host's face. The largest face in the photo is used. `replace=true`
    removes the host's earlier face photos first (a retake); otherwise photos accumulate."""
    patient_id = user["sub"]
    person = ensure_self_person(patient_id, user["username"])

    old = [] if not replace else supabase.table("face_embeddings").select("id") \
        .eq("known_person_id", person["id"]).execute().data
    try:
        added = await face.add_face_logic(file, person["id"])
    except face.InvalidImage as e:
        raise HTTPException(400, str(e))
    if not added:
        raise HTTPException(400, "No face found in the photo")

    if old:
        supabase.table("face_embeddings").delete().in_("id", [o["id"] for o in old]).execute()
        face.embedding_cache.clear()
    return profile(patient_id, user["username"])


@router.delete("/face")
def delete_host_faces(user=Depends(get_current_user)):
    patient_id = user["sub"]
    person = _self_person(patient_id)
    if person:
        supabase.table("face_embeddings").delete().eq("known_person_id", person["id"]).execute()
        face.embedding_cache.clear()
    return profile(patient_id, user["username"])
