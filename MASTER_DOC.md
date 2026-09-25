# PersonaLens: Master Context Document

Purpose: give a fresh chat (or a new teammate) full context on what this project is, why it exists, how it is built, what it can do today, and where it stands. Part 2 of this document is a **pitch pack**: content for a sales/pitch deck.

Related documents: [CLAUDE.md](CLAUDE.md) (commands and code-level guidance), [README.md](README.md) (setup basics), [docs/MOBILE_INTEGRATION.md](docs/MOBILE_INTEGRATION.md) (complete API contract and build guide for the Flutter app), [new_things.md](new_things.md) (product roadmap), [TODO.md](TODO.md) (the original implementation checklist).

Contents
- **Part 1 — Project reference:** 1 Problem · 2 Team · 3 Product at a glance · 4 Tech stack · 5 Architecture · 6 API · 7 Data model · 8 Main user flows · 9 Running it · 10 Configuration · 11 Measured performance · 12 State, limits and known issues
- **Part 2 — Pitch pack:** 13 Positioning · 14 Slide-by-slide outline · 15 Demo script · 16 Proof points · 17 Objections and honest answers · 18 Roadmap · 19 Claims to avoid

---

# Part 1 — Project reference

## 1. Problem statement

People with memory impairment (e.g. dementia, amnesia) often fail to recognize familiar people or to recall what was last discussed with them. This causes distress for the patient and strain for caregivers and family.

PersonaLens is an assistive system that acts as an external memory:

1. **Recognize** who is in front of the patient, from their face (camera or photo) and from their **voice**.
2. **Recall** context at the moment it matters: name, relationship, when they were last seen, and a short summary of the last conversation (plus a permanent summary of the first).
3. **Record** conversations with **live captions**, separate who said what (the patient versus the visitor), and summarize each one with an LLM so the context stays up to date.
4. **Handle new people** by naming them on the spot or later, from a session or from a photo.
5. **Answer questions** about past conversations in plain language ("Who brought me flowers?").

Design constraints from the team's requirements:
- The first-interaction summary is permanent; the latest interaction is kept as "last".
- Users are per-patient; data syncs between the web app and the mobile app through the shared backend.
- Voice work (speech-to-text, speaker separation, voice matching) runs on the backend host. Summaries, question answering and face verification use cloud models through Ollama, with a local face-matching fallback. See section 12 for exactly what stays local.

## 2. Team and ownership (from requirements.md)

| Area | Owner |
| --- | --- |
| Backend / Supabase (storage, users, sync) | Bhavesh Binudev |
| API (Whisper, face recognition, AI summaries) | Harshith Ashok |
| Web frontend | Siddhanth |
| Mobile frontend (Flutter) | Vakulabhushan Nandhagopal |

## 3. Product at a glance

What exists today (web app plus backend; the Flutter app is built against the same backend using [docs/MOBILE_INTEGRATION.md](docs/MOBILE_INTEGRATION.md)).

