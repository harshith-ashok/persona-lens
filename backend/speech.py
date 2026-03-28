import whisper
import tempfile
import os
from db import supabase
from llm import generate_summary

model = whisper.load_model("base")


async def process_audio(file, patient_id, person_id=None):
    try:
        # 💾 Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(await file.read())
            path = tmp.name

        # 🎤 Transcribe
        result = model.transcribe(path)
        transcript = result.get("text", "").strip()

        print("🧠 TRANSCRIPT:", transcript)

        # 🧠 Generate summary (ONLY if person exists)
        summary = None
        if person_id and transcript:
            summary = generate_summary(transcript)

        # 🗄️ Save interaction log
        log = supabase.table("interaction_logs").insert({
            "patient_id": patient_id,
            "known_person_id": person_id,
            "transcript": transcript
        }).execute()

        log_id = log.data[0]["id"]

        # 🧠 Update summaries
        if person_id and summary:
            existing = supabase.table("interaction_summaries") \
                .select("*") \
                .eq("known_person_id", person_id) \
                .limit(1) \
                .execute()

            if not existing.data:
                # ✅ FIRST TIME
                supabase.table("interaction_summaries").insert({
                    "known_person_id": person_id,
                    "first_summary": summary,
                    "first_occurred_at": "now()",
                    "first_log_id": log_id,
                    "last_summary": summary,
                    "last_occurred_at": "now()",
                    "last_log_id": log_id
                }).execute()
            else:
                # ✅ UPDATE LAST
                supabase.table("interaction_summaries").update({
                    "last_summary": summary,
                    "last_occurred_at": "now()",
                    "last_log_id": log_id
                }).eq("known_person_id", person_id).execute()

        return {
            "transcript": transcript,
            "summary": summary,
            "log_id": log_id
        }

    except Exception as e:
        print("Process audio error:", e)
        return {"error": str(e)}

    finally:
        if os.path.exists(path):
            os.remove(path)
