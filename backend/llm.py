import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_summary(transcript: str):
    try:
        prompt = f"""
        Summarize the conversation in 1–2 very short, easy-to-understand sentences for quick memory recall.

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
