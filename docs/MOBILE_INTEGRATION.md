# PersonaLens Voice — build the Flutter app (voice-only)

**Audience:** the developer (and any coding agent) building a new Flutter app that is the **voice-only version of the PersonaLens web app**, talking to the FastAPI backend that runs on a different computer.

**Scope:** everything the web app does with voice — including the life timeline (§10.8), people relevance (§10.9) and optional conversation video (§10.10) — login, your profile (username, voice and face, §6), sessions with **live captions**, speaker labels (host / other / named person), summaries, naming people afterwards, people list, history — **plus identifying faces from a photo** the user picks or takes (§11), a **recall card** when someone is recognized (§10.5), **Ask your memory** (§10.6) and **Big & simple mode** (§10.7). **live camera recognition** (vision mode, §11.6).

**Reference implementation:** the web app in `frontend/` (paths are given so the logic can be copied). This guide is written so the app can be built without access to the backend machine, except for testing.

---

## 1. Where the voice recognition runs

**All of it runs on the backend host (FastAPI), none on the device.** The app is a thin client: it captures microphone audio, streams it, and displays what comes back.

| Capability | Where it runs | How the app uses it |
|---|---|---|
| Speech → text (Whisper) | Backend (local Whisper, English only) | Streams audio to `/ws/live`; final transcript after the session |
| Live captions | Backend (`/ws/live`, rolling Whisper) | WebSocket events (§7) |
| Speaker separation (host vs. other) | Backend (pyannote, GPU/CPU) | Arrives with the finished session |
| Voice recognition of people | Backend (speaker embeddings compared to stored voices) | Automatic; the session result names the person |
| Host profile: username, voice print and face | Backend (stored on the account, shared by web and app) | App enrolls and reads it (§6) |
| Summaries | Backend → cloud LLM | Part of the finished session |
| Face identification from a photo or live camera frames | Backend (dlib detection + cloud vision model, dlib fallback) | Upload an image, get names and boxes back (§11, §11.6) |
| Ask your memory | Backend (embeddings + cloud LLM) | Send a question, get an answer with sources (§10.6) |
| Accounts | Supabase (auth) | Username + password (§5) |

On the device only: recording the mic, an optional simple silence detector (§8), and the UI.

**Consequence: no architecture change is needed.** A Flutter client is feasible as-is. The only requirements are network reachability to the backend host (§2), and streaming audio in one specific raw format (§7).

Everything is **English only** (`TRANSCRIBE_LANGUAGE=en` on the backend); other languages come out as garbled English.

---

## 2. Development network setup (backend on one computer, Flutter on another)

Topology in this project: the Flutter machine hosts a **mobile hotspot**; the backend machine is connected to it.

```
Flutter machine (hotspot, gateway 192.168.137.1)
        │  Wi-Fi (192.168.137.x)
Backend machine (this repo)  ─ 192.168.137.43 (example; check with `ipconfig getifaddr en0`)
   ├─ Supabase gateway  :8000   (docker compose)   ← reachable from the LAN already
   └─ FastAPI backend   :8120   (uvicorn)          ← must be started for the LAN, see below
```

### 2.1 On the backend machine (one-time each session)

1. Start Supabase: `docker compose up -d` (repo root). Its ports listen on all interfaces.
2. **Start the backend on all interfaces.** The default (`127.0.0.1`) is invisible to other computers, which is the most likely cause of "connection refused" from the app:

   ```bash
   cd backend && source .venv/bin/activate
   uvicorn main:app --reload --host 0.0.0.0 --port 8120
   ```
3. Note the machine's LAN IP: `ipconfig getifaddr en0`. It changes when the hotspot reconnects, so the app must let the user change the server address (§4).
4. If macOS asks about incoming connections for Python/Docker, allow them (System Settings → Network → Firewall).
5. Optional: the backend loads its models at startup in the background; the first request can be slow for ~10 s after a restart.

### 2.2 From the Flutter machine — verify before writing any Dart

Replace `<host>` with the backend machine's IP.

```powershell
# Windows PowerShell
Test-NetConnection <host> -Port 8000
Test-NetConnection <host> -Port 8120
curl.exe http://<host>:8120/health          # -> {"status":200}
curl.exe http://<host>:8000/auth/v1/health  # -> JSON with "name":"GoTrue"
```

If 8000 works and 8120 does not, the backend was started without `--host 0.0.0.0`.

### 2.3 Where you run the app changes the address

| Flutter target | Backend address to use |
|---|---|
| Windows/macOS desktop app | `http://<host>:8120` |
| Physical Android/iOS phone on the same hotspot | `http://<host>:8120` |
| Android emulator on the Flutter machine | `http://<host>:8120` — **not** `10.0.2.2`; that points at the Flutter machine itself, not the backend machine |
| Flutter web (`flutter run -d chrome`) | `http://<host>:8120`. The backend allows any origin (CORS). The browser only gives microphone access on `localhost` or HTTPS, and `flutter run` serves on `localhost`, so this works in development |

- **Android cleartext HTTP:** add `android:usesCleartextTraffic="true"` to `<application>` in `android/app/src/main/AndroidManifest.xml`. Also add `<uses-permission android:name="android.permission.INTERNET"/>` and `RECORD_AUDIO`.
- **iOS:** `NSMicrophoneUsageDescription` in `Info.plist`; for plain HTTP add an App Transport Security exception for the host (`NSAllowsLocalNetworking` or a domain exception). Development only.
- **macOS desktop:** add `com.apple.security.network.client` and `com.apple.security.device.audio-input` to the entitlements files.
- **Windows desktop:** nothing extra; allow the microphone in Windows privacy settings.
- Plain `http://`/`ws://` are development-only. Do not ship the exceptions.

The Supabase address is the same host on port **8000**: `http://<host>:8000`. The **anon key** is the value of `ANON_KEY` in the repo-root `.env` on the backend machine. Copy only that key. **Never** put `SERVICE_ROLE_KEY` or `POSTGRES_PASSWORD` in the app.

**Do not upload images through Supabase Storage.** This local Supabase has no Storage service (a Storage upload fails with a `413`/`404` from the gateway). Send images straight to the backend as multipart requests (§11).

---

## 3. Project setup

```bash
flutter create --org com.personalens --platforms=android,ios,windows,macos,web personalens_voice
cd personalens_voice
flutter pub add supabase_flutter dio web_socket_channel record permission_handler \
  shared_preferences path_provider flutter_riverpod image_picker
```

(Use whatever state management the developer prefers; Riverpod is only a suggestion. Keep the code below as the behavior spec.)

Suggested structure:

