<template>
  <div class="hud" :class="{ simple }">
    <div class="viewfinder">
      <div v-show="!cameraOn && !waveOn" class="idle-plate">
        <div class="idle-ring">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="3" /></svg>
        </div>
      </div>
      <video ref="video" autoplay playsinline muted :class="{ hidden: !cameraOn }" />
      <div v-if="waveOn" class="wave on"><WaveCanvas :analyser="recorder.analyser.value" /></div>

      <div class="scrim-top" />
      <div class="scrim-bottom" />
      <div class="scan-sweep" :class="{ active: cameraOn && scanning }" />
      <div class="brackets" aria-hidden="true"><span class="tl" /><span class="tr" /><span class="bl" /><span class="br" /></div>

      <div class="hud-top">
        <div class="readout" role="status" aria-live="polite">
          <span class="dot" :class="dotKind" />
          <span class="val">{{ readout }}</span>
        </div>
        <div class="hud-controls">
          <button class="icon-btn" :class="{ 'id-on': enrolled }" type="button" aria-label="Set up your voice and face" @click="showEnroll = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" /><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4" /></svg>
          </button>
          <button class="icon-btn" type="button" aria-label="Ask your memory" @click="openMenu('ask')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M21 12a8 8 0 01-11.6 7.1L3 21l1.9-5.4A8 8 0 1121 12z" /><path d="M9.5 9.5a2.5 2.5 0 114 2c-.9.6-1.5 1-1.5 2M12 16.5v.01" /></svg>
          </button>
          <button class="icon-btn" type="button" aria-label="Open menu" @click="openMenu('people')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="5" cy="12" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="19" cy="12" r="1.4" /></svg>
          </button>
        </div>
      </div>

      <div v-for="t in tags" :key="t.key" class="face-tag"
           :class="{ unknown: t.unknown, identifying: t.identifying, self: t.is_self, flip: flips(t) }" :style="styleFor(t)">
        <div class="box" /><div class="lead" />
        <div class="label">
          {{ t.is_self ? 'You' : t.unknown ? (t.identifying ? 'Identifying…' : 'Unmatched') : t.name }}
          <span class="sub">{{ tagSub(t) }}</span>
        </div>
      </div>

      <div class="captions" aria-live="polite">
        <div v-for="l in captions.lines.value" :key="l.id" class="cap-line" :class="l.speaker === 'host' ? 'host' : 'other'">
          <span class="tag" aria-hidden="true" /><span>{{ l.text }}</span>
        </div>
        <div v-if="captions.partial.value" class="cap-line partial" :class="{ 'is-last': true }">
          <span class="tag" aria-hidden="true" /><span>{{ captions.partial.value }}</span>
        </div>
      </div>

      <RecallCard :people="recallPeople" />

      <button v-if="simple" class="simple-exit" type="button"
              @pointerdown="holdStart" @pointerup="holdCancel" @pointerleave="holdCancel">Hold to exit</button>

      <div class="dock">
        <div class="mode-pill" role="tablist" aria-label="Session mode">
          <button type="button" role="tab" :class="{ active: mode === 'vision' }" :aria-selected="mode === 'vision'"
                  aria-label="Vision and voice" :disabled="busy" @click="mode = 'vision'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M23 7l-7 5 7 5V7z" /><rect x="1" y="5" width="15" height="14" rx="2" /></svg>
          </button>
          <button type="button" role="tab" :class="{ active: mode === 'audio' }" :aria-selected="mode === 'audio'"
                  aria-label="Voice only" :disabled="busy" @click="mode = 'audio'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" /><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4" /></svg>
          </button>
        </div>
        <div v-if="simple" class="simple-hint">{{ phase === 'recording' ? 'Tap to stop' : phase === 'idle' ? 'Tap to start' : 'Please wait…' }}</div>
        <button class="rec-ring" :class="{ recording: phase === 'recording' }" type="button"
                :aria-label="phase === 'recording' ? 'Stop recording' : 'Start recording'"
                :disabled="phase === 'processing' || phase === 'starting'" @click="phase === 'recording' ? endSession() : startSession()">
          <span class="core" />
        </button>
      </div>
    </div>

    <SessionCard v-if="card" :result="card" @close="card = null" @name="naming = { sessionId: card.session_id, faceBlob }" />
    <NamePrompt v-if="naming" :session-id="naming.sessionId" :face-blob="naming.faceBlob" :face-b64="naming.faceB64"
                :people="people" @saved="onNamed" @skip="naming = null" />

    <div v-if="showEnroll" class="overlay open" role="dialog" aria-modal="true" aria-labelledby="enroll-title"
         @click.self="setupComplete && (showEnroll = false)">
      <div class="modal tall">
        <div class="m-kicker">One-time setup</div>
        <h2 id="enroll-title">Set up you</h2>
        <HostSetup :host="host" skippable @changed="refreshHost" @done="showEnroll = false" @skip="skipEnroll" />
      </div>
    </div>

    <MenuDrawer :open="menuOpen" :initial-tab="menuTab" :people="people" :history="history" :host="host"
                :simple="simple" @update:simple="setSimple" :save-video="saveVideo" @update:save-video="setSaveVideo"
                @watch-video="watchVideo"
                @close="menuOpen = false" @host-changed="refreshHost" @name-session="nameFromHistory" />
    <div v-if="videoView" class="overlay open" role="dialog" aria-modal="true" @click.self="closeVideo">
      <div class="modal tall">
        <div class="m-kicker">Recorded conversation</div>
        <video :src="videoView.url" controls autoplay playsinline class="watch" />
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="deleteVideo">Delete video</button>
          <button class="btn primary" type="button" @click="closeVideo">Close</button>
        </div>
      </div>
    </div>

    <ToastStack />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import { useAudioRecorder } from '@/composables/useAudioRecorder'
