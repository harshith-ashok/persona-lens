# Implementation TODO (Claude Code handoff)

Companion checklist to the main tab. Assumes the resolved decisions there: Ollama Cloud vision is primary with local dlib as an automatic fallback on failure; audio-only sessions end after 15 seconds of silence; voice matching recognizes previously known speakers, not just host vs. unidentified; push transcription/summarization to the cloud wherever practical; no added privacy/consent gating.

## Phase 1 — Data model

- [x] Migration: new `sessions` table (`id`, `patient_id`, `person_id` nullable, `mode` \[`vision`|`audio`\], `status` \[`open`|`ended`|`resolved`\], `started_at`, `ended_at`)
- [x] Migration: new `host_voice_profile` table (`patient_id` PK/FK, `embedding`, `sample_audio_ref`, `created_at`)
- [x] Migration: add a `voice_embedding` column to `known_persons` (nullable, filled once a person is named/resolved)
- [x] Migration: `interaction_logs` — make `person_id` nullable, add `session_id`, add `mode`
- [x] Resolve the `face_embeddings` vector(512) vs. 128-d mismatch: repoint to the chosen Ollama Cloud embedding size, or drop the column if matching goes prompt-based

## Phase 2 — Voice enrollment & recognition (pyannote.audio)

- [x] New `backend/voice.py`: enroll function (audio → speaker embedding), diarize function (audio → time-stamped speaker segments)
- [x] `POST /voice/enroll`: one-time host enrollment endpoint, writes `host_voice_profile`
- [x] Setup-wizard step (frontend): "say a few sentences" recorder, calls `/voice/enroll`
- [x] Extend diarization: after labeling host segments, compare remaining segments against every `known_persons.voice_embedding` to identify returning speakers by voice
- [x] When a session ends and a person is newly named (Phase 4), store their voice embedding from that session's audio
- [x] Provision `pyannote.audio` model access (Hugging Face terms + auth token); add the token to Phase 0's env vars

## Phase 3 — Session engine & audio-only ingestion

- [x] New `backend/session.py`: session state machine (`open → ended → resolved`)
- [x] `POST /session/start {mode}`: creates a `sessions` row, returns `session_id`
- [x] `POST /session/{id}/end`: runs Whisper transcription, diarization, and the LLM summary; sets `status` accordingly
- [x] Silence detection: end an audio-only session automatically after 15 seconds of continuous silence
- [x] Generalize `speech.py` to run without a `person_id` supplied up front
- [ ] Deprecate/redirect `POST /process-interaction` to the new session flow (keep temporarily if anything else depends on it)

## Phase 4 — Unknown-conversation capture & naming

- [x] `POST /person/finalize {session_id, name, relationship, face_image?}`: creates the `known_persons` row, back-fills `person_id` onto the session's logs/summary, stores the voice embedding from that session
- [x] Frontend `NamePrompt` modal: fires once after `/session/{id}/end` returns with `person_id: null`; offers the captured face frame as the enrollment image on vision sessions
- [x] Handle "recognized by voice, no name on file yet" the same way as a fresh unknown (still prompt to name)

## Phase 5 — Vision: Ollama Cloud migration with fallback

- [x] Prototype both matching approaches from the design doc (embedding-based vs. prompt-based) against real known-person photos; pick one
- [x] Rewrite `face.py`'s `/recognize` and `/add-face` to call Ollama Cloud first
- [x] On any Ollama Cloud error/timeout, fall back automatically to the existing `face_recognition`/dlib code path (keep it, don't delete it)
- [x] Remove or repoint the in-memory embedding cache depending on where matching ends up happening

## Phase 6 — Push remaining stages to the cloud

- [x] Evaluate a hosted transcription API as a replacement or option alongside local Whisper `base`
- [x] Evaluate routing `llm.py`'s summary generation to a cloud-hosted model instead of local `qwen3:8b`
- [x] Keep `pyannote.audio` diarization local regardless (no cloud swap planned for this stage)
- [x] Add config flags so each stage's local-vs-cloud choice is switchable without a code change

## Phase 7 — Unified UI

- [x] Build `SessionPanel.vue`: single entry point offering "Vision" or "Audio-only" start
- [x] Build `SpeakerTranscript.vue`: renders host/other/named-person lines from diarization
- [x] Reuse one `NamePrompt.vue` modal (Phase 4) across both modes
- [x] Reconcile or retire `Dashboard-v.vue`
- [x] Move the hardcoded `http://localhost:8120` API base into config/env

## Phase 8 — Performance pass

- [x] Move diarization and (if kept local) summarization off the request/response cycle into a background task
- [x] Swap Whisper `base` for `faster-whisper`/`whisper.cpp` if staying local for transcription
- [x] Load-test a full session end-to-end (Whisper + diarization + vision + summary) and address the slowest stage first
