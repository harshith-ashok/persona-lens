# New things — making PersonaLens a really good product

A prioritized list of what to add to the **web app** and the **Flutter app**, based on what the product does today and where it falls short for its actual user: a person with memory loss, and the family or caregiver who supports them.

Each item says **what**, **why it matters**, **what it builds on** (so it is not a rewrite), and a rough **effort** (S = a day or less, M = a few days, L = a week or more).

---

## The north star

The hardest moment for the patient is not *after* a conversation. It is the moment someone walks up: **"Who is this, and what did we last talk about?"**

Today PersonaLens records and summarizes well, but it mostly shows that information in a drawer after the fact. A really good product puts the right sentence in front of the patient at the right moment, makes it very hard to be wrong, and gives the caregiver a way to help. The list below is ordered around that.

## The top five — do these first

| # | Item | Where | Effort |
|---|---|---|---|
| 1 | Recall card the moment someone is recognized | web + app | S–M |
| 2 | "Not sure" handling and a correct-me button (safety) | web + app | M |
| 3 | Manage people: edit, delete, merge, add more photos | web + app | M |
| 4 | Follow-ups: promises and plans pulled out of conversations | web + app | M |
| 5 | Caregiver accounts linked to a patient | backend + both | L |

---

## A. For the patient in the moment

### 1. Recall card at recognition  ·  S–M  ·  ✅ built on the web
**What:** when a face or voice is identified, show a card: name, relationship, *last seen 3 days ago*, and the "last time" summary in one or two sentences. In the web viewfinder it sits under the AR tag; in the app it appears under the identified face in a photo, and as a live banner in a voice session once someone is recognized by voice.
**Why:** this is the product's whole promise, and today the summary is buried in the People drawer.
**Builds on:** `GET /people` already returns `lastSummary`, `lastSeen` and `relation`; the recognition response already carries `person_id`. Mostly front-end work.
**Status (web):** done. A card (name, relationship, "Last seen 2 hours ago", "Last time: …") appears when someone is recognized by face **or by voice** (live caption lines now carry `person_id`), stays 20 seconds after they were last seen or heard, and shows at most two people. Still to do: the Flutter app (see `docs/MOBILE_INTEGRATION.md` §10.5).

### 2. Speak it out loud  ·  S
**What:** an optional "Whisper" setting that reads the recall card aloud ("This is Meera, your daughter. Last time you talked about the weekend visit") through the device speaker or earbuds. Off by default, with a volume control and a "don't repeat within 10 minutes" rule.
**Why:** many patients can't read a screen quickly, or don't hold the phone up.
**Builds on:** nothing new server-side. Web: the Web Speech API. Flutter: `flutter_tts`.

