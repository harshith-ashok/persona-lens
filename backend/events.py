"""Life timeline: decisions, activities, events, money and to-dos.

Found automatically in each conversation by an LLM (only what was actually said), or added by hand.
They are shown as a timeline and are searchable through Ask your memory.
"""
import json
import re
from datetime import date, datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Depends, Form, HTTPException

import config
import memory
from auth import get_current_user
from db import ensure_patient, supabase

router = APIRouter(prefix="/timeline", tags=["timeline"])

KINDS = ("decision", "activity", "event", "money", "task")
MAX_ITEMS = 8


# ---------- extraction ----------
def _parse_date(value) -> str | None:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _clean(item: dict) -> dict | None:
    kind = str(item.get("kind", "")).lower().strip()
    title = str(item.get("title", "")).strip()
    if kind not in KINDS or not title:
        return None
    amount = item.get("amount")
    try:
        amount = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    return {
        "kind": kind,
        "title": title[:120],
        "detail": (str(item.get("detail") or "").strip()[:300]) or None,
        "occurs_on": _parse_date(item.get("date")),
        "amount": amount,
        "currency": (str(item.get("currency") or "").strip()[:8]) or None,
        "person": (str(item.get("person") or "").strip()) or None,
    }


def extract(transcript: str, host_name: str | None, when: datetime) -> list[dict]:
    """Ask the LLM for structured items from one conversation. Returns [] if there are none."""
    if not transcript or not transcript.strip():
        return []
    today = when.astimezone().date()
    # models get weekday arithmetic wrong, so hand them a calendar to read the dates from
    calendar = "\n".join(
        f"{(today + timedelta(days=d)).strftime('%A')} = {(today + timedelta(days=d)).isoformat()}"
        + (" (today)" if d == 0 else " (yesterday)" if d == -1 else "")
        for d in range(-3, 15))
    prompt = f"""From this conversation, list the things worth remembering about {host_name or "the host"}'s life.
Use ONLY what is actually said. If nothing qualifies, return an empty list. Never invent anything.

Item kinds:
- "decision": something {host_name or "the host"} decided or agreed to do
- "activity": something done or happening in their day (a visit, a walk, a meal)
- "event": an appointment, occasion or plan involving a date (visit, doctor, birthday)
- "money": a payment, bill, purchase, or amount owed or received (put the number in "amount")
- "task": a responsibility or reminder still to do (a medicine, a call, a chore)

Calendar (use it to turn days like "Monday" or "yesterday" into dates; a weekday means its next occurrence):
{calendar}
Give "date" as YYYY-MM-DD when a day is mentioned or clearly implied; otherwise null.

Reply with JSON only: {{"items":[{{"kind":"...","title":"short phrase","detail":"one sentence or null","date":"YYYY-MM-DD or null","amount":number or null,"currency":"e.g. INR/USD or null","person":"name of the visitor involved or null"}}]}}
At most {MAX_ITEMS} items.

Conversation:
{transcript}"""

    res = requests.post(f"{config.OLLAMA_URL}/api/generate",
                        json={"model": config.EVENTS_MODEL, "prompt": prompt, "stream": False, "format": "json"},
                        timeout=config.SUMMARY_TIMEOUT)
    res.raise_for_status()
    text = re.sub(r"<think>.*?</think>", "", res.json().get("response", ""), flags=re.S).strip()
    data = json.loads(text)
    items = data.get("items", []) if isinstance(data, dict) else data
    return [c for c in (_clean(i) for i in items if isinstance(i, dict)) if c][:MAX_ITEMS]


# ---------- storing ----------
def _effective_date(row: dict) -> str:
    return row.get("occurs_on") or (row.get("created_at") or "")[:10]


def _event_text(row: dict, person_name: str | None) -> str:
    bits = [f"{row['kind'].capitalize()}: {row['title']}"]
    if row.get("detail"):
        bits.append(row["detail"])
    if row.get("amount") is not None:
        bits.append(f"Amount: {row['amount']:g} {row.get('currency') or ''}".strip())
    if person_name:
        bits.append(f"With {person_name}")
    if row.get("is_done"):
        bits.append("(done)")
    return ". ".join(bits)