| Capability | What it does | Where |
| --- | --- | --- |
| **Viewfinder with AR tags** | Live camera; a box and label follow each face; shows "verifying" first, then the confirmed name | Web |
| **Recall card** | When someone is recognized (face or voice): name, relationship, "last seen 3 days ago", "last time: …" | Web (+ documented for mobile) |
| **Live captions** | Text appears ~1.5–2 s after speech, labeled host / other / a known person's name | Web, mobile (WebSocket) |
| **Sessions** | Vision (camera + mic) or voice-only; ends automatically after 15 s of silence in voice mode | Web, mobile |
| **Speaker separation + voice recognition** | Separates the patient's voice from the visitor's; recognizes returning people by voice alone | Backend |
| **Host profile ("You")** | The username is the host's identity; their voice and face are enrolled once and tied to it, shared by web and app; the host shows as "You", never as a visitor | Web, mobile |
| **Summaries** | 1–2 sentence, first-person-style summary of each conversation | Backend |
| **Name people later** | After a conversation, from History, or from a photo: new person or "someone I know" | Web, mobile |
| **People and history** | Everyone known, first/last summaries, session list with speaker balance | Web, mobile |
| **Life timeline** | Decisions, activities, events, money and to-dos found automatically in conversations, with real dates, "Coming up", filters, tick-off to-dos, manual items | Web, mobile |
| **People closeness** | Each person is labeled Very close / Regular / Occasional from who they are and how often they appear | Web, mobile |
| **Optional conversation video** | Camera video of vision sessions, kept on your own backend and watchable or deletable from History | Web, mobile |
| **Ask your memory** | Typed or spoken questions answered only from recorded conversations, with sources | Web (+ mobile spec) |
| **Photo identification** | Upload a photo; get names and boxes for every face, final answer in ~1 s | Backend, mobile |
| **Live camera recognition on mobile** | Camera tags with "verifying" then confirmed names; the backend rotates and mirrors phone frames on request | Backend done; Flutter side specified in the guide (§11.6) |
| **Photo gallery** | Every uploaded photo is stored with each face's embedding; filter by person, "who is this?" queue, find photos by example | Backend, mobile |
| **Big & simple mode** | Large text, high contrast, one big button, hold to exit | Web (+ mobile spec) |
| **Username login** | Username + password only (no email) | Web, mobile |

## 4. Tech stack

| Layer | Technology |
| --- | --- |
| Web app | Vue 3, Vite, Axios, vue-router, Supabase JS (auth); custom HUD styling ([frontend/src/assets/hud.css](frontend/src/assets/hud.css)); design reference `ref.html` |
| API | Python 3.10, FastAPI, Uvicorn (port 8120), WebSocket for live captions |
| Face detection / encodings | OpenCV + `face_recognition` (dlib), 128-d encodings, runs locally |
| Face identification (primary) | Vision model `gemma4:31b-cloud` via Ollama: prompt-based matching against stored reference photos; falls back automatically to dlib on any error |
| Speech-to-text | OpenAI Whisper `base`, local, **English only** (optional hosted transcription flag, untested) |
| Speaker separation and voice matching | `pyannote.audio` (diarization `speaker-diarization-community-1`, embeddings `wespeaker-voxceleb-resnet34-LM`), local, on GPU (Apple MPS / CUDA) when available |
| Summaries and answers | Ollama, default `gpt-oss:120b-cloud` (switchable; `gemma4:31b-cloud` is faster) |
| Memory search | `nomic-embed-text` embeddings in pgvector (768-d) |
| Database and auth | Self-hosted Supabase in Docker: Postgres (+pgvector), GoTrue (auth), PostgREST, nginx gateway on port 8000. The backend uses the service-role key |
| Images | Stored as files on the backend host (`backend/data/gallery/`); the local stack has no Supabase Storage |
| Mobile | Flutter + `supabase_flutter`, `dio`, `record`, `web_socket_channel` (built on another machine from the guide) |

The original design docs said Angular for the web app; the implemented app is Vue 3. The README diagram still says Angular.

## 5. Architecture

```
Web (Vue) ──┐                                       ┌─> Supabase Postgres (+pgvector)  ← docker compose :8000
            ├─ Bearer JWT / WebSocket ─> FastAPI ───┤
Mobile ─────┘   (Supabase Auth token)    :8120      ├─> Local models: Whisper, pyannote, dlib
                                                    └─> Ollama (cloud models): summaries, Ask, face verification, embeddings
```

**Auth:** clients sign in with Supabase Auth directly and send the access token as `Authorization: Bearer`. Usernames are mapped to a synthetic email (`<username>@persona-lens.local`) because the auth service requires one. [backend/auth.py](backend/auth.py) validates the token and uses the user id as `patient_id`; every registered user is one patient. The backend uses the service-role client, so patient scoping is enforced in code.