### 3. Big-and-simple mode  ·  S  ·  ✅ built on the web
**What:** an accessibility mode: much larger text, high contrast, only one large button on screen, and no menus. Live captions of the other person in large type also help patients who are hard of hearing.
**Why:** the current HUD is designed for a technical user. The real user may be 80.
**Builds on:** the design tokens in `hud.css` (web) and the theme file (app).
**Status (web):** done. Menu → More → "Big & simple mode" (remembered on that device): high-contrast colors, much larger captions and recall card, one big record button with "Tap to start / Tap to stop", no menus or mode switch. To leave it, hold the small "Hold to exit" button for a bit over a second (so it can't be hit by accident). Still to do: the Flutter app.

### 4. Ask your memory  ·  M–L  ·  ✅ built (backend + web)
**What:** a box (or a voice question in the app): "When did Priya mention the flowers?", "What did the doctor say on Tuesday?", "Who visited this week?". The answer cites the session it came from.
**Why:** turns a log into an actual memory aid. This is the feature people will remember the product for.
**Builds on:** `interaction_logs` and `interaction_summaries` already hold the text; **pgvector is already installed**; `nomic-embed-text` is already available in your Ollama. Embed each summary when a session finishes, search by similarity, then have `gpt-oss:120b-cloud` answer from the top results.
**Status:** done. Every finished session is indexed (its summary plus the transcript in small windows) into `memory_chunks`; `POST /ask` takes a typed or spoken question, retrieves the closest chunks plus the last 10 sessions (so "who visited this week?" works), and answers only from those records, saying "I don't have a record of that." otherwise, with source snippets. Sessions recorded before this feature can be indexed with `POST /memory/reindex`. The web app has an Ask tab (and a quick button) with typed and voice questions. Answers are scoped to the signed-in user. Still to do: the Flutter app.

---

## B. Getting it right (safety)

### 5. "Not sure" handling and a correct-me button  ·  M
**What:**
- Below a confidence line, never assert a name. Show "Might be Meera" (or nothing) instead.
- A **"That's not Meera"** button on any recognition. It records the mistake, removes that match, and optionally asks "Who is it?".
- Enrollment guidance: ask for 3 or more photos in different lighting or angles, reject blurry or dark ones, and show how many photos each person has.
**Why:** for a person with memory loss, a confident wrong name is worse than no name. Trust is the product.
**Builds on:** the recognition response already has `confidence` and `source`; `/add-face` already stores multiple photos per person. Needs a small feedback table and a quality check on upload.

### 6. Verify the vision model with real photos  ·  S
**What:** the cloud matching was only tried on a handful of well-known faces, which the model may recognize from training rather than compare. Build a small test set of real (non-famous) family photos and measure right, wrong and "not sure" rates. Tune the number of reference photos and the confidence line from it.
**Why:** everything in section B rests on this number, and nobody has measured it yet.

---

## C. For the family or caregiver

### 7. Caregiver accounts linked to a patient  ·  L
**What:** a separate login for a family member or caregiver, linked to a patient. They can add people with photos, add notes, review history and summaries, and get alerts. The patient's own device stays simple.
**Why:** the person who needs the product is usually not the person who sets it up. Today one login is one patient (the user id *is* the patient id), so setup and use are the same person.
**Builds on:** Supabase auth. Needs a `caregivers` link table and the backend's patient scoping changed from "the token's user" to "a patient this user may access". This touches every endpoint, so plan it carefully and do it early, before more data depends on the current 1:1 model.

### 8. Notes that appear at the right moment  ·  S–M
**What:** the caregiver writes a note on a person ("Anita is the nurse; checks blood pressure at 5"), a reminder, or a medical note. It shows up on that person's recall card.
**Why:** turns the caregiver's knowledge into something the patient actually sees.
**Builds on:** **the `person_notes` table already exists** (with `note_type` and `valid_from`/`valid_until`) and is unused. Also unused: `ai_context_prompt` and `photo_url` on `known_persons`, which are natural homes for a profile photo and extra context for the summary prompt.

### 9. Follow-ups pulled out of conversations  ·  M
**What:** after each session, extract plans and promises ("Meera is bringing the grandchildren Saturday", "take the evening tablets", "call the bank Monday") as a checklist with dates. The patient sees "Coming up"; the caregiver sees what was promised.
**Why:** conversations contain commitments that are exactly what gets forgotten.
**Builds on:** the summary step already calls the LLM; extend the prompt to return structured JSON (summary plus action items) and add a small `follow_ups` table.

### 10. Daily digest and timeline  ·  M
**What:** an end-of-day card ("Today you talked with Meera and Priya; you planned…") and a timeline view of the week. Optionally sent to the caregiver.
**Why:** gives the patient an evening review and the caregiver peace of mind without reading every transcript.
**Builds on:** stored summaries; one extra LLM call per day.

### 11. Notifications  ·  M
**What:** push (app) and browser notifications for: a session finished processing, a follow-up is due, a person hasn't been seen for a long time.
**Builds on:** Firebase Cloud Messaging for the app and the Notifications API on the web. The backend needs a small scheduler.

---

## D. Data care (things that are missing today)

### 12. Manage people and sessions  ·  M
**What:** edit a person's name or relationship, set a profile photo, see and remove enrolled face photos, delete a person, **merge duplicates** (two entries for "Meera"), delete or edit a session or its summary, and rename a speaker.
**Why:** right now there are **no edit or delete endpoints at all**. One typo in a name is permanent, and duplicates are inevitable because unknown people get named one session at a time.
**Builds on:** `known_persons`, `face_embeddings`, `sessions` tables; needs `PATCH`/`DELETE` routes and a "People" management screen in both apps.

### 13. Group conversations  ·  M–L
**What:** conversations with several people (a family gathering). Recognize and label each voice, and let the user name each unknown speaker.
**Why:** today the system keeps one "other" voice per session, so with two visitors it merges them.
**Builds on:** the diarization already separates speakers; extend `label_speakers` to keep an embedding per unknown speaker and let `finalize` take a speaker choice.

### 14. Your data, your control  ·  S–M
**What:** opt-in controls, not gates: export all data, delete all data, delete one person's data, and a retention setting (for example "delete transcripts after 90 days"). A visible "recording" indicator and a one-tap pause.
**Why:** basic hygiene for a product that stores conversations and faces. It fits your earlier decision not to add consent gating, because none of this blocks use.
**Builds on:** raw audio is already deleted after processing, which is worth saying in the UI.

---

## E. App-specific

### 15. Batch-import people from the gallery  ·  S–M
**What:** a setup flow: pick photos from the phone's gallery, the app finds faces, and the user names each one (and sets a relationship) in a quick swipe-through.
**Why:** the fastest way to onboard 10 family members, using the photo-identification feature the app already has.
**Builds on:** `POST /person` (name plus photo in one call) and `POST /recognize?wait=true`.

### 16. Work when the network doesn't  ·  M
**What:** if the server is unreachable, keep recording, queue the audio and photos on the phone, and upload later with a clear "waiting to sync" state. Cache the People list so recall cards still appear offline.
**Why:** the app depends on reaching the backend, and hotspot and wifi drops are normal.
**Builds on:** the upload fallback for sessions is already part of the design.

### 17. Standby listening  ·  L
**What:** already planned: the phone listens for speech, starts a session, and ends it after silence. It needs a foreground service on Android and background audio on iOS.
**Why it is here:** it is the difference between a tool you open and an assistant that is simply there. Build it after captions and the recall card feel solid.

### 18. Home-screen widget and quick actions  ·  S–M
**What:** a widget or long-press action: "Who was I with today?", "Start a session". A lock-screen glance of today's follow-ups.

---

## F. Web-specific

### 19. Caregiver dashboard  ·  M
**What:** a bigger-screen view: people table, session history with search and filters, follow-ups, notes, a week timeline, and photo and voice management. (The current web app is one viewfinder plus a drawer, which is right for the patient and too small for the caregiver.)

### 20. Guided first-run setup  ·  S
**What:** a short wizard: create account → record host voice → add first three people with photos → try a test session. Show progress and a "you're ready" state.
**Why:** first-run today drops the user on a camera view with an enrollment popup.

### 21. Live conversation view on a second screen  ·  M
**What:** a read-only page showing the running live captions and speaker labels, so a caregiver can follow along, or a large screen can show captions for a hard-of-hearing patient.
**Builds on:** the live-caption stream; needs a way for a second client to subscribe to a session.

---

## G. Foundations — boring things that decide whether this survives real use

| Item | Why | Effort |
|---|---|---|
| **Automated tests** (none exist today): API tests for sessions and recognition, plus one end-to-end browser test | Every change so far was checked by hand | M |
| **Ownership checks on every route.** `/summary/{id}` and `/relation/{id}` still trust the id they're given | Any signed-in user could read another user's summary | S |
| **Route guard on the web app** (a logged-out user can open `/dashboard` and only gets redirected after the page loads) | Small correctness and security fix | S |
| **Embedding cache and face tracks live in one process's memory** | Breaks with more than one server worker | M |
| **HTTPS/WSS, real hostname, tightened CORS** (currently `*`) | Needed before anyone outside your network uses it; browsers also require HTTPS for the microphone off `localhost` | M |
| **One-command run** for backend, Supabase and web (a single compose file or script, backend on `0.0.0.0`) | Cuts setup time and the "can't reach the backend" class of problems | S |
| **Basic monitoring** from the per-stage timings already stored on each session (slowest stage, failure rate, cloud fallback rate) | Shows what to optimize | S–M |
| **Rate limits and payload size limits** on upload routes | Protects the models from a runaway client | S |
| **Backups** for the database volume | It holds people's memories | S |

---

## Suggested order

1. **Safety and value first (about 2 weeks):** #6 measure recognition, then #5 "not sure" and correct-me, #1 recall card, #12 manage people.
2. **Make it usable by a family (about 2–3 weeks):** #20 first-run wizard, #15 batch import, #8 notes, #9 follow-ups, then **start #7 caregiver accounts** before more data piles up on the 1:1 model.
3. **Make it feel like magic:** #2 speak-it-out-loud, #4 ask your memory, #3 big-and-simple mode, #10 daily digest.
4. **Reach:** #16 offline, #11 notifications, #17 standby listening, #19 caregiver dashboard, #13 group conversations.
5. **Run the foundations (section G) alongside all of it,** starting with tests and the ownership checks.

## Things to be careful about

- **Wrong-name risk** is the biggest product risk. Prefer silence over a confident mistake (#5, #6).
- **Cloud vision and summary models receive faces and conversation text.** Say so plainly in the app, and offer the local-only setting (`VISION_BACKEND=local`) for people who want nothing to leave the machine.
- **Everything is English-only** by decision. Multilingual families are a real gap if the product grows.
- **Standby listening** raises the privacy bar (always-on microphone). Make it an explicit, visible, easy-to-stop choice.
- **This is an assistive tool, not medical software.** Keep summaries and follow-ups clearly labelled as automatically generated, with an easy way to correct them (#12).