```
lib/
  core/        config.dart (server address), api_client.dart, supabase_boot.dart
  auth/        login_page.dart, register_page.dart
  audio/       pcm_recorder.dart, wav.dart, silence_detector.dart
  live/        live_captions.dart
  session/     session_controller.dart, session_card.dart, name_prompt.dart
  enroll/      voice_enroll.dart
  menu/        drawer.dart (people, history, ask, voice ID, settings)
  photo/       identify_photo_page.dart
  vision/      camera_session_page.dart, frame_converter.dart, face_tags.dart (§11.6)
  gallery/     gallery_page.dart, photo_detail_page.dart (§11.5)
  ui/          theme.dart, widgets
```

---

## 4. Configuration: the server address must be editable

The IP changes between hotspot sessions, so do **not** hardcode it. Store two values in `shared_preferences` and expose them in a "Server" setting (on the login screen and in the drawer):

- `serverHost` — e.g. `192.168.137.43`
- `anonKey` — the Supabase anon key (or bake it in with `--dart-define=SUPABASE_ANON_KEY=...`; it is not secret)

Derived URLs:

```dart
String get apiBase   => 'http://$serverHost:8120';
String get apiWs     => 'ws://$serverHost:8120/ws/live';
String get supaBase  => 'http://$serverHost:8000';
```

Because `supabase_flutter` is initialized with a URL, (re)initialize it after the host is known/changed (initialize on the login page instead of in `main()` before the user can set the server, or restart the auth client on change). Add a "Test connection" button that calls `GET $apiBase/health` and shows the result — it saves a lot of debugging.

---

## 5. Authentication (username + password)

There is **no email login**. The app maps the username to a synthetic email and uses ordinary Supabase email/password. (Web reference: `frontend/src/lib/supabase.ts`, `Login.vue`, `Register.vue`.)

```dart
String usernameToEmail(String u) => '${u.trim().toLowerCase()}@persona-lens.local';

// Register (keeps the full name in user metadata)
await supabase.auth.signUp(
  email: usernameToEmail(username), password: password, data: {'full_name': fullName});

// Login
await supabase.auth.signInWithPassword(email: usernameToEmail(username), password: password);
```

- Username: 3–32 characters, letters, numbers, `_ . -` (`^[a-z0-9_.-]{3,32}$`, case-insensitive). Password ≥ 8 characters, plus a "confirm password" field on register.
- No "forgot password" (there is no inbox). Email confirmation is off, so sign-up logs the user in immediately.
- Every backend call sends `Authorization: Bearer <accessToken>`; read the token at call time from `supabase.auth.currentSession?.accessToken` (the library refreshes it). A `401` means sign the user out.
- The user id inside the token is the patient id. The app never sends a patient id.

Dio client that always attaches the current token:

```dart
final dio = Dio(BaseOptions(baseUrl: apiBase, connectTimeout: const Duration(seconds: 8)))
  ..interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
    final t = Supabase.instance.client.auth.currentSession?.accessToken;
    if (t != null) o.headers['Authorization'] = 'Bearer $t';
    h.next(o);
  }));
```

---

## 6. Your profile: username, voice and face

**The host (the person who owns the account) is a person too.** Their identity is the **login username**, and their **voice print** and **face** are tied to it. All of it is stored on the account, so the web app and this app see the same profile: enroll on one device and the other already knows you. Recognized by voice, the host is labeled with their username (not "Host"); recognized by face, they are shown as **"You"**.

`GET /host` (also creates the host person the first time, named after the username):

```json
{"username":"harshi","name":"harshi","person_id":"c8ad…",
 "voice_enrolled":true,"face_enrolled":true,"face_count":1,
 "photo_b64":"<small JPEG, base64>"}
```

- Load it at start-up and after every change. Show "Signed in as **username**", a status tick for voice and for face, and `photo_b64` as the profile picture (`Image.memory(base64Decode(...))`). This is the "same face on every device" — it comes from the account, not from the phone.
- **Voice — guided, like setting up a voice assistant.** The user reads a few sentences; the screen shows **what was understood, live**, and each sentence must be understood before moving on (this proves the voice is actually transcribable, and gives the voice print about 20–25 seconds of speech). `voice_enrolled` in the profile (or `GET /voice/status` → `{"enrolled": bool}`) says whether it is done. Web reference: `GuidedVoiceEnroll.vue`.

  1. **Get the sentences:** `GET /voice/prompts` → `{"sentences":[5 strings],"min_score":0.75,"min_seconds":1.0,"done":[0,2]}`. Always use the server's list (do not hardcode it); `done` lists sentence indexes already accepted, so an interrupted setup resumes at the next one.
  2. **Show one sentence at a time**: "Sentence 1 of 5", the sentence in large type, progress dots, a live waveform, and a "What I heard" line.
  3. **Live captions while they read:** open the live WebSocket exactly as in §7.4 but send `{"type":"start","token":"<accessToken>","purpose":"enroll"}` (**no `session_id`**). Stream the same 16 kHz mono PCM frames. You get `partial` / `final` events with the text. Nothing is stored and no session is created. Show the heard text (partials replace each other; join finals and the current partial) and **highlight the words of the sentence that have been heard** (compare lowercase words with punctuation removed). If the socket fails, carry on without live text; the check in step 5 still works.
  4. **Stop by itself:** when the heard text covers about 85 % of the sentence's words in order, wait ~0.8 s and stop recording (like a voice assistant); also offer a "Done speaking" button, and stop after ~25 s regardless. Send `{"type":"stop"}` and close the socket.
  5. **Check the recording:** `POST /voice/enroll/clip`, `multipart/form-data`: **`index`** (the sentence number, 0-based) and **`audio`** (the clip: WAV, or m4a/webm). Response:

     ```json
     {"index":0,"sentence":"The quick brown fox…","transcript":"The quick brown fox jumps over the lazy dog near the river.",
      "score":1.0,"ok":true,"seconds":3.8,"done":[0],"complete":false}
     ```

     `ok` is `true` when the clip is at least `min_seconds` long and `score` (how much of the sentence was heard, in order) is at least `min_score`. If `ok` is `false`, show `I heard "<transcript>". Please read the sentence exactly as shown.` (or "I didn't hear anything. Check your microphone and try again." when `transcript` is empty) and let them try again. An accepted clip is kept on the server until step 6.
  6. **Finish:** when `complete` is `true`, call `POST /voice/enroll/finish` → `{"enrolled": true, "clips": 5}` (`400` `Sentences still to read: [..]` if some are missing). The server joins the clips and builds the voice print from all of them, stores it on the host person, and clears the clips. Show "Voice saved".
  7. **Redo:** if already enrolled, show "Your voice is set up" with a "Record it again" button that starts from sentence 1; finishing replaces the old voice print.

  A quicker single-clip option still exists for tools and tests: `POST /voice/enroll` with one `audio` file (WAV, ≥ 5 s) → `{"enrolled": true}`. The app should use the guided flow above.