**A session end to end**
1. `POST /session/start`, then audio streams to `/ws/live` (16 kHz mono PCM). Live captions come back (partial and final lines with a speaker label).
2. `POST /session/{id}/end` returns immediately (`processing`); the server keeps the streamed audio, so nothing is uploaded twice.
3. In the background: Whisper transcribes and pyannote separates speakers **in parallel**, then the LLM summarizes; the result is saved and the conversation is indexed for Ask.
4. Clients poll `GET /session/{id}` until `ended` (nobody identified: can be named) or `resolved` (identified, by a face passed in or by voice), or `failed`.

**Face recognition.** Live video: `/recognize` answers instantly with the local guess (`identifying: true`) and verifies with the cloud model in the background, keyed by a stable per-face `track_id`. Still photos: `/recognize?wait=true` waits for the cloud and answers once.

**Backend files** (all in `backend/`, flat imports)
- [main.py](backend/main.py): app, routes, start-up warm-up.
- [auth.py](backend/auth.py), [db.py](backend/db.py), [config.py](backend/config.py) (every local-vs-cloud choice is an environment variable).
- [face.py](backend/face.py), [vision.py](backend/vision.py): detection, dlib matching, cloud verification, tracks.
- [speech.py](backend/speech.py), [voice.py](backend/voice.py), [live.py](backend/live.py), [session.py](backend/session.py): transcription, speaker models, live captions, session state machine.
- [llm.py](backend/llm.py), [memory.py](backend/memory.py): summaries; embedding index and question answering.
- [gallery.py](backend/gallery.py): stored photos with face embeddings.

**Frontend** (`frontend/src/`): [Dashboard.vue](frontend/src/views/Dashboard.vue) is the viewfinder; components for the recall card, session card, name prompt, voice enrollment, drawer (People, History, Ask, Voice, More), live waveform and toasts; composables for the recorder, silence detection, live captions and face tags.

## 6. API endpoints

All require `Authorization: Bearer <token>` except `/health`. Full request/response shapes are in [docs/MOBILE_INTEGRATION.md](docs/MOBILE_INTEGRATION.md).

| Endpoint | Purpose |
| --- | --- |
| `GET /health`, `GET /me` | Liveness; the caller's patient id |
| `POST /session/start`, `POST /session/{id}/end`, `GET /session/{id}` | Session lifecycle (start, finish and process in the background, poll the result) |
| `WS /ws/live` | Live captions for an open session |
| `POST /person/finalize` | Name the person from an unidentified session (new or existing) |
| `GET /host`, `PUT /host`, `POST /host/face`, `DELETE /host/face` | The host as a person, tied to the login username: profile and face photo |
| `GET /voice/prompts`, `POST /voice/enroll/clip`, `POST /voice/enroll/finish`, `WS /ws/live` (purpose `enroll`), `GET /voice/status` | Guided voice setup: sentences to read, live "what I heard" text, a per-sentence check, then the voice print from all clips (`POST /voice/enroll` is the one-clip shortcut) |
| `POST /recognize` (`?wait=true` for still photos; `?rotate=90&mirror=true` for phone camera frames) | Detect and identify faces in an image |
| `POST /person` (name, relationship, optional photo), `POST /add-face` | Create a person (optionally with their face); add more photos |
| `GET /people`, `GET /sessions` | Known people with summaries; history |
| `POST /ask`, `POST /memory/reindex` | Answer a typed or spoken question from past conversations; index older sessions |
| `POST /gallery`, `GET /gallery`, `GET /gallery/{id}` (+ `/thumb`, `/image`), `DELETE /gallery/{id}` | Photo gallery |
| `POST /gallery/faces/{id}/assign`, `POST /gallery/reidentify`, `POST /gallery/search` | Name a face; re-try unidentified faces; find photos by example |
| `GET /timeline`, `GET /timeline/upcoming`, `POST /timeline`, `PATCH /timeline/{id}`, `DELETE /timeline/{id}`, `POST /timeline/reextract` | The life timeline: decisions, activities, events, money and to-dos (found automatically, or added by hand) |
| `GET /session/{id}/video`, `DELETE /session/{id}/video` (video is sent with `POST /session/{id}/end`) | Optional video of a vision session |
| `GET /summary/{id}`, `GET /relation/{id}`, `POST /process-interaction` | Older endpoints, still working (the last is a legacy single-shot upload) |

