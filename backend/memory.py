"""Ask your memory: index finished conversations, then answer questions from them.

Each session becomes a few embedded chunks (its summary, plus the transcript in small windows).
A question is answered by retrieving the closest chunks (pgvector, `match_memory`), adding a short
list of recent sessions (for "who visited this week?" style questions), and asking an LLM to answer
only from that context.
"""
import re
from datetime import datetime, timezone

import requests

import config
import host
from db import supabase

CHUNK_CHARS = 500      # transcript window size
TOP_K = 8
RECENT_SESSIONS = 10
MIN_SIMILARITY = 0.3   # below this a chunk is unrelated noise


def _embed(texts: list[str], prefix: str) -> list[list[float]]:
    res = requests.post(f"{config.OLLAMA_URL}/api/embed", json={
        "model": config.EMBED_MODEL,
        "input": [f"{prefix}: {t}" for t in texts],   # nomic-embed-text wants a task prefix
    }, timeout=60)
    res.raise_for_status()
    return res.json()["embeddings"]


def _vector(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def _windows(transcript: str) -> list[str]:
    """Group transcript lines into windows of about CHUNK_CHARS, never splitting a line."""
    out, cur = [], ""
    for line in (l.strip() for l in transcript.splitlines()):
        if not line:
            continue
        if cur and len(cur) + len(line) > CHUNK_CHARS:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    if cur:
        out.append(cur)
    return out


def index_session(patient_id: str, session_id: str, person_id: str | None, occurred_at: str,
                  transcript: str | None, summary: str | None) -> int:
    """(Re)build the chunks for one session. Returns how many were stored."""
    chunks = []
    if summary:
        chunks.append(("summary", summary))
    chunks += [("transcript", w) for w in _windows(transcript or "")]

    supabase.table("memory_chunks").delete().eq("session_id", session_id).neq("kind", "event").execute()
    if not chunks:
        return 0

    vectors = _embed([c for _, c in chunks], "search_document")
    supabase.table("memory_chunks").insert([{
        "patient_id": patient_id,
        "session_id": session_id,
        "person_id": person_id,
        "occurred_at": occurred_at,
        "kind": kind,
        "content": content,
        "embedding": _vector(vec),
    } for (kind, content), vec in zip(chunks, vectors)]).execute()
    return len(chunks)


def set_person(session_id: str, person_id: str) -> None:
    """A session was named after the fact: point its chunks at the person."""
    supabase.table("memory_chunks").update({"person_id": person_id}).eq("session_id", session_id).execute()


def reindex_all(patient_id: str) -> dict:
    """Index every finished session that has a transcript (for data recorded before this feature)."""
    sessions = supabase.table("sessions") \
        .select("id, person_id, started_at, summary") \
        .eq("patient_id", patient_id).in_("status", ["ended", "resolved"]).execute().data
    indexed = chunks = 0
    for s in sessions:
        log = supabase.table("interaction_logs").select("transcript") \
            .eq("session_id", s["id"]).limit(1).execute().data
        transcript = log[0]["transcript"] if log else ""
        if not transcript and not s["summary"]:
            continue
        chunks += index_session(patient_id, s["id"], s["person_id"], s["started_at"], transcript, s["summary"])
        indexed += 1
    return {"sessions": indexed, "chunks": chunks}


def _people_names(person_ids: set) -> dict:
    ids = [p for p in person_ids if p]
    if not ids:
        return {}
    rows = supabase.table("known_persons").select("id, name, relationship, is_self").in_("id", ids).execute().data
    return {r["id"]: r for r in rows}


def _parse_dt(ts: str) -> datetime:
    d = datetime.fromisoformat(re.sub(r"\.(\d+)", lambda m: "." + m.group(1).ljust(6, "0")[:6], ts.replace("Z", "+00:00")))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _fmt_date(ts: str) -> str:
    return _parse_dt(ts).strftime("%a %d %b %Y, %H:%M")


def ask(patient_id: str, question: str) -> dict:
    question = question.strip()
    if not question:
        return {"answer": "Ask me something about your conversations.", "sources": []}

    qvec = _embed([question], "search_query")[0]
    hits = supabase.rpc("match_memory", {"p_patient": patient_id, "p_query": _vector(qvec), "p_k": TOP_K}).execute().data
    hits = [h for h in hits if h["similarity"] >= MIN_SIMILARITY]

    recent = supabase.table("sessions") \
        .select("id, started_at, person_id, summary") \
        .eq("patient_id", patient_id).in_("status", ["ended", "resolved"]) \
        .order("started_at", desc=True).limit(RECENT_SESSIONS).execute().data

    items = supabase.table("life_events").select("kind, title, detail, occurs_on, amount, currency, is_done, created_at") \
        .eq("patient_id", patient_id).order("created_at", desc=True).limit(25).execute().data
    people = _people_names({h["person_id"] for h in hits} | {r["person_id"] for r in recent})

    def who(pid):
        p = people.get(pid)
        if p and p.get("is_self"):
            return "you"
        return f"{p['name']} ({p['relationship']})" if p and p.get("relationship") else (p["name"] if p else "an unnamed visitor")

    if not hits and not recent:
        return {"answer": "I don't have any recorded conversations yet.", "sources": []}

    context = "\n\n".join(f"[{_fmt_date(h['occurred_at'])}] with {who(h['person_id'])}:\n{h['content']}" for h in hits) or "(nothing closely related)"
    timeline = "\n".join(f"- {_fmt_date(r['started_at'])}: {who(r['person_id'])} — {r['summary'] or 'no summary'}" for r in recent)

    host_name = host.display_name(patient_id)
    host_label = host_name or "the host"
    host_alias = f' or "{host_name}"' if host_name else ""

    items_text = "\n".join(
        f"- [{i['occurs_on'] or i['created_at'][:10]}] {i['kind']}: {i['title']}"
        + (f" ({i['detail']})" if i.get("detail") else "")
        + (f" — {i['amount']:g} {i.get('currency') or ''}".rstrip() if i.get("amount") is not None else "")
        + (" [done]" if i.get("is_done") else "")
        for i in items)

    prompt = f"""You are a gentle memory assistant for a person with memory loss. Answer their question using ONLY the records below.
Rules:
- Reply in English in one to three short, plain sentences, and say who and when (use the record's date, not exact clock times, unless asked).
- Statements by the person asking (marked "Host") are records too: if they said they did something, that answers "did I...?".
- Wording may differ from the question; answer if a record covers it, even if the time of day is only approximate.
- If nothing in the records covers it, say exactly "I don't have a record of that." Never guess or invent.
- The person asking is {host_label} (shown as "Host"{host_alias} in transcripts); "Other" is a visitor whose name may be unknown.

Now: {datetime.now(timezone.utc).astimezone().strftime('%A %d %B %Y, %H:%M')}

Recent conversations (newest first):
{timeline or '(none)'}

Decisions, plans, money and to-dos noted from conversations:
{items_text or '(none)'}

Most relevant records:
{context}

Question: {question}
Answer:"""

    res = requests.post(f"{config.OLLAMA_URL}/api/generate",
                        json={"model": config.ASK_MODEL, "prompt": prompt, "stream": False},
                        timeout=config.SUMMARY_TIMEOUT)
    res.raise_for_status()
    answer = re.sub(r"<think>.*?</think>", "", res.json().get("response", ""), flags=re.S).strip()

    answer = answer or "I don't have a record of that."
    if answer.lower().startswith("i don't have a record"):
        return {"answer": answer, "sources": []}   # nothing to cite

    seen, texts, sources = set(), set(), []
    for h in hits:
        if h["session_id"] in seen or h["content"] in texts:
            continue
        seen.add(h["session_id"])
        texts.add(h["content"])
        sources.append({"session_id": h["session_id"], "date": h["occurred_at"],
                        "person_name": (people.get(h["person_id"]) or {}).get("name"),
                        "snippet": h["content"][:200], "similarity": round(h["similarity"], 2)})
    return {"answer": answer, "sources": sources[:4]}