def _index_event(row: dict, person_name: str | None) -> None:
    """Make one event searchable in Ask your memory."""
    supabase.table("memory_chunks").delete().eq("event_id", row["id"]).execute()
    vec = memory._embed([_event_text(row, person_name)], "search_document")[0]
    supabase.table("memory_chunks").insert({
        "patient_id": row["patient_id"], "session_id": row.get("session_id"), "person_id": row.get("person_id"),
        "occurred_at": (row.get("occurs_on") or row["created_at"]),
        "kind": "event", "event_id": row["id"], "content": _event_text(row, person_name),
        "embedding": memory._vector(vec),
    }).execute()


def _names(patient_id: str) -> dict:
    rows = supabase.table("known_persons").select("id, name").eq("patient_id", patient_id).execute().data
    return {r["id"]: r["name"] for r in rows}


def save_session_events(patient_id: str, session_id: str, session_person_id: str | None, items: list[dict]) -> int:
    """Store the extracted items for a session (replacing any earlier automatic ones)."""
    old = supabase.table("life_events").select("id").eq("session_id", session_id).eq("source", "auto").execute().data
    if old:
        supabase.table("life_events").delete().in_("id", [o["id"] for o in old]).execute()
    if not items:
        return 0

    by_name = {n.lower(): i for i, n in _names(patient_id).items()}
    rows = supabase.table("life_events").insert([{
        "patient_id": patient_id, "session_id": session_id,
        "person_id": by_name.get((i["person"] or "").lower()) or session_person_id,
        "kind": i["kind"], "title": i["title"], "detail": i["detail"], "occurs_on": i["occurs_on"],
        "amount": i["amount"], "currency": i["currency"], "source": "auto",
    } for i in items]).execute().data

    names = _names(patient_id)
    for r in rows:
        try:
            _index_event(r, names.get(r.get("person_id")))
        except Exception as e:
            print("Event indexing skipped:", e)
    return len(rows)


def _view(row: dict, names: dict) -> dict:
    return {
        "id": row["id"], "kind": row["kind"], "title": row["title"], "detail": row["detail"],
        "occurs_on": row["occurs_on"], "date": _effective_date(row),
        "amount": float(row["amount"]) if row.get("amount") is not None else None,
        "currency": row["currency"], "is_done": row["is_done"], "source": row["source"],
        "person_id": row["person_id"], "person_name": names.get(row["person_id"]),
        "session_id": row["session_id"],
    }


