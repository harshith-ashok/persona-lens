# Web app — sales pitch demo script

A run-through for presenting the **web version** live, from setting up a new person's profile to trying every feature. Each step has what to do, what to say, what you should see, and what to do if it doesn't work.

**Length:** about 10 minutes for the full demo, or 5 minutes using only the steps marked ★.
**You need:** one presenter (the patient) and, for the best effect, one helper who plays the visitor.

---

## Part A — Before the meeting

### A1. Start everything (30 minutes before)

Run these on the backend machine.

1. `docker compose up -d` (repo root): database and login
2. Ollama running and signed in, with the cloud models available (`gpt-oss:120b-cloud`, `gemma4:31b-cloud`) and `nomic-embed-text` pulled
3. Backend: `cd backend && source .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8120`
4. Web: `cd frontend && npm run dev`, then open **http://localhost:5173** in **Chrome**

Wait about **20 seconds** after the backend starts: it loads its speech and voice models in the background, and the first conversation is slower until they are ready.

### A2. Check it works (5 minutes)

- `http://localhost:8120/health` shows `{"status":200}`
- Chrome allows **camera and microphone** for localhost (the page must be on `localhost` or HTTPS for the microphone to work)
- Good light on your face; the camera at eye level; a quiet room
- Speakers off, or use a headset, so the microphone doesn't pick up the laptop's own sound
- Internet is on (summaries, questions and face confirmation use cloud models)
- Close other tabs; turn off notifications

### A3. Rehearse with a fresh account, then decide which account to demo

**Recommended:** demo from a **pre-seeded account** so the recall card, People list and Timeline already have content. Seed it once, the day before:

1. Register a demo account (for example username `demo`, full name and password of your choice)
2. Do Part B (your own profile) once
3. Have your helper play **Meera** and run the **seed conversation** below **twice**, in two separate sessions (Part D); name her "Meera", relationship "Daughter", when asked
4. Check the Timeline tab shows the items and People shows Meera

You will then demo a **second** account (or the same one, skipping the parts already done). To show the setup live, create a fresh account for the profile section only (see Part B) and switch to the seeded account for the rest.
...l;llkkjjjkjkjk

### A4. The seed conversation (say it aloud, two people)

Speak clearly, at a normal pace, with a short pause between speakers.

> **Meera:** "Hi, it's Meera. I'll bring the grandchildren this Saturday, and we can go for a walk in the garden."  
> **You:** "That would be lovely. I decided to move my tablets to the evening from now on. Yesterday I paid twelve hundred rupees for the electricity bill."
> **Meera:** "Good. Don't forget your doctor appointment on Thursday."
> **You:** "Please remind me to call the bank on Monday."

This is what fills the Timeline (a plan, a decision, a payment, an appointment, a to-do) and gives the recall card its "last time" summary.

### A5. Reset between demos

- Use a **new username** for a clean run of the profile section, or
- Keep the seeded account and only redo steps you want to show ("Record it again" for voice; "Retake with camera" for face)

---

## Part B — ★ Set up the voice profile (about 3 minutes)

**Say:** "PersonaLens starts by learning who _you_ are, so it can tell you apart from everyone you talk to. Your username is your identity, and your voice and face are tied to it."

1. Open the web app and **register** (username, full name, password, confirm password) or log in with a fresh account.
2. The **"Set up you"** screen appears: _Signed in as_ **your username**.
   - **Point out:** "There's no email. Your username is you."

### B1. Voice — five sentences

3. Under **Your voice**, press **Start — read the sentence aloud**.
4. Read sentence 1 (it shows on screen): **"The quick brown fox jumps over the lazy dog near the river."**
   - **Watch for:** as you speak, the **"What I heard"** box fills in live, and the sentence's words turn **teal** as they are understood.
   - **Say:** "It shows me what it understood while I speak, so I know my voice is being picked up clearly."
5. It stops by itself when the sentence is heard, checks it, and says **Got it.** Then press **Read the next sentence** and read the next ones:
   - "Please remind me who is visiting this afternoon."
   - "My favorite kind of music is quiet piano in the morning."
   - "Thank you for coming, it is so good to see you again."
   - "I would like a cup of warm tea with a little honey."
6. After the fifth, the screen says **Saving your voice…**, then **Voice saved** and **Your voice is set up ✓**.