## 7. Data model

Schema: [supabase.sql](supabase.sql) plus incremental, idempotent migrations in [migrations/](migrations/) (001–008), which docker compose also applies on a fresh database.

| Table | Holds |
| --- | --- |
| `patients`, `known_persons` | Users; the people they know (name, relationship, **voice embedding**). The host is a `known_persons` row flagged `is_self`, named after the username |
| `face_embeddings` | dlib 128-d encodings plus a small reference photo per enrolled face |
| `sessions` | One row per conversation: mode, status, summary, speaker-labeled lines, the other speaker's voice embedding, saved face frame, per-stage timings |
| `interaction_logs`, `interaction_summaries` | Transcript per encounter; one row per person with first and last summary |
| `host_voice_profile` | The host's voice print |
| `memory_chunks` | Embedded summary and transcript windows for Ask your memory |
| `gallery_images`, `gallery_faces` | Stored photos; each face's box, 128-d embedding, and match |
| `life_events` | Decisions, activities, events, money and to-dos: kind, title, detail, date, amount, done, and where they came from |
| `person_notes` | Exists, not used yet |

## 8. Main user flows

1. **Register / log in** with a username. First run: record the host's voice (skippable).
2. **Start a session** (camera + voice, or voice only). Faces get tags; a recall card shows who they are and what you last discussed; captions stream live with speaker labels.
3. **End** (tap, or after 15 s of silence in voice mode). The summary and speaker balance appear; if someone new spoke or was seen, the app offers to name them.
4. **Name later** from History ("Name this person") with the saved photo, as a new or existing person. Next time that voice or face is recognized automatically.
5. **Ask** ("Who visited me recently?") by typing or speaking.
6. **Photos:** identify a face from a picture; keep pictures in the gallery; name faces and find every photo of a person.
7. **Big & simple mode** for patients: large type, one button.

## 9. Running it

1. Run `./docker/gen-env.sh` once (creates the root `.env` with fresh keys), then `docker compose up -d` (Supabase on port 8000; database on 54322).
2. Ollama running with the models pulled: `gpt-oss:120b-cloud`, `gemma4:31b-cloud`, `nomic-embed-text` (embeddings), signed in for cloud models.
3. Backend: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`, put `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` and `HF_TOKEN` in `backend/.env`, then `uvicorn main:app --reload --host 0.0.0.0 --port 8120` (**`--host 0.0.0.0` is required for the Flutter app on another machine**). Accept the Hugging Face model terms for the pyannote models.
4. Web: `cd frontend && npm install && npm run dev`; `frontend/.env.local` holds the Supabase URL/anon key and `VITE_API_URL`.
5. Verify from another machine: `curl http://<host>:8120/health`.

## 10. Configuration (backend/.env; see `.env.example`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `VISION_BACKEND` / `VISION_MODEL` | `cloud` / `gemma4:31b-cloud` | Cloud face verification with dlib fallback, or `local` for dlib only |
| `TRANSCRIBE_BACKEND` / `WHISPER_MODEL` / `TRANSCRIBE_LANGUAGE` | `local` / `base` / `en` | Transcription; hosted (`openai`) is an untested option; English only |
| `SUMMARY_MODEL`, `ASK_MODEL` | `gpt-oss:120b-cloud` | Any Ollama model (a local one is impractical on the dev machine) |
| `EMBED_MODEL` | `nomic-embed-text` | Memory search embeddings |
| `VOICE_DEVICE`, `VOICE_MATCH_THRESHOLD` | `auto`, `0.6` | GPU/CPU for pyannote; voice-match distance |
| `GALLERY_DIR`, `GALLERY_MAX_MB` | `backend/data/gallery`, `25` | Photo storage |
| `WARMUP` | `1` | Load the models at start-up |

