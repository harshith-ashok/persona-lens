import os
import assemblyai as aai
import tempfile
from db import supabase

aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")


async def process_audio(file, patient_id, person_id=None):

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        path = tmp.name

    try:
        config = aai.TranscriptionConfig(
            speaker_labels=True
        )

        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(path, config=config)

        if transcript.status == "error":
            return {"error": transcript.error}

        full_text = transcript.text

        segments = []
        if transcript.utterances:
            for utt in transcript.utterances:
                segments.append({
                    "speaker": f"Speaker {utt.speaker}",
                    "text": utt.text,
                    "start": utt.start / 1000,
                    "end": utt.end / 1000
                })

        log = supabase.table("interaction_logs").insert({
            "patient_id": patient_id,
            "known_person_id": person_id,
            "transcript": full_text
        }).execute()

        return {
            "transcript": full_text,
            "segments": segments,
            "log_id": log.data[0]["id"]
        }

    finally:
        os.remove(path)