- **Face:** `POST /host/face`, `multipart/form-data`: field **`file`** (a JPEG/PNG photo; the largest face is used) and optional `replace` (`true` = a retake that replaces earlier photos; default `false` adds another photo, which improves recognition). Returns the profile above. `400` `No face found in the photo` → ask for a clearer photo. Take it with the front camera (`image_picker` with `preferredCameraDevice: CameraDevice.front`) or choose one from the gallery. `DELETE /host/face` removes the host's face photos. Web reference: `FaceEnroll.vue`.
- **Display name (optional):** `PUT /host` with form field `name` overrides the username as the shown name; the voice and face stay tied to the same person. Most apps won't need it.
- **First-run flow:** on first launch after login, if `voice_enrolled` or `face_enrolled` is false and the user has not skipped, show "Set up you": the username, then the voice step, then the face step (each skippable; remember the skip locally). The same screen is reachable later from the drawer's **You** tab. Web reference: `HostSetup.vue`.

**What the host being a person changes elsewhere**
- The host is **not** in `GET /people` and never appears as a visitor. A session is never attached to the host, and `POST /person/finalize` with the host's `person_id` returns `400` `That person is you`.
- Recognition results (`/recognize`, gallery faces) carry **`is_self: true`** when the face is the host's. Show such a face as **"You"** (with the username underneath), do not show a recall card for it, do not count it as the recognized visitor, and do not treat it as an unknown face needing a name (§11.6).
- Speaker lines: live `final` events and finished-session `segments` carry a **`name`**: the host's username for host lines, a known person's name for theirs, `null` for an unnamed visitor. Show `name ?? label` (`label` being "Host"/"Other"). Transcripts and summaries use the username too, and Ask answers say "you".

---

## 7. Sessions with live captions — the core flow

A session is one conversation. The recommended path (streaming, no upload) is:

```
POST /session/start ─► WS /ws/live (stream PCM, receive captions) ─► {"type":"stop"}
   ─► POST /session/{id}/end (no audio) ─► poll GET /session/{id} ─► result
```

### 7.1 Start

`POST /session/start`, form field `mode=audio` → the session row, use `id`. (`status` is `open`.)

### 7.2 Capture audio: raw PCM, 16 kHz, mono, 16-bit

The backend requires exactly this format on the WebSocket: **16 kHz, mono, signed 16-bit little-endian PCM, no header, no container.** With the `record` package:

```dart
final rec = AudioRecorder();
if (!await rec.hasPermission()) { /* show "Microphone access was blocked." */ }
final stream = await rec.startStream(const RecordConfig(
  encoder: AudioEncoder.pcm16bits, sampleRate: 16000, numChannels: 1));
```

`stream` yields `Uint8List` chunks of varying size. Re-chunk them into **~100 ms frames (3200 bytes)** before sending, and feed the same bytes to the silence detector (§8) and to a local file (§7.6). Stop with `await rec.stop()`.

### 7.3 WAV wrapper (for enrollment and the upload fallback)

```dart
Uint8List pcm16ToWav(Uint8List pcm, {int sampleRate = 16000}) {
  final b = BytesBuilder();
  void s(String x) => b.add(x.codeUnits);
  void u32(int v) => b.add((ByteData(4)..setUint32(0, v, Endian.little)).buffer.asUint8List());
  void u16(int v) => b.add((ByteData(2)..setUint16(0, v, Endian.little)).buffer.asUint8List());
  s('RIFF'); u32(36 + pcm.length); s('WAVE'); s('fmt '); u32(16);
  u16(1); u16(1); u32(sampleRate); u32(sampleRate * 2); u16(2); u16(16);
  s('data'); u32(pcm.length); b.add(pcm);
  return b.toBytes();
}
```

### 7.4 The live-captions WebSocket

`ws://<host>:8120/ws/live` (use `IOWebSocketChannel.connect` / `WebSocketChannel.connect`).

1. After the socket opens, send **one text message**: `{"type":"start","token":"<accessToken>","session_id":"<id>"}`. The token goes here, not in the URL.
2. Wait for `{"type":"ready"}` before sending audio. On `{"type":"error","message":...}` the server closes (bad token, or session not `open`).
3. Send the PCM frames as **binary** messages.
4. Server events (JSON text):
   - `{"type":"partial","text":"…"}` — utterance in progress. Each partial **replaces** the previous partial. First one arrives ~1.5–2 s after speech starts.
   - `{"type":"final","text":"…","speaker":"host|other|<name>","person_id":"<id>|null","name":"<display name>|null","start":s,"end":s}` — utterance finished (after ~0.8 s of quiet, or 8 s of continuous speech). Append to the caption list, clear the partial. `person_id` is set when the voice matched a known person, so you can show that person's recall card (§10.5).
   - `{"type":"error","message":"…"}`.
5. To finish: send `{"type":"stop"}`, keep listening (the server flushes the last utterance as a `final`), and wait for the socket to close (timeout ~4 s).

Captions are best-effort. If the socket fails, **keep recording**; the session still works via the upload fallback (§7.6). `speaker` on a live line is a best-effort voice match; the accurate host/other split comes with the finished session.

