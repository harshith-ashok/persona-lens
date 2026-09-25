# PersonaLens — full feature list

PersonaLens is an external memory for people with memory loss. It recognizes who is in front of you, reminds you who they are and what you last talked about, captions and remembers your conversations, and lets you ask questions about them.

There are two apps on one account: the **web app** and the **Flutter app**. They share the same backend, so anything saved in one (your voice, your face, the people you know, conversations, photos) is available in the other.

**Status key:** ✅ built and working · 🔜 planned

---

## Web app

### Account and setup
- ✅ Log in and register with a **username and password** (no email needed)
- ✅ Signed-out visitors are sent to the login page
- ✅ **You are a person too:** your username is your identity, and your **voice** and **face** are tied to it and saved on the account
- ✅ First-run **"Set up you"** screen: shows your username, then walks you through your voice and your face; each step can be skipped and redone any time from the menu (You tab)
- ✅ **Guided voice setup, like a voice assistant:**
  - Read five short sentences aloud, one at a time
  - **Live text shows what was understood** while you speak, and the sentence's words light up as they are heard
  - A sentence is accepted only once it is understood; a wrong sentence, silence, or a clip that is too short is rejected and shows what was heard
  - It stops by itself when the sentence has been heard, or you can press "Done speaking"
  - Your voice print is built from all five sentences, and setup resumes where you stopped if you quit midway
  - Redo it any time
- ✅ **Face setup:** take your photo with the camera or choose one; retake any time; your photo is shown in the setup screen

### The main screen (viewfinder)
- ✅ Full-screen dark camera view with a live status line (Standby, Rec 00:12 · Scanning, Processing…)
- ✅ Two modes: **Vision** (camera and microphone) and **Voice only** (microphone with a live waveform)
- ✅ One large record button; a "starting" state prevents accidental double sessions
- ✅ Toast messages for saves and errors

### Face recognition (camera)
- ✅ **AR face tags:** a box and label follow each face in the camera view
  - Shows "Identifying…" or "verifying" straight away, then the confirmed name and match percentage
  - Boxes glide smoothly, survive a missed frame, stay correct when the window is resized, and stay aligned on a mirrored, cropped video
  - Several faces get separate tags, and the label flips to the left near the right edge
- ✅ **Your own face is shown as "You"**, never as a visitor: no recall card and no "Who was that?"
- ✅ Recognition keeps working if the cloud model is unavailable (it falls back to the local matcher automatically)

### Recall card
- ✅ When someone is recognized by **face or by voice**, a card shows their **name, relationship, "Last seen 3 days ago"** and **"Last time: …"** (the summary of your last conversation with them)
- ✅ Stays on screen about 20 seconds after they were last seen or heard, shows up to two people, and says "First time we've met" for someone new

### Conversations
- ✅ **Live captions**, about 1.5–2 seconds behind speech
  - Shows the last three finished lines plus the line in progress
  - Each line is colored by speaker: you (shown by your username), the visitor, or a known person by name
- ✅ **Automatic end after 15 seconds of silence** in voice mode, with a countdown from 5 seconds
- ✅ Recordings are processed in the background, so the screen stays responsive ("Processing…", about 3 seconds for a short conversation)
- ✅ **Who said what:** the system separates your voice from the visitor's
- ✅ **Recognition by voice:** anyone named before is recognized by their voice alone
- ✅ **Short summary** of every conversation (one or two sentences)
- ✅ **Result card:** summary, a bar showing how much each side spoke, and a show/hide full transcript
- ✅ English-only transcription, captions and summaries

### Naming people
- ✅ **Name the person** when someone new spoke or was seen: name and relationship, with the captured face photo offered as their recognition photo
- ✅ Choose **New person** or **Someone I know** to attach a conversation to an existing person
- ✅ **Name later from History:** unnamed conversations have a "Name this person" button and show the saved photo
- ✅ Naming saves the person's **voice** and (optionally) **face**, so they are recognized automatically next time

### Video of conversations (optional)
- ✅ **Save video of conversations:** off by default; when on, the camera video of a vision session is kept on your own backend machine
- ✅ Watch it later from History with a normal player (play, pause, seek); **delete any video** in one tap

### Menu drawer
- ✅ **People:** everyone you know, closest first, with relationship, a **closeness label** (Very close, Regular, Occasional), number of conversations, and their first-met and most-recent summaries
- ✅ **Timeline:** your life timeline (below)
- ✅ **History:** every conversation with date, summary and a speech-share bar; conversations with saved video have a **Watch video** button
- ✅ **Ask:** ask your memory (below)
- ✅ **You:** your username, voice and face setup
- ✅ **More:** settings (Big & simple mode, Save video of conversations)

### Life timeline
- ✅ **Decisions, activities, events, money and to-dos are picked out of your conversations automatically** — only what was actually said, with days like "Monday" or "yesterday" turned into real dates
- ✅ A **timeline** of your life in order: "Coming up" first, then Today, Yesterday and earlier days
- ✅ Filter by **Decisions, Activities, Events, Money or To-do**
- ✅ **To-dos and responsibilities** can be ticked off; money shows the amount and currency
- ✅ **Add your own items**, edit or delete any item; look back through older conversations to fill in the timeline
- ✅ Everything on the timeline is also searchable with Ask

### Ask your memory
- ✅ Ask in plain language, by **typing or speaking:** "Who brought me flowers?", "What did I plan to do today?", "Who visited me recently?"
- ✅ Answers come only from your recorded conversations, say who and when, and show the source snippets
- ✅ Says "I don't have a record of that." instead of guessing
- ✅ Example questions when empty; a quick-access button on the main screen

