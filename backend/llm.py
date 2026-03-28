import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_summary(transcript: str):
    try:
        prompt = f"""
        Summarize the following conversation in 1-2 short, clear sentences for quick memory recall.

        Use first-person perspective for the patient (e.g., “enquired about YOUR day” instead of quoting full questions).
        Generalize personal or vague questions (like “how is your day?”) into concise, meaningful actions or intents.
        Focus on key events, topics, or interactions, ignoring filler or small talk.
        Keep it simple, actionable, and context-aware.

        Example:
        Input: "Patient: How are you today? Nurse: I'm fine, thanks. Patient: I feel dizzy."
        Output: "Patient enquired about YOUR day and reported feeling dizzy."

        Conversation:
        {transcript}
        """

        res = requests.post(OLLAMA_URL, json={
            "model": "qwen3:8b",
            "prompt": prompt,
            "stream": False
        })

        data = res.json()
        return data.get("response", "").strip()

    except Exception as e:
        print("Ollama error:", e)
        return None