def _owned(patient_id: str, event_id: str) -> dict:
    rows = supabase.table("life_events").select("*").eq("id", event_id).eq("patient_id", patient_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Event not found")
    return rows[0]


# ---------- routes ----------
@router.get("")
def timeline(kind: str | None = None, days: int = 90, open_only: bool = False, limit: int = 200,
             user=Depends(get_current_user)):
    """Newest first. `days` looks back that far (and includes anything in the future)."""
    patient_id = user["sub"]
    q = supabase.table("life_events").select("*").eq("patient_id", patient_id)
    if kind:
        if kind not in KINDS:
            raise HTTPException(400, f"kind must be one of {KINDS}")
        q = q.eq("kind", kind)
    if open_only:
        q = q.eq("kind", "task").eq("is_done", False)
    rows = q.order("created_at", desc=True).limit(1000).execute().data

    since = (datetime.now(timezone.utc) - timedelta(days=max(days, 1))).date().isoformat()
    rows = [r for r in rows if _effective_date(r) >= since]
    rows.sort(key=lambda r: (_effective_date(r), r["created_at"]), reverse=True)
    names = _names(patient_id)
    return {"events": [_view(r, names) for r in rows[:limit]]}


@router.get("/upcoming")
def upcoming(user=Depends(get_current_user)):
    """What is coming up: dated items from today on, plus open to-dos with no date."""
    patient_id = user["sub"]
    today = date.today().isoformat()
    rows = supabase.table("life_events").select("*").eq("patient_id", patient_id).eq("is_done", False) \
        .in_("kind", ["event", "task", "decision", "money"]).execute().data
    keep = [r for r in rows if (r["occurs_on"] and r["occurs_on"] >= today) or (r["kind"] == "task" and not r["occurs_on"])]
    keep.sort(key=lambda r: (r["occurs_on"] or "9999-12-31", r["created_at"]))
    names = _names(patient_id)
    return {"events": [_view(r, names) for r in keep[:50]]}


@router.post("")
def add_event(kind: str = Form(...), title: str = Form(...), detail: str = Form(None), occurs_on: str = Form(None),
              amount: float = Form(None), currency: str = Form(None), person_id: str = Form(None),
              user=Depends(get_current_user)):
    """Add an item by hand (for example a responsibility a caregiver wants remembered)."""
    patient_id = user["sub"]
    if kind not in KINDS:
        raise HTTPException(400, f"kind must be one of {KINDS}")
    if not title.strip():
        raise HTTPException(400, "A title is required")
    if occurs_on and not _parse_date(occurs_on):
        raise HTTPException(400, "occurs_on must be YYYY-MM-DD")
    ensure_patient(patient_id)

    row = supabase.table("life_events").insert({
        "patient_id": patient_id, "kind": kind, "title": title.strip()[:120],
        "detail": (detail or "").strip()[:300] or None, "occurs_on": _parse_date(occurs_on),
        "amount": amount, "currency": (currency or "").strip()[:8] or None,
        "person_id": person_id or None, "source": "manual",
    }).execute().data[0]
    names = _names(patient_id)
    try:
        _index_event(row, names.get(row["person_id"]))
    except Exception as e:
        print("Event indexing skipped:", e)
    return _view(row, names)


@router.patch("/{event_id}")
def update_event(event_id: str, title: str = Form(None), detail: str = Form(None), kind: str = Form(None),
                 occurs_on: str = Form(None), amount: float = Form(None), currency: str = Form(None),
                 is_done: bool = Form(None), user=Depends(get_current_user)):
    patient_id = user["sub"]
    _owned(patient_id, event_id)
    patch = {}
    if title is not None:
        if not title.strip():
            raise HTTPException(400, "A title is required")
        patch["title"] = title.strip()[:120]
    if detail is not None:
        patch["detail"] = detail.strip()[:300] or None
    if kind is not None:
        if kind not in KINDS:
            raise HTTPException(400, f"kind must be one of {KINDS}")
        patch["kind"] = kind
    if occurs_on is not None:
        if occurs_on == "":
            patch["occurs_on"] = None
        elif _parse_date(occurs_on):
            patch["occurs_on"] = _parse_date(occurs_on)
        else:
            raise HTTPException(400, "occurs_on must be YYYY-MM-DD")
    if amount is not None:
        patch["amount"] = amount
    if currency is not None:
        patch["currency"] = currency.strip()[:8] or None
    if is_done is not None:
        patch["is_done"] = is_done
    if not patch:
        raise HTTPException(400, "Nothing to change")

    row = supabase.table("life_events").update(patch).eq("id", event_id).execute().data[0]
    names = _names(patient_id)
    try:
        _index_event(row, names.get(row["person_id"]))
    except Exception as e:
        print("Event indexing skipped:", e)
    return _view(row, names)


@router.delete("/{event_id}")
def delete_event(event_id: str, user=Depends(get_current_user)):
    _owned(user["sub"], event_id)
    supabase.table("life_events").delete().eq("id", event_id).execute()   # its search chunk cascades
    return {"deleted": event_id}


@router.post("/reextract")
def reextract(user=Depends(get_current_user)):
    """Find items in older conversations that were recorded before the timeline existed."""
    patient_id = user["sub"]
    import host
    host_name = host.display_name(patient_id)
    sessions = supabase.table("sessions").select("id, person_id, started_at") \
        .eq("patient_id", patient_id).in_("status", ["ended", "resolved"]) \
        .order("started_at", desc=True).limit(50).execute().data
    have = {r["session_id"] for r in supabase.table("life_events").select("session_id").eq("patient_id", patient_id).execute().data}

    done = created = 0
    for s in sessions:
        if s["id"] in have:
            continue
        log = supabase.table("interaction_logs").select("transcript").eq("session_id", s["id"]).limit(1).execute().data
        transcript = log[0]["transcript"] if log else ""
        if not transcript:
            continue
        when = memory._parse_dt(s["started_at"])
        try:
            created += save_session_events(patient_id, s["id"], s["person_id"], extract(transcript, host_name, when))
            done += 1
        except Exception as e:
            print("Re-extract skipped for", s["id"], e)
    return {"sessions": done, "events": created}