## 11. Measured performance (dev machine, warm, local tests)

| What | Result |
| --- | --- |
| A 17-second conversation, end to end after it ends | ≈ 2.7 s (transcribe 0.8 s ∥ speaker separation 0.6–0.9 s on GPU, then summary 1.2–1.7 s). Before the changes: ≈ 9 s |
| Time to first live caption | ≈ 1.5–2 s after speech starts |
| Photo identification (11-megapixel photo) | ≈ 1.1 s with a confirmed answer (was 2.7 s) |
| Live video recognition, known face | Boxes immediately; confirmed within ≈ 1.3 s; repeats ≈ 0.25 s |
| End a session request | ≈ 30 ms (processing runs in the background) |
| 3 sessions finishing at once | ≈ 6 s wall time (the two speech models queue) |
| Speaker separation accuracy | Clean on synthetic voices; **not yet measured on real recordings** |

These are measurements from a development laptop with synthetic test audio and a few test photos, not clinical results.

## 12. Current state, limits and known issues

**Where data goes.** Stays on the backend host: audio (deleted after processing), Whisper transcription, speaker separation and voice matching, dlib face detection, the database, and stored photos. Sent to cloud models through Ollama: conversation text (for summaries and Ask), face crops with reference photos (for face verification unless `VISION_BACKEND=local`). Do not describe the product as "fully on-device".

**Known limits and debt**
- **Recognition accuracy is unmeasured on real family photos.** Cloud matching was only tried on a handful of well-known faces, which the model may recognize from training. A wrong name is the biggest product risk; a "not sure" state and a correct-me button are planned.
- **No automated tests** beyond hand-run end-to-end checks.
- **Authorization gaps:** `/summary/{id}` and `/relation/{id}` still trust the id they are given; the web route guard is weak. Newer endpoints scope every query to the signed-in user.
- **Secrets:** the original Supabase URL, anon key and login credentials are in git history (the project they belonged to appears unreachable); rotate anything still live. CORS is `*`.
- **Process-local state:** the face-embedding cache and face tracks live in one process, so multiple workers would break them. Sessions that were processing during a restart are marked failed.
- **English only** by decision. Non-English speech is transcribed as garbled English.
- **Hosted transcription** (`TRANSCRIBE_BACKEND=openai`) and **HEIC photos** are untested.
- **Background/standby listening** on mobile is not built (needs an Android foreground service / iOS background audio).
- **No edit or delete for people or sessions**, no caregiver accounts, no notifications (all in [new_things.md](new_things.md)).
- **Repo hygiene:** `__pycache__` and `faces.pkl` are tracked in git.
- Unused schema: `person_notes`, and `ai_context_prompt` / `photo_url` on `known_persons`.
- Deleting a gallery photo does not remove recognition photos added when a face was named from it.

---

# Part 2 — Pitch pack (for a sales / pitch deck)

Written for whoever builds the deck. Everything below is grounded in what exists today; anything not built is labelled **Roadmap**. Items marked **[fill in]** need the team's own data (market, pricing, traction) — none of it is in this repo, so it is not invented here.

## 13. Positioning

**One line:** PersonaLens is an external memory for people with memory loss: it tells them who is in front of them and what they last talked about, and remembers every conversation for them.

**10-second version:** "When someone walks up, PersonaLens says who they are and what you talked about last time. It captions conversations live and remembers them so you can ask later."

