"""Central settings. Every stage's local-vs-cloud choice is an env var (backend/.env), no code change needed."""
import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# --- Transcription: "local" (openai-whisper on this machine) or "openai" (hosted, needs OPENAI_API_KEY)
TRANSCRIBE_BACKEND = os.getenv("TRANSCRIBE_BACKEND", "local")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
# Speech is always transcribed as this language (skips auto-detection, which also stops noise being "detected" as another language)
TRANSCRIBE_LANGUAGE = os.getenv("TRANSCRIBE_LANGUAGE", "en")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")

# --- Summaries: any model Ollama can serve, e.g. "gpt-oss:120b-cloud" (cloud) or "qwen3:8b" (local)
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gpt-oss:120b-cloud")
SUMMARY_TIMEOUT = float(os.getenv("SUMMARY_TIMEOUT", "60"))

# --- Vision: "cloud" (Ollama Cloud, dlib fallback) or "local" (dlib only)
VISION_BACKEND = os.getenv("VISION_BACKEND", "cloud")
VISION_MODEL = os.getenv("VISION_MODEL", "gemma4:31b-cloud")
VISION_TIMEOUT = float(os.getenv("VISION_TIMEOUT", "8"))
VISION_COOLDOWN = float(os.getenv("VISION_COOLDOWN", "30"))

# --- Voice (pyannote, always local): "auto" picks cuda > mps > cpu
VOICE_DEVICE = os.getenv("VOICE_DEVICE", "auto")
HF_TOKEN = os.getenv("HF_TOKEN")
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "pyannote/wespeaker-voxceleb-resnet34-LM")
VOICE_MATCH_THRESHOLD = float(os.getenv("VOICE_MATCH_THRESHOLD", "0.6"))

# --- Startup: load models in the background so the first session isn't slow
WARMUP = os.getenv("WARMUP", "1") == "1"

# --- Ask your memory: embeddings via Ollama, answers via ASK_MODEL (defaults to the summary model)
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
ASK_MODEL = os.getenv("ASK_MODEL", SUMMARY_MODEL)

# --- Photo gallery: uploaded images are stored on this machine (Supabase Storage isn't part of the local stack)
GALLERY_DIR = os.getenv("GALLERY_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "gallery"))
GALLERY_MAX_MB = float(os.getenv("GALLERY_MAX_MB", "25"))

# --- Video of vision sessions (opt-in from the app); stored on this machine
VIDEO_DIR = os.getenv("VIDEO_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "videos"))
VIDEO_MAX_MB = float(os.getenv("VIDEO_MAX_MB", "300"))
EVENTS_MODEL = os.getenv("EVENTS_MODEL", ASK_MODEL)