import { useSilenceDetector } from '@/composables/useSilenceDetector'
import { useFaceTags } from '@/composables/useFaceTags'
import { useLiveCaptions } from '@/composables/useLiveCaptions'
import { toast } from '@/composables/useToast'
import WaveCanvas from '@/components/WaveCanvas.vue'
import SessionCard from '@/components/SessionCard.vue'
import NamePrompt from '@/components/NamePrompt.vue'
import HostSetup from '@/components/HostSetup.vue'
import MenuDrawer from '@/components/MenuDrawer.vue'
import ToastStack from '@/components/ToastStack.vue'
import RecallCard from '@/components/RecallCard.vue'
import '@/assets/hud.css'

const SILENCE_SECONDS = 15
const SIMPLE_KEY = 'pl_simple'
const VIDEO_KEY = 'pl_save_video'
const RECALL_SECONDS = 20   // how long a recall card stays after the person was last seen/heard
const HOLD_MS = 1200
const ENROLL_SKIP_KEY = 'pl_enroll_skipped'

const router = useRouter()
const video = ref(null)

const mode = ref('vision')          // vision | audio (locked while a session is running)
const phase = ref('idle')           // idle | starting | recording | processing
const activeMode = ref('vision')    // mode of the session in progress / just ended
const busy = computed(() => phase.value !== 'idle')

const recorder = useAudioRecorder()
const { tags, scanning, recognized, sawUnknown, styleFor, flips, start: startTags, stop: stopTags, captureFull } = useFaceTags(video)
const captions = useLiveCaptions()
const silence = useSilenceDetector({ silenceMs: SILENCE_SECONDS * 1000, onSilence: () => endSession() })

const cameraOn = computed(() => phase.value === 'recording' && activeMode.value === 'vision')
const waveOn = computed(() => phase.value === 'recording' && activeMode.value === 'audio')

let stream = null
let sessionId = null

const card = ref(null)
const naming = ref(null)   // { sessionId, faceBlob?, faceB64? } while the name prompt is open
const faceBlob = ref(null)

const people = ref([])
const history = ref([])
const host = ref(null)          // GET /host: username, voice/face status, photo (same on every device)
const enrolled = computed(() => !!host.value?.voice_enrolled)
const setupComplete = computed(() => !!host.value?.voice_enrolled && !!host.value?.face_enrolled)
const showEnroll = ref(false)
const menuOpen = ref(false)
const menuTab = ref('people')

// ── Big & simple mode (remembered on this device) ──
function readSimple() {
  try { return localStorage.getItem(SIMPLE_KEY) === '1' } catch (e) { return false }
}
const simple = ref(readSimple())
function setSimple(on) {
  simple.value = on
  try { localStorage.setItem(SIMPLE_KEY, on ? '1' : '0') } catch (e) { /* storage unavailable */ }
  if (on) menuOpen.value = false
}
// ── Save video of vision sessions (opt-in, remembered on this device) ──
const saveVideo = ref((() => { try { return localStorage.getItem(VIDEO_KEY) === '1' } catch (e) { return false } })())
function setSaveVideo(on) {
  saveVideo.value = on
  try { localStorage.setItem(VIDEO_KEY, on ? '1' : '0') } catch (e) { /* storage unavailable */ }
}