**30-second version:** "For a person with memory loss, the hardest moment is when someone walks up and they can't place them. PersonaLens recognizes people by face and by voice, and shows their name, relationship and a short summary of the last conversation, right then. It captions the conversation live, tells who said what, writes a short summary, and lets you ask questions like 'who visited me this week?'. Family and caregivers add people from photos, and everything is tied to one account that works on the web and in a mobile app."

**Who it is for:** the person with memory loss (patient), and their family or caregiver (who set it up and want peace of mind). Buyers are most likely families and care providers **[fill in: target segment]**.

**Why it is different (defensible, from what is built)**
1. **Two ways to know who it is: face and voice.** It also recognizes people by voice alone, from a voiceprint learned the first time they are named.
2. **Recall at the moment of need**, not just a log: a card with name, relationship, last seen and last summary.
3. **Conversations, not just faces:** live captions, who-said-what, summaries, and question answering over everything said.
4. **Gets better as it is used:** every person named, from a session or a photo, improves recognition everywhere.
5. **Made to fail safely:** if the cloud model is unavailable, face matching falls back to a local model automatically; a face is shown as "verifying" until confirmed.
6. **Built for the patient:** big, high-contrast, one-button mode.

## 14. Slide-by-slide outline

Suggested 12–14 slides. Each has the message, the content, and a suggested visual.

1. **Title** — "PersonaLens: an external memory." Tagline: *Who is this, and what did we last talk about?* Visual: the viewfinder with a recall card.
2. **The problem** — Memory loss makes familiar people and past conversations slip away; distress for the patient, strain on the family. Use the team's own framing; add a credible statistic **[fill in: cited source]**. Visual: a simple before/after moment (a visitor walks in).
3. **Who feels it** — The patient (in the moment), the family (reassurance and setup), the caregiver (continuity). One line each.
4. **The solution** — Three pillars: **Recognize** (face and voice), **Recall** (name, relationship, last conversation), **Record** (live captions, summaries, ask anything). Visual: three icons.
5. **How it works** — The diagram in section 5, simplified: camera and microphone → PersonaLens → a card and captions. Add one line: "Works on web today; a mobile app uses the same account."
6. **The key moment (demo slide)** — A screenshot sequence: face recognized → recall card ("Meera · Daughter · last seen 2 days ago · last time: …") → live captions with host/other labels. Visual: three stacked screenshots from the web app.
7. **Conversations that remember** — Live captions ~2 s behind speech, who-said-what, an auto summary, and **Ask your memory** with sources. Visual: an Ask answer with its source snippet.
8. **It learns the people in your life** — Add someone from a photo, or name them after a conversation; from then on they are recognized by face and by voice. Photo gallery groups every photo by person. Visual: the gallery "Who is this?" queue.
9. **Designed for the patient** — Big & simple mode: one button, large captions, high contrast. Visual: side-by-side normal and simple mode.
10. **Trust and safety** — Be plain: audio and voice recognition stay on the host machine; conversation text and face crops go to the cloud AI service (with a local-only face option); cloud face matching falls back to local; a face shows "verifying" before it is confirmed. **Roadmap:** a "not sure" state, a correct-me button, data export and delete. Do not overclaim (see section 19).
11. **Proof it works** — The measured numbers in section 16, labelled as development measurements. Visual: three big numbers (≈3 s to a finished summary, ≈2 s to first caption, ≈1 s to identify a photo).
12. **Roadmap** — From [new_things.md](new_things.md): speak the recall card aloud, caregiver accounts and notes, follow-ups pulled from conversations, daily digest, offline mode, standby listening on mobile. Visual: a three-column now / next / later.
13. **Business model** — **[fill in: who pays (family subscription, care provider licence), price, cost per user]**. Cost drivers that are real: cloud AI calls per conversation and per new face; local compute for speech models.
14. **Team and ask** — Names and roles from section 2; the ask **[fill in: pilot partners, funding, introductions]** and next steps (a pilot with a small number of families **[fill in]**).