### Accessibility
- ✅ **Big & simple mode:** white-on-black high contrast, very large captions and recall card, one large button ("Tap to start" / "Tap to stop"), no menus
- ✅ Turned on from the menu (More) and remembered on that device
- ✅ Leaves only by **holding** a small button for about a second, so it can't be exited by accident

### Not on the web yet
- 🔜 Photo upload, identify-from-photo and the photo gallery screens
- 🔜 Edit, merge or delete people and conversations
- 🔜 Speak the recall card aloud, follow-ups pulled from conversations, daily digest, notifications
- 🔜 Separate caregiver accounts and notes

---

## Flutter app

The phone app uses the same account, so your profile, people, conversations and photos are already there when you sign in.

### Account and setup
- ✅ Log in and register with the same **username and password**
- ✅ **Server address setting** with a "Test connection" button
- ✅ **Your profile tied to your username:** the same voice and face as on the web
  - First-run "Set up you" with guided voice setup and a face photo (front camera or a chosen photo); skippable, and reachable later from the menu
  - Your voice and face **sync with the web:** set them up on either and both know you, and your photo shows on both
- ✅ **Guided voice setup, like a voice assistant:** five sentences read aloud, live "what I heard" text with the words lighting up, each sentence checked before moving on, resumes if interrupted
- ✅ You are shown as **"You"** (face) or by your username (voice), never as a visitor

### Voice conversations
- ✅ Tap to record; audio streams as you speak
- ✅ **Live captions** with speaker labels: you, the visitor, or a known person by name
- ✅ **Automatic end after 15 seconds of silence**, with a countdown from 5 seconds
- ✅ Processing in the background, then a **result card:** summary, speech-share bar, show/hide transcript
- ✅ If the live connection drops, the recording is kept and uploaded instead, so nothing is lost
- ✅ Speaker separation and **recognition by voice**

### Live camera (vision mode)
- ✅ **Voice / Vision switch** on the main screen; vision adds the camera to a normal session
- ✅ **Face tags on the camera preview:** a dashed "verifying" tag first, then the confirmed name and match percentage
- ✅ Tags follow faces smoothly, survive a missed frame, and keep two faces apart
- ✅ Works on the **front and back cameras**, in portrait and landscape
- ✅ Your own face shows as "You", with no recall card and no name prompt
- ✅ Recall card for each recognized person, with live captions running at the same time
- ✅ The face seen during the session is saved, so an unknown person can be **named afterwards with their photo**
- ✅ Gentle on battery and data: small frames, a limited rate, and it stops when the session ends or the app goes to the background

### Recall, questions and people
- ✅ **Recall card** when someone is recognized by voice, by camera or in a photo: name, relationship, last seen, last conversation
- ✅ **Ask your memory** by typing or speaking, with source snippets and "I don't have a record of that."
- ✅ **Name people** after a conversation and later from History: a new person or "Someone I know"
- ✅ **People** screen (closest first, with a closeness label, and first-met and most-recent summaries) and **History** screen (with speech-share bars)
- ✅ **Life timeline:** decisions, activities, events, money and to-dos found in your conversations, with "Coming up", filters, tick-off to-dos, and your own items
- ✅ **Optional video of conversations:** saved from vision sessions on your own backend, watched and deleted from History

### Photos
- ✅ **Identify faces in a photo** picked from the gallery or taken with the camera: a labeled box on every face, a final answer in about a second
- ✅ **Save an unknown face as a person** in one step (name, relationship and the photo together); add more photos of someone to improve recognition
- ✅ Handles rotated phone photos and very large images
- ✅ **Photo gallery:** every photo you add is kept, with each face's identity and embedding stored
  - Grid of thumbnails, open the full image, delete
  - Filter by person, and a **"Who is this?"** list of photos with unrecognized faces
  - **Name a face** in a photo (new or existing person); it also improves recognition everywhere
  - **Re-identify** to fill in the same person on their other photos once someone new is named
  - **Find photos of someone** by giving a photo of them

### Accessibility
- ✅ **Big & simple mode:** large type, high contrast, one big button, hold to exit

### Reliability
- ✅ Clear messages when the server can't be reached (showing the address in use), when the microphone or camera is blocked, or when a session fails
- ✅ Signing in again automatically when the login expires

### Not in the Flutter app yet
- 🔜 Listening in the background / standby mode (needs platform work on both Android and iOS)
- 🔜 Offline mode that queues recordings and photos until the server is reachable
- 🔜 Push notifications, edit/merge/delete people, speaking the recall card aloud

---

## Behind both apps (backend)

- ✅ **Speech to text** (Whisper, English) and **live captions** streamed as you speak
- ✅ **Speaker separation and voice matching** to tell you from visitors and to recognize returning people by voice
- ✅ **Face detection and matching** (runs locally) with a cloud vision model that confirms identities, and an automatic local fallback
- ✅ **Summaries and question answering** written from your conversations, with a searchable index of everything said and everything on your timeline
- ✅ **Automatic life timeline:** structured decisions, activities, events, money and to-dos with real dates
- ✅ **Photo storage** with each face's embedding
- ✅ **Fast:** a short conversation is summarized and speaker-labeled about 3 seconds after it ends; first live caption in about 2 seconds; a photo identified in about 1 second
- ✅ **Private by account:** everything is scoped to the signed-in user, and raw audio is deleted once it has been processed
- ✅ **Configurable:** which parts run locally and which use cloud models is a setting, not a code change