**If a sentence isn't accepted:** it shows _I heard "…"_ and asks you to read it exactly as shown. Just try again. (This is a good moment to say: "It only accepts a sentence once it truly understood it.")
**If nothing is heard:** "I didn't hear anything. Check your microphone and try again." Check the mic permission and input device.
**Optional show-off:** read the wrong sentence on purpose once, and let the audience see it refuse it.

### B2. Face

7. Under **Your face**, press **Use camera**, look at the camera, press **Capture**.
   - Your photo appears, with **"Saved to your account. Every device you sign in on can use it."**
   - **Say:** "Your voice and your face are saved to your account, so the phone app knows the same you."
8. Both steps show a teal ✓. Press **Done**.

**If "No face found in the photo":** improve the light, face the camera, retake.

---

## Part C — ★ The main screen and live recognition (about 3 minutes)

**Say:** "This is the screen the patient uses. One big button."

1. Point out the **status line** (top left: _Standby_), the two **mode icons** (camera = Vision, microphone = Voice only), the **big record button**, the **mic icon** (your voice and face setup), the **speech-bubble icon** (Ask), and the **••• menu**.
2. Stay in **Vision** mode. Press the **record button**.
   - Status line: **Rec 00:03 · Scanning**.
3. **Your own face** appears with a tag that says **You** and your username.
   - **Say:** "It knows this is me, so it never treats me as a visitor: no pop-ups, no 'who's that?'"
4. Bring your helper into the frame (see Part D for the conversation).

---

## Part D — ★ A conversation with live captions and recall (about 3 minutes)

_Use the seeded account here, so Meera is already known._

**Say:** "Now someone I know walks up."

1. With the record button on (Vision mode), your helper (**Meera**) steps into view.
   - Her tag first says **Identifying…** (dashed box), then her **name** with a match percentage.
   - **Say:** "It shows a fast answer first, then confirms it. It never claims certainty it doesn't have."
2. A **recall card** appears (top left): **Meera · Daughter · Last seen … ago · Last time: …**
   - **Say:** "This is the moment that matters. Instead of struggling to remember, I see who she is and what we last talked about."
3. Have the conversation (use the seed conversation lines, or make up something natural).
   - **Live captions** appear about **two seconds** behind speech, at the bottom of the screen, with a colored dot for each speaker.
   - **Say:** "Captions appear live, and it can tell who's speaking, me or her."
4. **End the session:** in Vision mode, press the **record button** again.
   - **Optional (Voice only mode):** to show the automatic ending, switch to the **microphone** mode icon, start a session, talk briefly, then **stop talking**. After **5 seconds** the status line shows **Silence · ending in …s**, and at **15 seconds** the session ends by itself. The automatic end applies only in Voice only mode.
5. **Processing…** shows for about **three seconds**, then the **result card**: the short summary, a bar showing how much each person spoke, and **Show transcript**.
   - **Say:** "About three seconds after we stop talking, it has written a summary and worked out who said what."

**If the recall card doesn't show:** she must have been named in an earlier session (Part A3). If she is new, that is the next step, so use it (Part E).

---

## Part E — ★ A new person: naming (about 1 minute)

_Use a helper who has **not** been named, or a fresh account._

1. Have the new person talk and stand in view for a few seconds, then end the session.
2. The **"Who was that?"** window opens with their captured **face photo**.
   - Enter **Name** and pick a **Relationship**, press **Save**.
   - **Say:** "I name them once. From now on it recognizes them by face and by voice."
3. Or press **Skip**, and later open **••• → History → Name this person** on that session.
   - Choose **New person** or **Someone I know**.
4. Run another short session: they are recognized straight away, with a recall card.

---

## Part F — Try the other features (2–3 minutes; pick what fits)

### F1. ★ Ask your memory

1. Press the **speech-bubble icon** (or **••• → Ask**).
2. Ask, typed or spoken (press the mic button, speak, press again):
   - "**Who visited me recently?**"
   - "**What did I decide about my tablets?**" → _You decided to switch your tablets to the evening._
   - "**How much did I pay for the electricity bill?**" → _1200 rupees._
   - "**What is coming up this week?**" → the grandchildren's visit and the doctor appointment
3. Point out the **source snippets** under the answer.
4. Ask something that never happened: "**When did I travel to the moon?**" → **"I don't have a record of that."**
   - **Say:** "It only answers from what was really said. It won't make things up."

### F2. ★ Life timeline