let videoRec = null
let videoChunks = []
function startVideo() {
  if (activeMode.value !== 'vision' || !saveVideo.value || !window.MediaRecorder) return
  try {
    videoChunks = []
    videoRec = new MediaRecorder(stream, { videoBitsPerSecond: 800000 })
    videoRec.ondataavailable = (e) => e.data.size && videoChunks.push(e.data)
    videoRec.start(1000)
  } catch (e) {
    videoRec = null
  }
}
function stopVideo() {
  return new Promise((resolve) => {
    if (!videoRec || videoRec.state === 'inactive') return resolve(null)
    videoRec.onstop = () => { resolve(new Blob(videoChunks, { type: videoRec.mimeType || 'video/webm' })); videoRec = null }
    videoRec.stop()
  })
}

// Watch a saved video (fetched with the login, so it stays private)
const videoView = ref(null)
async function watchVideo(session) {
  try {
    const { data } = await api.get(`/session/${session.id}/video`, { responseType: 'blob' })
    menuOpen.value = false
    videoView.value = { id: session.id, url: URL.createObjectURL(data) }
  } catch (e) {
    toast('Could not open that video')
  }
}
function closeVideo() {
  if (videoView.value) URL.revokeObjectURL(videoView.value.url)
  videoView.value = null
}
async function deleteVideo() {
  const id = videoView.value?.id
  closeVideo()
  try { await api.delete(`/session/${id}/video`); toast('Video deleted'); refreshLists() } catch (e) { toast('Could not delete the video') }
}

let holdTimer = null
const holdStart = () => { holdTimer = setTimeout(() => setSimple(false), HOLD_MS) }
const holdCancel = () => clearTimeout(holdTimer)

// ── Recall cards: who is here right now, and what we last talked about ──
const seenAt = ref({})     // person_id -> last time seen (face) or heard (voice), ms
const clockTick = ref(Date.now())
let tickTimer = null

function touchPerson(id) {
  if (!id) return
  seenAt.value = { ...seenAt.value, [id]: Date.now() }
  if (!people.value.some((p) => p.id === id)) refreshLists()   // someone new since the list loaded
}

watch(tags, (list) => list.forEach((t) => !t.unknown && !t.is_self && touchPerson(t.person_id)))
watch(() => captions.lines.value, (list) => list.forEach((l) => touchPerson(l.person_id)))
watch(recognized, (r) => r && touchPerson(r.person_id))

const recallPeople = computed(() => {
  if (phase.value !== 'recording') return []
  return Object.entries(seenAt.value)
    .filter(([, t]) => clockTick.value - t < RECALL_SECONDS * 1000)
    .sort((a, b) => b[1] - a[1])
    .map(([id]) => people.value.find((p) => p.id === id))
    .filter(Boolean)
    .slice(0, 2)
})

function tagSub(t) {
  if (t.is_self) return t.name
  if (t.identifying) return t.unknown ? 'Checking…' : `${Math.round(t.confidence * 100)}% · verifying`
  return t.unknown ? 'No match' : `${Math.round(t.confidence * 100)}% match`
}