Caption display (web reference: `.captions` in `Dashboard.vue`, `useLiveCaptions.js`): show the **last 3 final lines plus the partial**. Older finals are dimmed; the partial is italic and full strength. Each line has a small dot: teal for `host`, amber for anything else (`other` or a person's name).

### 7.5 End, poll, result

1. Stop the recorder; send `{"type":"stop"}`; wait for the socket to close.
2. `POST /session/{id}/end` with **no `audio` field** (the server kept the streamed audio). It returns in ~30 ms: `{"session_id":"…","status":"processing"}`. Errors: `409` session not open, `404` not this user's, `400` no audio.
3. **Poll** `GET /session/{id}` about once per second while `status == "processing"` (stop after 5 minutes). A 17-second recording takes roughly 3 seconds. Show "Processing…".
4. Terminal states: `resolved` (someone was identified), `ended` (finished, nobody identified — can be named), `failed` (show `error`).

Result (`resolved` / `ended`):

```json
{
  "session_id": "…", "status": "resolved", "mode": "audio",
  "person_id": "…", "person_name": "Daniel",
  "needs_naming": false,
  "other_speaker_detected": true,
  "transcript": "Host: …\nDaniel: …",
  "segments": [{"start":0.0,"end":2.1,"speaker":"host","name":"harshi","person_id":null,"text":"…"}],
  "summary": "One or two sentences.",
  "durationSec": 31,
  "timings": {"transcribe":0.8,"diarize":0.9,"summary":1.4,"total":2.7}
}
```

- `segments[].speaker` is `"host"`, `"other"`, or a known person's **name**. `segments` and `other_speaker_detected` are `null` if speaker separation was unavailable → show the plain `transcript`.
- **Show the result card** (web reference: `SessionCard.vue`): title = `person_name` or "Unmatched speaker"; the `summary` (or "No summary was generated for this session."); a two-color bar showing the host's share of speech (host characters ÷ all characters from `segments`); a "Show/Hide transcript" toggle listing `segments` with a colored dot and speaker label; a "Name person" button when naming is needed; a Dismiss button.
- **When to ask for a name** (voice-only rule): `person_id == null && (other_speaker_detected ?? transcript.isNotEmpty)`. If only the host spoke (`other_speaker_detected == false`), do not prompt.

### 7.6 Upload fallback (when the WebSocket failed)

Also write every PCM frame to a temp file (`path_provider`). If the socket never became `ready` or dropped mid-session, end the session with an upload instead: `POST /session/{id}/end`, `multipart/form-data`, field **`audio`** = `pcm16ToWav(allPcm)` as `session.wav`. An upload always wins over streamed audio. Delete the temp file afterwards. (`m4a`/`webm`/`ogg` also work, but WAV needs no encoder.)

### 7.7 UI state machine and the exact strings

States: `idle → starting → recording → processing → idle`. Disable the record button in `starting` and `processing` (this prevents a double-tap from starting two sessions — a bug the web app already hit).

Status line (top-left):

| State | Text |
|---|---|
| idle | `Standby · voice only` |
| recording | `Rec 00:12 · Listening` |
| recording, ≥ 5 s of silence | `Rec 00:31 · Silence · ending in 9s` |
| processing | `Processing…` |

The indicator dot is grey when idle, blinking red while recording, teal while processing.

---

## 8. Silence detection (auto-end after 15 s)

Web reference: `frontend/src/composables/useSilenceDetector.js`. Voice sessions end **automatically after 15 seconds of continuous silence**.

From each PCM frame compute the RMS of samples normalized to −1…1 (`sample / 32768`). A frame with RMS **> 0.015** counts as sound and resets the silence clock. Every ~200 ms compute `silentFor = now − lastSound`. Show the countdown once `silentFor ≥ 5 s` and end the session at `silentFor ≥ 15 s`. (The clock starts when recording starts, so a session where nobody talks also ends after 15 s.) Tune 0.015 on a real microphone.

---

## 9. Naming people after the fact

`POST /person/finalize` (multipart form). Voice-only, no face fields:

- `session_id` (required) and either
  - `name` (+ optional `relationship`) → creates a new person, **or**
  - `person_id` → attaches the session to a person that already exists.
- Returns `{"person":{…},"session_id":"…","face_added":null}`. Errors: `409` (session is not an unnamed `ended` one), `404` (unknown person), `400` (missing name).

Naming also stores the other speaker's **voice** for that person (if they have none yet), so the next session with them resolves to their name automatically.

Two entry points, as on the web (`NamePrompt.vue`):
1. Right after a session when the rule in §7.5 says a name is needed (open ~0.5 s after the card appears).
2. Later, from **History**: a row with `personId == null && status == "ended"` shows a **Name this person** button.

The prompt: title "Who was that?", a switch **New person / Someone I know** (the second only if people exist), Name (required, "Enter a name first."), Relationship (Daughter, Son, Spouse, Grandchild, Sibling, Friend, Neighbor, Caregiver, Other), or a Person dropdown for existing people ("Choose who this was."). Buttons: Skip, Save. After saving: toast `Saved <name>`, refresh people and history.

---

## 10. People and history (the drawer)

Open from a "•••" button (top right). Tabs: **People**, **History**, **Ask** (§10.6), **Voice ID** (§6), **More** (settings: Big & simple mode, §10.7). Refresh both lists when the drawer opens and after every finished session or naming.

`GET /people` → `[{"id","name","relation","firstSummary","lastSummary","lastSeen","sessions"}]` (`relation` and summaries may be `null`). List sorted by `sessions` descending, avatar = initials, subtitle `Relationship · N sessions` (`Not specified` if null). Tapping a person shows their detail: name, relation, last seen, **First met** (`firstSummary`) and **Most recent** (`lastSummary`), with "No summary yet." when empty.

`GET /sessions` → the 50 latest sessions that are not `open`:
`[{"id","mode","status","date","durationSec","personId","personName","summary","hostPct"}]`. Row: name (`Unnamed` if none), short date, summary truncated to ~110 characters, and the host/other bar from `hostPct` (0–100, or `null` → hide the bar). Unnamed + `ended` rows get "Name this person" (§9).

## 10.5. Recall card — show who this is and what you last talked about

When someone is identified (a face match in §11, or a live caption `final` with a `person_id` in §7.4), show a card: **name**, **relationship**, **"Last seen 3 days ago"**, and **"Last time: …"** with `lastSummary`. All of it comes from `GET /people` (load it at start and refresh after sessions/namings; refresh again if a `person_id` is not in the list). Use `lastSeen` for the relative time ("just now", "5 minutes ago", "yesterday", "3 days ago", "2 weeks ago", then a date). With no `lastSummary` show "No conversation has been recorded with them yet."; with no `lastSeen` show "First time we've met".

Keep the card on screen for ~20 s after the person was last seen or heard, show at most two people, and clear it when a new session starts. Web reference: `frontend/src/components/RecallCard.vue`, `Dashboard.vue` (`recallPeople`), `frontend/src/lib/format.js` (`timeAgo`).

## 10.6. Ask your memory

Let the user ask questions about past conversations, by typing or by voice.

`POST /ask`, `multipart/form-data`, either field **`question`** (text) **or** field **`audio`** (a short recording, e.g. WAV/m4a; the server transcribes it — English only):

```json
{"question":"Who brought me flowers?",
 "answer":"Daniel brought you flowers on Friday 25 September 2026.",
 "sources":[{"session_id":"…","date":"2026-09-25T05:02:11+00:00","person_name":"Daniel","snippet":"…","similarity":0.65}]}
```

- Show `answer` prominently and `sources` (date · person · snippet) underneath. `sources` is empty when the answer is "I don't have a record of that." — show that plainly, it is a correct answer.
- Answers can take a few seconds (retrieval plus a cloud model): show "Thinking…" and allow up to ~90 s before timing out. Voice: while recording show "Listening…", then send the clip; the response echoes what was heard in `question`.
- `400` means neither a question nor audio was sent, or nothing could be heard.
- Example prompts to show when empty: "Who visited me recently?", "What did I plan to do today?", "Did anyone bring me something?".
- Conversations recorded before this feature existed can be indexed once with `POST /memory/reindex` (returns `{"sessions":n,"chunks":n}`); new sessions are indexed automatically.
- Add it as an **Ask** tab in the drawer (§10) and a shortcut button on the main screen. Web reference: `frontend/src/components/AskPanel.vue`.

## 10.7. Big & simple mode

A setting (kept on the device) for patients who find the normal screen too small or busy: high-contrast colors (white on black, amber for names), much larger captions (~26 sp), a large recall card (name ~34 sp, summary ~22 sp), and **one big record button** with the text "Tap to start" / "Tap to stop"; hide the mode switch, the menu and the icon buttons. To leave it, show a small "Hold to exit" button in a corner that needs a press of ~1.2 s, so it cannot be hit by accident. Turn it on from Settings ("More" tab). Web reference: `.hud.simple` in `frontend/src/assets/hud.css` and `Dashboard.vue`.

## 10.8. Life timeline — decisions, activities, events, money and to-dos

The backend picks out **decisions, activities, events/appointments, money and to-dos** from every conversation automatically (only what was actually said), and lets people add their own. Show them as a timeline, so a person can see their life in order and what is coming up. They are also searchable through Ask (§10.6).

Item shape (`kind` is `decision`, `activity`, `event`, `money` or `task`):

```json
{"id":"…","kind":"task","title":"Call the bank","detail":null,"occurs_on":"2026-09-28","date":"2026-09-28",
 "amount":null,"currency":null,"is_done":false,"source":"auto","person_id":null,"person_name":null,"session_id":"…"}
```

`occurs_on` is when it happened or is due (`null` if no day was mentioned); `date` is the day to sort and group by (`occurs_on`, else the day it was noted). `source` is `auto` or `manual`.

| Call | Purpose |
|---|---|
| `GET /timeline?kind=&days=90&open_only=false` | Newest first → `{"events":[…]}`. `kind` filters; `days` looks back (future items are always included) |
| `GET /timeline/upcoming` | Not-done items due from today on, plus undated open to-dos, soonest first |
| `POST /timeline` (form `kind`, `title`, optional `detail`, `occurs_on` `YYYY-MM-DD`, `amount`, `currency`, `person_id`) | Add an item by hand |
| `PATCH /timeline/{id}` (any of `title`, `detail`, `kind`, `occurs_on` (empty string clears it), `amount`, `currency`, `is_done`) | Edit or tick off |
| `DELETE /timeline/{id}` | Remove |
| `POST /timeline/reextract` | Look through older conversations recorded before the timeline existed → `{"sessions":n,"events":n}` (can take a while; use a long timeout) |

Screen (web reference: `TimelinePanel.vue`, `TimelineItem.vue`): filter chips (All, Decisions, Activities, Events, Money, To-do); a **Coming up** section from `/timeline/upcoming`, then everything else grouped by day ("Today", "Yesterday", "Saturday, Sep 26"); to-dos have a checkbox (`is_done`), money shows the amount and currency, each row can be deleted; an "Add an item" form; and, when empty, a "Look through older conversations" button. New automatic items appear a few seconds after a session finishes processing, so refresh when the session result arrives and when the tab opens. Items come from speech, so they can be wrong: keep edit and delete easy. Money items are things mentioned in conversation, not a bank record.

## 10.9. How close is this person — relevance

`GET /people` also returns `"relevance":{"label":"Very close|Regular|Occasional","score":23.0,"sessions_30d":8}` for each person. It combines who they are (a spouse, child or grandchild counts most, then caregiver, friend, neighbor) with how often and how recently they appear. Sort the People list by `relevance.score` (highest first) and show the `label` under the name.

## 10.10. Video of a conversation (optional)

For vision sessions the app can keep the camera video, on the backend machine, so it can be watched later. **Off by default** and controlled by a setting on the device ("Save video of conversations" in the More tab); say clearly that the video is stored on the user's own backend and can be deleted.

- **Record:** record the camera and microphone together for the session (`camera` recording, or the platform's video recorder, at a modest bitrate — about 0.8 Mbps is plenty) and send the finished file on `POST /session/{id}/end` as an extra multipart field **`video`** (WebM or MP4; `413` if larger than 300 MB). It is best-effort: if recording fails, end the session normally without it.
- **Know it exists:** `has_video` on `GET /session/{id}` and `hasVideo` on each `GET /sessions` row.
- **Watch:** `GET /session/{id}/video` (bearer token; supports range requests, so seeking works). Because it needs the auth header, use `video_player` with `httpHeaders: {'Authorization': 'Bearer $token'}` on the network source, or download the bytes first. `404` if there is no video or it is another user's.
- **Delete:** `DELETE /session/{id}/video` → `{"deleted": true}`; the History row's "Watch video" button then disappears.
- History rows with `hasVideo` show a **Watch video** button. Web reference: `Dashboard.vue` (`startVideo`, `watchVideo`).

---

## 11. Identify a face from a photo

The user picks an image (gallery) or takes one, and the app shows who is in it. This is a **still-image** flow: one upload, one final answer. It also works from the same login as everything else.

### 11.1 Identify

`POST /recognize?wait=true`, `multipart/form-data`, field **`file`** = the image (JPEG or PNG). **Always send `wait=true` for photos.** Without it the server answers instantly with a provisional guess (`identifying: true`) meant for live video, and a still image would never get the confirmed answer. With `wait=true` it waits for the vision model (about 1 s) and every face in the response is final.

Response: an array with one entry per face found (empty array = no face in the photo):

```json
[{"name":"Olive","person_id":"5ea7…","confidence":0.99,"source":"cloud",
  "location":[158,625,405,378],"track_id":1,"identifying":false,"is_self":false,
  "image_width":910,"image_height":1137}]
```

- `location` is `[top, right, bottom, left]` in **pixels of the image as displayed** (after the phone's rotation flag is applied — see below). `image_width` / `image_height` are that displayed size, so map a box onto whatever size you draw the image at with `x * drawnWidth / image_width` (and the same for y). Do not decode the file yourself to get the size.
- **`is_self: true`** = the face is the host's: label it "You" (§6), skip the recall card and the "save this person" prompt.
- **Unknown face:** `name == "Unknown"` and `person_id == null` (confidence 0). Offer to save this person (§11.2). Also treat `confidence < 0.6` as unknown, like the web app.
- `source` is `cloud`, `local` or `local-fallback` (informational).
- Several faces → several entries, each with its own box. Label each box with `name` and the confidence.

Errors: `400` `Invalid image` (not an image), `401` sign in again, `500` unexpected.

### 11.2 Save an unknown face as a person

`POST /person`, `multipart/form-data`: `name` (required), `relationship` (optional; same list as §9), and **`file`** (the photo). One call creates the person and enrolls their face:

- `200` → the person object (`id`, `name`, `relationship`, …, `face_added: true`).
- `400` `No face found in the photo` → nothing is created. Tell the user to pick a clearer photo.
- If the photo has several faces, the **largest** face is enrolled. Ask the user to crop or pick a photo of one person when this matters.

To add more photos of someone who already exists (more photos = better recognition): `POST /add-face`, fields `person_id` and `file`. `404` `Person not found` if that person isn't this user's; `400` `No face found`.

Next time the same person appears in a photo, `POST /recognize?wait=true` returns their name.

### 11.3 Image handling rules (avoids the usual problems)

- **Rotation:** phones store photos sideways with a rotation flag. The server applies the flag, so `location` is in the **upright** picture. Show the picture with Flutter's normal `Image.file` / `Image.memory` (which also applies the flag) and the boxes will line up. If you re-encode or resize the image yourself, keep it upright; do not strip the flag without rotating the pixels first.
- **Size:** you don't need to downscale. The server shrinks big photos for detection (an 11-megapixel photo takes ~1 s). But large uploads cost mobile data and time: resizing to about 1600 px on the long side and JPEG quality ~85 before upload is a sensible default. If you resize, use the returned `image_width`/`image_height` for the box math, not the original file's size.
- **Formats:** JPEG and PNG. HEIC (iPhone) has not been tested and the server's image decoder probably can't read it; convert to JPEG on the phone before uploading (`flutter_image_compress` does this).
- Only the people who belong to the signed-in user can be recognized. Each user's people are private.

### 11.4 Screen behavior

1. A "Choose photo" button (gallery) and a "Take photo" button (camera), using `image_picker`.
2. Show the photo with a "Identifying…" indicator; on the response draw one box per face with the label (`name` and confidence in amber for a match; dashed grey box and "Unmatched" for an unknown).
3. Tapping an unmatched box opens the "save this person" sheet (§11.2): name, relationship, and the photo is attached automatically.
4. Empty array → "No face found in this photo."
5. Show errors as toasts; never leave the spinner running.
6. When a face is matched, also show that person's recall card (§10.5).

Add `image_picker` (and permission entries for photos/camera: iOS `NSPhotoLibraryUsageDescription`, `NSCameraUsageDescription`; Android needs none for the picker) to the project.

### 11.5 Gallery — keep every uploaded photo, with its face embeddings

Use the gallery when the user wants photos **kept**, not just identified. `POST /gallery` does everything `POST /recognize?wait=true` does (same per-face identification, ~1 s) **and** stores the image on the backend machine together with each face's embedding and match. It is the recommended upload for a "Gallery" screen; keep `/recognize` for one-off "who is this?" checks that should not be saved.

Storage note: images are stored as files on the backend host (this local Supabase has no Storage service), while metadata and embeddings are in the database. The app never touches Supabase Storage.

| Call | Purpose |
|---|---|
| `POST /gallery` (multipart `file`, optional `caption`) | Store an image and identify its faces → image object |
| `GET /gallery?limit=30&offset=0` | Newest first → `{"images":[…],"total":n}` |
| `GET /gallery?person_id=<id>` | Only photos that person is in |
| `GET /gallery?unidentified=true` | Only photos with a face nobody matched (a "Who is this?" queue) |
| `GET /gallery/{id}` | One image object |
| `GET /gallery/{id}/thumb` | ~400 px JPEG thumbnail (use in grids) |
| `GET /gallery/{id}/image` | The original file |
| `DELETE /gallery/{id}` | Delete the image, its file and its stored faces → `{"deleted":"<id>"}` |
| `POST /gallery/faces/{face_id}/assign` (form `person_id`, **or** `name` + optional `relationship`; `enroll`, default `true`) | Say who a face is |
| `POST /gallery/reidentify` | Re-try every unidentified face with the people known now → `{"checked":n,"matched":n}` |
| `POST /gallery/search` (multipart `file`) | Find stored photos of the person in the uploaded photo (largest face) |

Image object (returned by upload, list and detail):

```json
{"id":"c520…","caption":"Oval office","created_at":"2026-09-25T…","width":910,"height":1137,"byte_size":280123,
 "image_url":"/gallery/c520…/image","thumb_url":"/gallery/c520…/thumb",
 "faces":[{"id":"8dc3…","person_id":"c9b7…","person_name":"Olive","is_self":false,"confidence":0.99,"source":"cloud",
           "location":[158,625,405,378]}]}
```

- `image_url` / `thumb_url` are **relative**: prefix the API base. The files need the bearer token, so load them with the header: `Image.network(base + thumbUrl, headers: {'Authorization': 'Bearer $token'})` (or `CachedNetworkImage` with `httpHeaders`). A request without a token gets `401`; another user's image gets `404`.
- `faces[].location` is `[top, right, bottom, left]` in pixels of the stored image (`width` × `height`, upright); scale it like §11.1. A face with `person_id == null` is unidentified. An image with no faces has `"faces": []` and is still stored.
- `source` is `cloud`, `local`, `local-fallback`, or `manual` (set by the user through `assign`).
- Errors: `400` `Invalid image`, `413` larger than 25 MB (`GALLERY_MAX_MB`), `404` not found / not yours, `401` sign in.

**Suggested flow.** A grid of thumbnails with an "Add photo" button (`image_picker`). Show unidentified faces as "Who is this?": tapping one opens the same name sheet as §9 (new person or "someone I know") and calls `assign`. After naming (or after adding people any other way) call `POST /gallery/reidentify` and refresh, so the same person is filled in on their other photos. A person's profile can link to `GET /gallery?person_id=…`. "Find photos of…" uses `POST /gallery/search`.

`assign` with `enroll: true` also adds that face to the person's **recognition photos**, so `/recognize` gets better at them everywhere (this is why naming a face in the gallery helps live recognition). Deleting a gallery image does **not** remove those recognition photos.

### 11.6 Live camera recognition (vision mode)

The same experience as the web app's viewfinder: the camera is on, a tag follows each face (first "verifying", then the confirmed name), a recall card appears, and the conversation is captioned and recorded. Build it after voice sessions (§7), photo identification (§11.1) and the recall card (§10.5) work, because it reuses all three. **Not verified on a device from this repo (there is no Flutter runtime here); the backend side is tested, the Dart below is a spec, so calibrate on a real phone (last step).**

**Packages and permissions.** Add `camera`. Android: `CAMERA` permission. iOS: `NSCameraUsageDescription`. Create the controller with `enableAudio: false`: the microphone is recorded with `record` (§7.2) so captions and the session audio work exactly as in voice mode.

**Session.** A vision session is a normal session (§7) started with `mode=vision`: `POST /session/start` (form `mode=vision`), stream audio to `/ws/live`, and on `POST /session/{id}/end` send two extra optional fields: `person_id` (the person recognized during the session, if any) and `face_image` (a JPEG still with the face, so someone can be named later with their photo; see below). Start the recognition loop only once the session is `recording`, and stop it before ending.

**Frame loop** (web reference: `frontend/src/composables/useFaceTags.js`):
1. `controller.startImageStream((CameraImage img) { ... })` delivers frames continuously. Keep only the newest and process one at a time: skip a frame if a request is still in flight or fewer than ~150 ms have passed since the last one.
2. Convert the frame to a **small upright-or-sensor-oriented JPEG, about 320 px on the long side, quality ~70**. Android delivers `yuv420`, iOS `bgra8888` (ask for it with `imageFormatGroup`). Downsample while converting (sample every Nth pixel) so it costs a few milliseconds, and do it off the UI thread (`compute`/an isolate). If conversion proves troublesome, a slower fallback is `takePicture()` on a timer (about 2–3 per second; on some devices it makes a shutter sound).
3. `POST /recognize` with the JPEG in field `file` and, when needed, the query parameters below. **Do not** send `wait=true` (that is for still photos); the live call answers immediately.
4. Repeat until the session ends. Ignore an individual failed request (log it); after ~5 consecutive failures show "Recognition unavailable" but keep recording. Stop the loop when the app goes to the background.

**Sending frames as they come off the sensor.** Phone frames are usually rotated, and the front camera needs mirroring. Instead of rotating pixels in Dart, tell the server:

| Query parameter | Meaning |
|---|---|
| `rotate` = `0`, `90`, `180`, `270` | Rotate the frame **clockwise** by this many degrees before detection (`400` for any other value) |
| `mirror` = `true` | Flip left-right after the rotation (use for the front camera, whose preview is shown mirrored) |

The response's `location`, `image_width` and `image_height` describe the frame **after** that transform, i.e. the picture as the user sees it. Getting `rotate` right matters: a sideways frame simply finds no face (`[]`). Starting values (verify on a device): back camera `rotate = (sensorOrientation − deviceRotation + 360) % 360`; front camera `rotate = (sensorOrientation + deviceRotation) % 360` with `mirror=true`, where `sensorOrientation` is `camera.sensorOrientation` and `deviceRotation` is 0/90/180/270 for portrait/landscape-left/upside-down/landscape-right. **Calibration:** point the phone at a face; if the response is `[]`, cycle `rotate` through 0/90/180/270 (a hidden debug toggle is handy) until a box comes back, and hard-code the right rule per platform.

**Response** (per face; same fields as §11.1, in live mode):

```json
[{"name":"Olive","person_id":"5ea7…","confidence":0.75,"source":"local",
  "location":[142,209,300,77],"track_id":3,"identifying":true,"is_self":false,
  "image_width":240,"image_height":320}]
```

- `identifying: true` = provisional local guess while the cloud model verifies. Show it as "verifying" (dashed box, "Olive · 75% · verifying" or "Identifying…" if unknown). A later frame of the same face (same `track_id`) returns `identifying: false` with the confirmed answer, usually within ~1–2 s.
- `track_id` is stable while a face stays in the frame: use it as the widget key and to smooth boxes (blend new and previous box, weight ≈ 0.5 on the newest).
- Treat a face as unknown if `person_id == null` or `confidence < 0.6`. A face with `is_self: true` is **you**: show "You", no recall card, and never count it as `sawUnknownFace` or as the visitor's `person_id`.

**Drawing the tags** (web reference: `styleFor` in `useFaceTags.js`). Map the returned box onto `CameraPreview` the same way the web maps onto its `object-fit: cover` video: with the preview area `W × H` and the returned frame `iw × ih` (`image_width` × `image_height`): `scale = max(W/iw, H/ih)`, `dw = iw*scale`, `dh = ih*scale`, `ox = (W-dw)/2`, `oy = (H-dh)/2`, then `screenX = x*scale + ox`, `screenY = y*scale + oy` (for `left`/`right` use x, for `top`/`bottom` use y). Do **not** mirror again: with `mirror=true` the boxes already match the mirrored preview. Behavior: tags glide between updates (an implicit animation of ~180 ms); keep a tag for ~700 ms when a frame finds no face; flip the label to the left of the box when the box is within ~200 px of the right edge; unknown = grey dashed box with "Unmatched" (or "Identifying…" while `identifying`); match = amber box with name and confidence.

**Recall card.** As in §10.5, show the card for each confirmed person (`person_id` from a non-unknown face, and from live caption `final` events). Also remember the most recently matched `person_id` for `/end`.

**Naming after a vision session.** Keep two things while the session runs: `recognizedPersonId` (last confirmed match) and `sawUnknownFace` (an unknown face was in frame after its verification finished, i.e. `identifying == false`). When ending: send `person_id` if you have one, and send `face_image`: keep the latest frame that contained a face as a JPEG of about 640 px (the server stores it with the session). The result then follows the rule:

`needsName = person_id == null && ((other_speaker_detected ?? transcript.isNotEmpty) || (mode == vision && sawUnknownFace))`

so a silent visit by an unknown face can still be named. The name prompt (§9) shows the stored face and offers "use this photo to recognize them"; send `use_session_face=true` to `/person/finalize` when it is ticked (or send a fresh `face_image`). Naming later from History works the same, using `GET /session/{id}?include_face=true` for the photo.

**Screen.** Add a **Voice / Vision** switch to the main screen (locked while a session is running). Vision shows the camera preview full-screen with corner brackets, the tags, the recall card, the captions above the dock and the same record button; the status line reads `Rec 00:12 · Scanning` until someone is matched, then `Rec 00:12 · <First name> matched`. Voice mode is unchanged.

**Cost and battery.** Camera plus the network loop is the heaviest thing the app does: use a low or medium `ResolutionPreset`, ≤ 6 requests per second, one in flight, and shut the camera and the loop down as soon as the session ends or the app is backgrounded.

**Testing (real device).** (1) Calibrate `rotate`/`mirror` for both cameras in portrait and landscape until the box sits on the face. (2) A known person shows "verifying" then their confirmed name. (3) Two faces get two tags that do not swap. (4) An unknown face shows "Unmatched"; after the session it can be named, then recognized next time. (5) Turning the phone does not misplace the boxes. (6) Ending the session releases the camera.

---

## 12. Look and feel

Match the web app's dark "viewfinder" design (reference: `ref.html` in the repo root and `frontend/src/assets/hud.css`). Voice-only means no camera, so the main screen is the idle plate with a waveform:

Color tokens: background `#050708`, panel `rgba(10,14,15,0.82)`, strong panel `rgba(8,11,12,0.94)`, line `rgba(126,240,214,0.22)`, strong line `rgba(126,240,214,0.5)`, ink `#EAF6F2`, dim ink `#8FA39D`, glow (host / accent) `#3DFBD1`, amber (other / person) `#FFB238`, record red `#FF4757`. Fonts: **Space Grotesk** (UI) and **JetBrains Mono** (labels, captions) via `google_fonts`.

Layout: full-screen dark background with corner brackets; status readout top-left; mic, ask and menu icon buttons top-right (the mic button opens Voice ID setup and is amber once enrolled); an idle ring in the middle that becomes a live **waveform** (from the PCM levels) while recording; the recall card under the readout; captions stacked above the bottom dock; a large round **record button** in the dock (red dot → red rounded square while recording, with a pulse). The result card is a bottom sheet; the name prompt and enrollment are centered dialogs; toasts appear near the bottom.

---

## 13. Errors and edge cases

| Situation | Behavior |
|---|---|
| Can't reach the server | Message that includes the address being used and a link to "Server" settings; do not crash |
| `401` | Sign out, go to login |
| Microphone denied | Toast `Mic blocked`; stay idle |
| `/session/start` fails | Toast with `detail`; stay idle, release the mic |
| Socket fails or drops | Keep recording; no captions; finish via upload (§7.6) |
| `/end` returns `409` | The session already ended; just poll it |
| Session `failed` | Toast the `error`; recording is not retried |
| Polling > 5 minutes | Toast `Processing timed out` |
| App backgrounded while recording | Not supported in this version (see §15) |

---

## 14. Verification

Smoke test from the Flutter machine, then in the app. Replace `<host>` and `<ANON_KEY>`.

```powershell
# sign in (creates nothing); use a username registered through the app
curl.exe -s -X POST "http://<host>:8000/auth/v1/token?grant_type=password" `
  -H "apikey: <ANON_KEY>" -H "Content-Type: application/json" `
  -d '{\"email\":\"<username>@persona-lens.local\",\"password\":\"<password>\"}'
# take access_token from the JSON, then:
curl.exe -H "Authorization: Bearer <token>" http://<host>:8120/voice/status
```

Acceptance checklist (test on the real target, not only a simulator):
- [ ] Server setting saved; "Test connection" reports OK.
- [ ] Register and log in with a username; still logged in after restarting the app.
- [ ] Your profile: the first-run "Set up you" shows the username. Guided voice: each sentence shows live text while read, its matched words light up, a wrong sentence or silence is rejected with what was heard, five accepted sentences finish with "Voice saved", and quitting midway resumes at the next sentence; a face photo saves ("No face found" for a bad one); enrolling on the web is visible in the app (photo, ticks) and the other way round.
- [ ] Your own face and voice: shown as "You"/your username, with no recall card and no name prompt, on the app and on the web.
- [ ] Session: press record → speak → captions appear within ~2 s → stop → "Processing…" → result card with summary and host/other bar.
- [ ] Silence: stop talking → countdown appears at 5 s → session ends at 15 s by itself.
- [ ] Two people (or one person and a recording of another voice): the other voice shows as `Other`, then is offered for naming; after naming, a new session with that voice resolves to their name with no prompt.
- [ ] Naming later from History works for both "New person" and "Someone I know".
- [ ] Recall card: when a known person is recognized (face or voice) it shows name, relationship, last seen and the last summary.
- [ ] Timeline: decisions, plans, money and to-dos from a conversation appear a few seconds after it finishes, dates are right ("Monday" is the coming Monday), a to-do can be ticked off, an item can be added, edited and deleted, and "Coming up" lists what is due next.
- [ ] People are ordered by relevance and show a label such as "Very close".
- [ ] Video (only if implemented): with the setting on, a vision session's video appears in History as "Watch video", plays and seeks, and can be deleted.
- [ ] Ask: a typed and a spoken question both return an answer; an unrelated question returns "I don't have a record of that."
- [ ] Big & simple mode turns on from Settings, survives an app restart, and exits only with a press-and-hold.
- [ ] Photo: pick an image with a known person → box and name appear (~1–2 s). An unknown face shows "Unmatched"; saving it as a person, then picking another photo of them, names them.
- [ ] Photo taken in portrait on a phone (rotation flag) → the box sits on the face, not sideways.
- [ ] A photo with no face → "No face found in this photo."; a non-image → clear error.
- [ ] Vision mode: boxes sit on faces on both cameras in portrait and landscape; a known person goes verifying → confirmed; an unknown face can be named after the session (with its photo) and is recognized next time; the camera is released when the session ends.
- [ ] Gallery: upload a photo → it appears in the grid with the right names; it is still there after restarting the app and the backend; thumbnails load with the auth header.
- [ ] Gallery: an unidentified face → name it → "reidentify" fills the same person in on their other photos; filtering by that person lists them.
- [ ] Gallery: deleting a photo removes it from the list; one user cannot open another user's image.
- [ ] Turn WiFi off mid-session: the app does not crash, shows a clear error, and the recording is not silently lost.
- [ ] Start with the backend down: clear error that shows the server address.

---

## 15. Not in this version (ask the developer)

- **Background / screen-off standby listening.** Continuous background microphone use needs an Android foreground service and the iOS background-audio mode, and drains the battery. Build the foreground app first; standby is a follow-up.
- HTTPS/WSS, real domain names, production hosting, push notifications.

## 16. If something does not match this guide

The backend is the source of truth: routes are in `backend/main.py`, the session logic in `backend/session.py`, the live-caption protocol in `backend/live.py`, memory search in `backend/memory.py`. The web client in `frontend/src/` shows every call being made. Prefer reading those over guessing.