1. **••• → Timeline**.
2. Show **Coming up** (the Saturday visit, the doctor appointment, the bank call) and the earlier items (decision, payment).
   - **Say:** "It listened to the conversation and pulled out the plans, the payment and the reminder, with real dates."
3. Tick the **to-do** ("Call the bank") to mark it done.
4. Press a filter: **Money** shows just the payment.
5. Press **Add an item** to add one by hand (for example, a to-do: "Pick up prescription").

### F3. People and closeness

1. **••• → People**: each person has a relationship and a closeness label (**Very close**, **Regular**, **Occasional**), closest first.
2. Tap a person: **First met** and **Most recent** summaries.

### F4. History and video (optional)

1. **••• → More →** turn on **Save video of conversations** (off by default).
2. Record a short Vision session, end it, then **••• → History → Watch video**: it plays, and you can drag to seek.
3. Press **Delete video** to show it can be removed.
   - **Say:** "Video is optional, off by default, stays on our own machine, and can be deleted."

### F5. ★ Big & simple mode (for the patient)

1. **••• → More →** turn on **Big & simple mode**.
2. The screen becomes white-on-black with huge text and **one large button** ("Tap to start").
3. Start a short session: captions and the recall card are large.
4. To leave: **press and hold** the small **Hold to exit** button (top right) for about a second.
   - **Say:** "For someone who finds screens hard, there is only one thing to press. And it can't be exited by accident."

---

## Part G — Close (1 minute)

**Say:** "In about ten minutes you saw it learn who I am, recognize someone I love by face and by voice, caption our conversation live, remember it, and answer questions about it. The phone app uses the same account, so it all follows me."

Then move to your slides: roadmap, pricing, pilot request.

---

## Part H — If something goes wrong

| What happens                                                 | What to do                                                                                                          |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| Nothing loads / login fails                                  | Check the backend health page (`/health`) and that `docker compose up -d` is running; refresh the page              |
| Camera or microphone blocked                                 | Click the lock icon in the address bar, allow camera and microphone, reload                                         |
| A tag says "Identifying…" for a long time                    | The cloud model may be slow or offline: it falls back to the local match by itself. Keep talking; do not wait       |
| Captions don't appear                                        | The recording still works. Say: "Captions are best-effort; the full transcript arrives when we finish" and continue |
| "Processing…" takes more than 10 seconds                     | Right after a restart the models are still warming up. Wait, or move on to Ask and come back                        |
| The visitor isn't recognized                                 | They may not be named yet: name them (Part E) and try again. Face the camera in good light                          |
| A sentence isn't accepted during voice setup                 | Read it exactly as shown; reduce background noise; move closer to the microphone                                    |
| Ask says "I don't have a record of that." for something real | Say it as designed: it only answers from what was recorded. Ask a question about the seeded conversation instead    |
| Total failure                                                | Switch to the recorded backup video of the demo (**record one during rehearsal**)                                   |

---

## Part I — What to say, and what not to say

**Safe to say (all true today)**

- "Your voice and face are tied to your username and follow you between the web and phone apps."
- "It recognizes people by face and by voice."
- "Captions appear about two seconds behind speech; a summary about three seconds after a conversation."
- "It answers only from what was recorded, and says so when it doesn't know."
- "Audio is deleted once it's processed. Video is optional, off by default, and can be deleted."

**Do not say**

- "Everything stays on the device." Conversation text and face crops go to cloud AI services (summaries, questions, face confirmation).
- "It's always right" or any accuracy percentage. Accuracy on real family photos has not been measured yet.
- "It works in any language." It is English only.
- "It listens in the background." Not yet; a person starts a session.
- "It's a medical device." It is an assistive memory tool, and its summaries are automatically generated and can be wrong.

---

## Quick reference — the ten-minute run order

| #   | Part                                                 | Time     | ★   |
| --- | ---------------------------------------------------- | -------- | --- |
| 1   | B — Voice profile (five sentences) and face          | 3 min    | ★   |
| 2   | C — Main screen, "You" tag                           | 1 min    | ★   |
| 3   | D — Conversation, live captions, recall card, result | 3 min    | ★   |
| 4   | E — Name a new person                                | 1 min    | ★   |
| 5   | F1 — Ask your memory                                 | 1 min    | ★   |
| 6   | F2 — Life timeline                                   | 1 min    | ★   |
| 7   | F5 — Big & simple mode                               | 1 min    | ★   |
| 8   | F3, F4 — People closeness, history and video         | optional |     |