## 15. Demo script (about 90 seconds)

Set up: one enrolled "family member" with a couple of past conversations; the presenter's voice enrolled; web app in the viewfinder.

1. **(10 s)** "Someone I know is walking up." Start a session; the family member's face appears with a tag: verifying → confirmed. The recall card shows name, relationship, "last seen 2 days ago", and "last time: they promised to bring the grandchildren".
2. **(25 s)** Have a short two-person exchange. Captions appear live, colored for you versus the visitor.
3. **(15 s)** Stay silent: the countdown shows and the session ends by itself. The card shows the summary and who spoke how much.
4. **(20 s)** Introduce a stranger, then "name them" from the prompt (or from History): "Next time, it knows them, by face and by voice."
5. **(20 s)** Open Ask and say "Who visited me recently?". The answer appears with its source.
6. **(optional, 10 s)** Switch on Big & simple mode to show the patient's view.

Have a recorded backup of the demo in case the network or a cloud model is unavailable.

## 16. Proof points you can state (with the right caveat)

Say "measured in our development environment", not "guaranteed".

- **~2.7 s** from the end of a 17-second conversation to a finished, speaker-labeled summary (was ~9 s before optimization).
- **~1.5–2 s** to the first live caption.
- **~1 s** to identify everyone in a photo (11-megapixel photos included).
- **Two independent signals** (face and voice) that both improve as people are named.
- **Automatic fallback** to a local face matcher if the cloud model is unavailable (tested by making the cloud unreachable).
- **Per-user privacy scoping** in the newer endpoints (tested: a second account sees none of the first account's data).

## 17. Objections and honest answers

- **"Is it private?"** Audio, transcription, speaker separation and voice recognition run on the backend host and audio is deleted after processing. Conversation text and face crops are sent to a cloud AI service for summaries, question answering and face verification. A local-only face-matching option exists; a fully local summary model is possible but impractical on the current hardware. Data export and delete controls are on the roadmap.
- **"What if it names the wrong person?"** It is the top risk we are designing around: a face stays "verifying" until confirmed, and the roadmap adds a "not sure" state and a correct-me button. Accuracy on real family photos has not been measured yet; that is the first thing a pilot should measure.
- **"Does it work offline?"** Not yet. It needs the backend reachable. Offline queueing is on the roadmap.
- **"Which languages?"** English only, by decision.
- **"Does it run all day on a phone?"** Not yet. Live listening in the background on a phone needs platform work that is on the roadmap; today a person starts a session or opens the app.
- **"Who sets it up?"** Today the same account does setup and use; separate caregiver accounts are the largest planned item.
- **"What does it cost to run?"** Local compute for the speech models, plus cloud AI calls per conversation and per new face **[fill in: measured cost per user per month]**.

## 18. Roadmap (from new_things.md, in priority order)

**Now (safety and value):** measure recognition on real photos; "not sure" handling and a correct-me button; recall card everywhere (done on web); manage people (edit, merge, delete).
**Next (usable by a family):** guided first-run setup; batch import of people from the phone's gallery; caregiver notes; follow-ups pulled from conversations; **caregiver accounts**.
**Later (magic and reach):** speak the recall card aloud; daily digest and timeline; offline mode; push notifications; standby listening on mobile; group conversations; caregiver dashboard.
**Foundations:** automated tests, ownership checks on every route, HTTPS and a real hostname, one-command deployment, monitoring, backups.

## 19. Claims to avoid

- "Fully on-device / nothing leaves the device" — conversation text and face crops go to a cloud AI service.
- "Always correct" or any accuracy percentage — accuracy on real photos is unmeasured.
- "Medical device / diagnoses / treats" — it is an assistive memory tool, not medical software; summaries are automatically generated and can be wrong.
- "Works in any language" — English only.
- "Runs in the background on the phone" — not built yet.
- Any market size, customer, or traction figure without a source — none is in this repository.
