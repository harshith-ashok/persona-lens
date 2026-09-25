# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PersonaLens assists patients with memory loss: it recognizes faces from a camera feed, transcribes conversations with Whisper, and stores an LLM-generated summary of the first and most recent interaction with each known person. Components: `backend/` (FastAPI), `frontend/` (Vue 3 dashboard), `mobile/` (Flutter; currently empty in git), and `supabase.sql` (schema). `vision-pro/` (visionOS app) was deleted from the working tree. `testing/getToken.js` fetches a Supabase access token for hitting the API manually.

There are no automated tests or linters configured.

## Commands

Backend (Python 3.10; needs `face_recognition`/dlib, `openai-whisper`, `opencv`):
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8120   # 0.0.0.0 so other machines (e.g. the Flutter app) can reach it
```

Frontend:
```bash
cd frontend && npm install
npm run dev          # http://localhost:5173
npm run type-check   # vue-tsc
npm run build        # type-check + vite build
npm run format       # prettier on src/
```

The backend also requires a local Ollama server (`http://localhost:11434`) with the `qwen3:8b` model pulled.

## Architecture

**Auth flow:** The frontend logs in via Supabase Auth directly and sends the access token as a Bearer header to the backend. [backend/auth.py](backend/auth.py) validates it with `supabase.auth.get_user` and returns `{"sub": user.id}`; that id is the `patient_id` used to scope all queries. The backend uses the Supabase **service-role** client ([backend/db.py](backend/db.py)), which bypasses RLS, so patient scoping is enforced manually in code (e.g. `.eq("known_persons.patient_id", ...)`), not by the database. Not every endpoint checks ownership (`/summary`, `/relation`, `/add-face` trust the given `person_id`).

**Backend modules** (flat, imported by bare name, so run from `backend/`):
- `main.py`: routes `/person`, `/add-face`, `/recognize`, `/process-interaction`, `/summary/{id}`, `/relation/{id}`, `/me`, `/health`.
- `face.py`: `face_recognition` (dlib) 128-d encodings; compares to stored embeddings by `face_distance` with a 0.6 threshold. Embeddings are cached per patient in the in-memory `embedding_cache`. `add_face_logic` clears the **entire** cache. The cache is process-local, so it breaks with multiple workers.
- `speech.py`: loads Whisper `base` at import time, transcribes the upload, calls `llm.generate_summary` (Ollama), inserts into `interaction_logs`, then creates or updates the single `interaction_summaries` row per person (first_* set once, last_* overwritten).
- `llm.py`: plain `requests` call to Ollama; returns `None` on failure.

**Frontend:** [frontend/src/views/Dashboard.vue](frontend/src/views/Dashboard.vue) is the main screen. It captures webcam frames and mic audio and calls the backend with axios. `Dashboard-v.vue` is an alternate or older variant. Routing is in `src/router/index.ts`, with Login and Register views.

**Schema:** [supabase.sql](supabase.sql) defines the tables and enables RLS on four of them (no policies are defined in the file). Note that it declares `face_embeddings.embedding` as `vector(512)`, but the code stores 128-d `face_recognition` encodings, so check for a mismatch before touching embeddings or the schema.

## Gotchas

- Supabase URL and keys are hardcoded: `db.py` contains `"SECRET"` placeholders that must be filled locally (never commit real keys; `backend/.env` was deleted from the repo), and the frontend and `testing/getToken.js` embed a project URL, an anon key and credentials. There is no env-var loading.
- CORS is `allow_origins=["*"]`.
- `backend/__pycache__` and `faces.pkl` are tracked in git.
- The README's flow diagram mentions Angular, but the web dashboard is Vue.