// ── Status readout ────────────────────────────────────
const clock = computed(() => {
  const s = recorder.seconds.value
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

const readout = computed(() => {
  if (phase.value === 'processing') return 'Processing…'
  if (phase.value === 'recording') {
    let label
    if (activeMode.value === 'audio') {
      label = silence.silentFor.value >= 5
        ? `Silence · ending in ${SILENCE_SECONDS - silence.silentFor.value}s`
        : 'Listening'
    } else {
      label = recognized.value ? `${recognized.value.name.split(' ')[0]} matched` : 'Scanning'
    }
    return `Rec ${clock.value} · ${label}`
  }
  return mode.value === 'vision' ? 'Standby' : 'Standby · voice only'
})

const dotKind = computed(() => {
  if (phase.value === 'recording') return recognized.value ? 'match' : 'live'
  return phase.value === 'processing' ? 'ok' : ''
})

// ── Session lifecycle ─────────────────────────────────
async function startSession() {
  if (phase.value !== 'idle') return
  phase.value = 'starting'
  seenAt.value = {}
  card.value = null
  activeMode.value = mode.value
  try {
    stream = await navigator.mediaDevices.getUserMedia(
      mode.value === 'vision' ? { video: { facingMode: 'user' }, audio: true } : { audio: true },
    )
  } catch (e) {
    phase.value = 'idle'
    toast(mode.value === 'vision' ? 'Camera or mic blocked' : 'Mic blocked')
    return
  }

  try {
    const fd = new FormData()
    fd.append('mode', mode.value)
    sessionId = (await api.post('/session/start', fd)).data.id
    await recorder.start(stream)
  } catch (e) {
    releaseStream()
    phase.value = 'idle'
    toast(e.response?.data?.detail || 'Could not start session')
    return
  }

  phase.value = 'recording'
  startVideo()
  captions.start(stream, sessionId) // best-effort; the recording below is what gets processed
  if (activeMode.value === 'vision') {
    await nextTick()
    video.value.srcObject = stream
    video.value.onloadedmetadata = () => startTags()
  } else {
    silence.start(stream)
  }
}

async function endSession() {
  if (phase.value !== 'recording') return
  phase.value = 'processing'
  silence.stop()
  captions.stop()

  const person = recognized.value
  const unknownFace = sawUnknown.value
  faceBlob.value = activeMode.value === 'vision' ? await captureFull() : null
  stopTags()

  const audio = await recorder.stop()
  const video = await stopVideo()
  releaseStream()

  try {
    const fd = new FormData()
    fd.append('audio', audio, 'session.webm')
    if (person) fd.append('person_id', person.person_id)
    if (faceBlob.value) fd.append('face_image', faceBlob.value, 'face.jpg')  // kept so they can be named later
    if (video) fd.append('video', video, 'session.webm')
    await api.post(`/session/${sessionId}/end`, fd)
    const data = await waitForResult(sessionId)

    // someone worth naming: an unmatched voice, an unmatched face, or (diarization unavailable) any speech
    const otherSpeaker = data.other_speaker_detected ?? !!data.transcript
    const needsName = !data.person_id && (otherSpeaker || (activeMode.value === 'vision' && unknownFace))

    card.value = { ...data, needs_naming: needsName, mode: activeMode.value, durationSec: data.durationSec ?? recorder.seconds.value }
    if (needsName) setTimeout(() => (naming.value = { sessionId: data.session_id, faceBlob: faceBlob.value }), 500)
    refreshLists()
  } catch (e) {
    toast(e.response?.data?.detail || e.message || 'Session failed to save')
  } finally {
    phase.value = 'idle'
  }
}

// The backend processes a session in the background; poll until it finishes.
const POLL_MS = 1000
const POLL_TIMEOUT_MS = 5 * 60 * 1000

async function waitForResult(id) {
  const deadline = Date.now() + POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    const { data } = await api.get(`/session/${id}`)
    if (data.status === 'failed') throw new Error(data.error || 'Processing failed')
    if (data.status === 'ended' || data.status === 'resolved') return data
    await new Promise((r) => setTimeout(r, POLL_MS))
  }
  throw new Error('Processing timed out')
}

function releaseStream() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  if (video.value) video.value.srcObject = null
}

// Name someone from a past, unnamed session (History tab)
async function nameFromHistory(session) {
  try {
    const { data } = await api.get(`/session/${session.id}`, { params: { include_face: true } })
    menuOpen.value = false
    naming.value = { sessionId: session.id, faceB64: data.face_image_b64 || '' }
  } catch (e) {
    toast('Could not open that session')
  }
}

function onNamed({ person, session_id: savedId }) {
  naming.value = null
  if (card.value?.session_id === savedId) {
    card.value = { ...card.value, person_name: person.name, person_id: person.id, needs_naming: false }
  }
  toast(`Saved ${person.name}`)
  refreshLists()
}

// ── Voice enrollment ──────────────────────────────────
async function refreshHost() {
  try { host.value = (await api.get('/host')).data } catch (e) { /* offline */ }
}

function skipEnroll() {
  showEnroll.value = false
  try { localStorage.setItem(ENROLL_SKIP_KEY, '1') } catch (e) { /* storage unavailable */ }
}

// ── Menu / data ───────────────────────────────────────
function openMenu(tab) {
  menuTab.value = tab
  menuOpen.value = true
  refreshLists()
}

async function refreshLists() {
  try {
    const [p, h] = await Promise.all([api.get('/people'), api.get('/sessions')])
    people.value = p.data
    history.value = h.data
  } catch (e) {
    console.error('Failed to load people/history', e)
  }
}

function onKeydown(e) {
  if (e.key !== 'Escape') return
  if (naming.value) naming.value = null
  else if (showEnroll.value && setupComplete.value) showEnroll.value = false
  else if (menuOpen.value) menuOpen.value = false
}

onMounted(async () => {
  const { data } = await supabase.auth.getSession()
  if (!data.session) return router.replace('/login')

  window.addEventListener('keydown', onKeydown)
  tickTimer = setInterval(() => (clockTick.value = Date.now()), 1000)
  refreshLists()

  await refreshHost()
  let skipped = false
  try { skipped = localStorage.getItem(ENROLL_SKIP_KEY) === '1' } catch (e) { /* storage unavailable */ }
  if (!setupComplete.value && !skipped) setTimeout(() => (showEnroll.value = true), 500)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  clearInterval(tickTimer)
  clearTimeout(holdTimer)
  silence.stop()
  captions.stop()
  stopTags()
  recorder.release()
  releaseStream()
})
</script>
