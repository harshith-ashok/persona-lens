import re

import requests

from config import OLLAMA_URL, SUMMARY_MODEL, SUMMARY_TIMEOUT


def generate_summary(transcript: str):
    try:
        prompt = f"""
        Summarize the following conversation in 1-2 short, clear sentences for quick memory recall.

        Use first-person perspective for the patient (e.g., “enquired about YOUR day” instead of quoting full questions).
        Generalize personal or vague questions (like “how is your day?”) into concise, meaningful actions or intents.
        Focus on key events, topics, or interactions, ignoring filler or small talk.
        Keep it simple, actionable, and context-aware. Write the summary in English.

        Example:
        Input: "Patient: How are you today? Nurse: I'm fine, thanks. Patient: I feel dizzy."
        Output: "Patient enquired about YOUR day and reported feeling dizzy."

        Conversation:
        {transcript}
        """

        res = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": SUMMARY_MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=SUMMARY_TIMEOUT)
        res.raise_for_status()

        text = res.json().get("response", "")
        # local reasoning models (e.g. qwen3) prepend their reasoning in <think> tags
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    except Exception as e:
        print("Ollama error:", e)
        return None
