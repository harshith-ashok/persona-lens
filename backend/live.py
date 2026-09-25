"""Live captions: PCM audio in over a WebSocket, rolling Whisper transcription out.

Wire format (see docs/MOBILE_INTEGRATION.md):
  client -> {"type":"start","token":"<supabase access token>","session_id":"<uuid>"}
  server -> {"type":"ready"}
  client -> binary frames: 16 kHz, mono, signed 16-bit little-endian PCM
  server -> {"type":"partial","text":...}                        current utterance, replaced by later events
            {"type":"final","text":...,"speaker":...,"start":s,"end":s}   utterance finished
  client -> {"type":"stop"}   (server flushes the last utterance, then closes)

The streamed audio is also kept, so a session can end without re-uploading the recording.
"""
import asyncio
import contextlib
import os
import tempfile

import numpy as np
import torch
from fastapi import WebSocket, WebSocketDisconnect

import config
import host
import speech
import voice
from db import supabase
from session import _load_voices, get_session

SAMPLE_RATE = 16000
PARTIAL_EVERY = 1.5     # seconds of new audio between partial updates
MAX_UTTERANCE = 8.0     # force a final line after this much continuous speech (limits mixed-speaker lines)
SILENCE_SECONDS = 0.8   # trailing quiet that ends an utterance
SILENCE_RMS = 0.012
MIN_LABEL_SECONDS = 1.0 # shortest utterance we try to attribute to a speaker


def audio_path(session_id: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"pl_live_{session_id}.pcm")


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x * x))) if len(x) else 0.0


def _transcribe(samples: np.ndarray) -> str:
    """Whisper on a raw float32 buffer, dropping the phantom text it produces on noise."""
    with speech._transcribe_lock:
        result = speech.get_whisper().transcribe(
            samples, fp16=False, condition_on_previous_text=False, temperature=0.0,
            language=config.TRANSCRIBE_LANGUAGE)
    keep = [s["text"].strip() for s in result.get("segments", [])
            if not (s.get("no_speech_prob", 0) > 0.6 and s.get("avg_logprob", 0) < -1.0)]
    return " ".join(t for t in keep if t).strip()


class LiveTranscriber:
    def __init__(self, host_embedding=None, known_voices=None, host_name=None, label=True):
        self.label = label
        self.host_name = host_name
        self.host_embedding = host_embedding
        self.known_voices = known_voices or []
        self.buf = np.zeros(0, dtype=np.float32)
        self.committed = 0.0     # seconds already finalized
        self.since_partial = 0.0
        self.last_partial = ""

    def _label(self, samples: np.ndarray) -> tuple[str, str | None]:
        """-> (speaker label, person_id if a known person's voice matched)."""
        if not self.label or len(samples) < MIN_LABEL_SECONDS * SAMPLE_RATE:
            return "other", None
        try:
            audio = {"waveform": torch.from_numpy(samples).unsqueeze(0), "sample_rate": SAMPLE_RATE}
            with voice._lock:
                emb = voice._embed(audio)
            return voice._classify(emb, self.host_embedding, self.known_voices)
        except Exception as e:  # voice models unavailable: captions still work, unlabeled
            print("Live speaker label skipped:", e)
            return "other", None

    def _final(self, text: str) -> dict:
        start = self.committed
        dur = len(self.buf) / SAMPLE_RATE
        speaker, person_id = self._label(self.buf) if text else ("other", None)
        name = self.host_name if speaker == "host" else (None if speaker == "other" else speaker)
        event = {"type": "final", "text": text, "speaker": speaker, "person_id": person_id, "name": name,
                 "start": round(start, 2), "end": round(start + dur, 2)}
        self.committed += dur
        self.buf = np.zeros(0, dtype=np.float32)
        self.since_partial = 0.0
        self.last_partial = ""
        return event

    def feed(self, pcm: bytes, flush: bool = False) -> list[dict]:
        """Blocking (runs Whisper): call from a thread. Returns the events to send."""
        if pcm:
            chunk = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
            self.buf = np.concatenate([self.buf, chunk])
            self.since_partial += len(chunk) / SAMPLE_RATE

        dur = len(self.buf) / SAMPLE_RATE
        if dur < 0.4:
            return []

        tail = self.buf[-int(SILENCE_SECONDS * SAMPLE_RATE):]
        trailing_quiet = dur >= SILENCE_SECONDS and _rms(tail) < SILENCE_RMS
        has_speech = _rms(self.buf) >= SILENCE_RMS * 0.6

        if not has_speech:
            # nothing but quiet: keep just a short lead-in so the next word isn't clipped
            self.buf = self.buf[-int(0.3 * SAMPLE_RATE):]
            self.committed += max(0.0, dur - len(self.buf) / SAMPLE_RATE)
            self.since_partial = 0.0
            return []

        due = self.since_partial >= PARTIAL_EVERY
        if not (due or flush or (trailing_quiet and self.last_partial != "")):
            return []

        text = _transcribe(self.buf)
        self.since_partial = 0.0
        if flush or trailing_quiet or dur >= MAX_UTTERANCE:
            return [self._final(text)] if text else self._drop()
        if text and text != self.last_partial:
            self.last_partial = text
            return [{"type": "partial", "text": text}]
        return []

    def _drop(self) -> list[dict]:
        self.committed += len(self.buf) / SAMPLE_RATE
        self.buf = np.zeros(0, dtype=np.float32)
        self.last_partial = ""
        return []


async def handle(ws: WebSocket) -> None:
    await ws.accept()
    path = None
    try:
        hello = await ws.receive_json()
        enroll = hello.get("purpose") == "enroll"     # voice-setup captions: no session, nothing kept
        if hello.get("type") != "start" or not hello.get("token") or not (hello.get("session_id") or enroll):
            await ws.send_json({"type": "error", "message": "first message must be {type:'start', token, session_id}"})
            return await ws.close(code=1008)

        try:
            res = await asyncio.to_thread(supabase.auth.get_user, hello["token"])
            patient_id = res.user.id
            if not enroll:
                session = await asyncio.to_thread(get_session, hello["session_id"], patient_id)
                if session["status"] != "open":
                    raise ValueError(f"session is {session['status']}")
        except Exception as e:
            await ws.send_json({"type": "error", "message": f"unauthorized: {e}"})
            return await ws.close(code=1008)

        if enroll:
            host_emb, known, host_name = None, [], None
            transcriber = LiveTranscriber(None, [], None, label=False)
        else:
            try:
                host_emb, known = await asyncio.to_thread(_load_voices, patient_id)
            except Exception:
                host_emb, known = None, []
            host_name = await asyncio.to_thread(host.display_name, patient_id)
            transcriber = LiveTranscriber(host_emb, known, host_name)
            path = audio_path(hello["session_id"])
            open(path, "wb").close()
        await ws.send_json({"type": "ready"})

        with (open(path, "ab") if path else contextlib.nullcontext()) as sink:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes"):
                    if sink:
                        sink.write(message["bytes"])
                        sink.flush()
                    events = await asyncio.to_thread(transcriber.feed, message["bytes"])
                elif message.get("text") and '"stop"' in message["text"]:
                    events = await asyncio.to_thread(transcriber.feed, b"", True)
                    for event in events:
                        await ws.send_json(event)
                    break
                else:
                    continue
                for event in events:
                    await ws.send_json(event)

        await ws.close()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print("Live captions error:", e)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
