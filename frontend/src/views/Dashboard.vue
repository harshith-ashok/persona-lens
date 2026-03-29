<template>
  <div class="shell">
    <video ref="video" autoplay playsinline class="video" />

    <div
      v-for="(face, i) in faces"
      :key="'box-' + i"
      class="face-wrap"
      :style="getWrapStyle(face)"
    >
      <div class="face-box" :class="{ unknown: isUnknown(face) }" />

      <div class="face-label" :class="{ unknown: isUnknown(face) }">
        <span class="face-label-name">
          {{ isUnknown(face) ? 'Unknown' : face.name }}
        </span>

        <span v-if="face.confidence" class="face-label-conf">
          {{ Math.round(face.confidence * 100) }}%
        </span>

        <span
          v-if="face.person_id && relations[face.person_id]"
          class="face-label-relation"
        >
          • {{ relations[face.person_id] }}
        </span>
      </div>
    </div>

    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-brand">
          <span class="brand-dot" :class="{ active: faces.length > 0 }" />
          <span class="brand-text">PERSONALENS</span>
        </div>
      </div>

      <!-- <div class="statusbar">
        <span class="status-item">
          <span class="status-dot" :class="{ live: cameraActive }" />
          {{ cameraActive ? 'LIVE' : 'OFFLINE' }}
        </span>
        <span class="status-divider">|</span>
        <span class="status-item">
          {{ faces.length }} FACE{{ faces.length !== 1 ? 'S' : '' }} DETECTED
        </span>
      </div> -->
      
      <div class="stats-strip">
        <div class="stat">
          <div class="stat-num">{{ faces.length }}</div>
          <div class="stat-label">IN FRAME</div>
        </div>
        <div class="stat-div" />
        <div class="stat">
          <div class="stat-num">{{ knownCount }}</div>
          <div class="stat-label">IDENTIFIED</div>
        </div>
        <div class="stat-div" />
        <div class="stat">
          <div class="stat-num">{{ unknownCount }}</div>
          <div class="stat-label">UNKNOWN</div>
        </div>
      </div>

      <div class="sidebar-section-label">DETECTED PEOPLE</div>
      <div class="face-list">
        <transition-group name="card">
          <div
            v-for="(face, i) in faces"
            :key="face.person_id || face.name + i"
            class="face-card"
            :class="{ unknown: isUnknown(face) }"
          >
            <div class="card-top">
              <div class="avatar" :class="avatarColor(face.name)">
                {{ (face.name || '?')[0].toUpperCase() }}
              </div>
              <div class="card-meta">
                <div class="card-name">
                  {{ isUnknown(face) ? 'Unidentified' : face.name }}
                </div>
                <div class="card-conf" v-if="face.confidence">
                  {{ Math.round(face.confidence * 100) }}% match
                </div>
              </div>
              <div class="card-badge" :class="isUnknown(face) ? 'badge-warn' : 'badge-ok'">
                {{ isUnknown(face) ? 'NEW' : 'ID' }}
              </div>
            </div>

            <div
              v-if="face.person_id && summaries[face.person_id]"
              class="card-summary"
            >
              <div v-if="summaries[face.person_id].first_summary" class="summary-row">
                <span class="summary-tag">FIRST</span>
                <span class="summary-text">{{ summaries[face.person_id].first_summary }}</span>
              </div>
              <div v-if="summaries[face.person_id].last_summary" class="summary-row">
                <span class="summary-tag">LAST</span>
                <span class="summary-text">{{ summaries[face.person_id].last_summary }}</span>
              </div>
            </div>
          </div>
        </transition-group>

        <div v-if="faces.length === 0" class="empty-state">
          <div class="empty-icon">◎</div>
          <div class="empty-text">No faces in frame</div>
        </div>
      </div>

      <div class="mic-section">
        <div class="sidebar-section-label" style="padding: 0 0 8px;">INTERACTION LOG</div>
        <button
          class="mic-btn"
          :class="{ recording: isRecording }"
          @click="isRecording ? stopRecording() : startRecording()"
        >
          <span class="mic-icon">{{ isRecording ? '⏹' : '⏺' }}</span>
          {{ isRecording ? 'Stop Recording' : 'Start Recording' }}
        </button>
        <div v-if="transcript" class="log-block">
          <div class="log-tag">TRANSCRIPT</div>
          <p class="log-text">{{ transcript }}</p>
        </div>
        <div v-if="summary" class="log-block">
          <div class="log-tag">SUMMARY</div>
          <p class="log-text">{{ summary }}</p>
        </div>
      </div>
    </aside>

    <div class="statusbar">
      <span class="status-item">
        <span class="status-dot" :class="{ live: cameraActive }" />
        {{ cameraActive ? 'LIVE' : 'OFFLINE' }}
      </span>
      <span class="status-divider">|</span>
      <span class="status-item">
        {{ faces.length }} FACE{{ faces.length !== 1 ? 'S' : '' }} DETECTED
      </span>
    </div>

    <transition name="popup">
      <div v-if="hasUnknown" class="add-popup">
        <div class="add-popup-header">
          <span class="add-popup-indicator" />
          <span class="add-popup-title">New Face Detected</span>
          <button class="add-popup-close" @click="dismissPopup">✕</button>
        </div>
        <p class="add-popup-hint">
          {{ unknownCount }} unidentified person{{ unknownCount !== 1 ? 's' : '' }} in frame.
          Enter a name to register them.
        </p>
        <div class="add-popup-row">
          <input
            v-model="name"
            placeholder="Enter name…"
            class="add-input"
            @keyup.enter="addFace"
          />
          <button class="add-btn" @click="addFace">ADD</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import axios from 'axios'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://pffshbkpvbxakvblflzw.supabase.co'
const SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZnNoYmtwdmJ4YWt2YmxmbHp3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MDUyMTIsImV4cCI6MjA5MDE4MTIxMn0.4rUiGa7rBz7dwloK6nXHqKx2_2nJj1lQpGM7PZQXMLY'
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

const API = 'http://localhost:8120'

// ── Refs ──────────────────────────────────────────────
const video          = ref(null)
const faces          = ref([])
const trackedFaces   = ref({})
const summaries      = ref({})
const relations      = ref({})
const name           = ref('')
const isRecording    = ref(false)
const mediaRecorder  = ref(null)
const audioChunks    = ref([])
const transcript     = ref('')
const summary        = ref('')
const currentTime    = ref('')
const cameraActive   = ref(false)
const popupDismissed = ref(false)

let isProcessing  = false
let clockInterval = null

// ── Computed ───────────────────────────────────────────
const knownCount   = computed(() => faces.value.filter(f => !isUnknown(f)).length)
const unknownCount = computed(() => faces.value.filter(f => isUnknown(f)).length)
const hasUnknown   = computed(() => unknownCount.value > 0 && !popupDismissed.value)

// ── Clock ──────────────────────────────────────────────
function updateClock() {
  currentTime.value = new Date().toLocaleTimeString('en-US', {
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

// ── Auth ───────────────────────────────────────────────
async function getToken() {
  const { data } = await supabase.auth.getSession()
  return data?.session?.access_token || null
}

// ── Lifecycle ──────────────────────────────────────────
onMounted(async () => {
  await nextTick()
  updateClock()
  clockInterval = setInterval(updateClock, 1000)
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    video.value.srcObject = stream
    video.value.onloadedmetadata = () => {
      video.value.play()
      cameraActive.value = true
      startLoop()
    }
  } catch (e) {
    console.error('Camera error:', e)
  }
})

onUnmounted(() => clearInterval(clockInterval))

// ── Frame capture ──────────────────────────────────────
function captureFrame() {
  if (!video.value || video.value.videoWidth === 0) return null
  const canvas = document.createElement('canvas')
  canvas.width  = 320
  canvas.height = 240
  canvas.getContext('2d').drawImage(video.value, 0, 0, 320, 240)
  return new Promise((resolve) =>
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.7)
  )
}

// ── Recognition ────────────────────────────────────────
async function recognizeFrame() {
  const token = await getToken()
  if (!token) return

  const blob = await captureFrame()
  if (!blob) return

  const formData = new FormData()
  formData.append('file', blob)

  const res = await axios.post(`${API}/recognize`, formData, {
    headers: { Authorization: `Bearer ${token}` },
  })

  const rect   = video.value.getBoundingClientRect()
  const scaleX = rect.width  / 320
  const scaleY = rect.height / 240

  const prevHadUnknown = faces.value.some(f => isUnknown(f))

  faces.value = res.data.map((face) => {
    const id = face.person_id || face.name

    if (trackedFaces.value[id]) {
      const prev = trackedFaces.value[id]
      face.location = face.location.map((v, i) => prev[i] * 0.7 + v * 0.3)
    }

    trackedFaces.value[id] = face.location
    
    if (face.person_id) {
      fetchSummary(face.person_id)
      fetchRelation(face.person_id) // ✅ NEW
    }

    return {
      ...face,
      location: [
        face.location[0] * scaleY,  // top
        face.location[1] * scaleX,  // right
        face.location[2] * scaleY,  // bottom
        face.location[3] * scaleX,  // left
      ],
    }
  })

  const nowHasUnknown = faces.value.some(f => isUnknown(f))
  if (!prevHadUnknown && nowHasUnknown) {
    popupDismissed.value = false
  }
}

function startLoop() {
  async function loop() {
    if (!isProcessing) {
      isProcessing = true
      await recognizeFrame()
      isProcessing = false
    }
    requestAnimationFrame(loop)
  }
  loop()
}

// ── Summaries ──────────────────────────────────────────
async function fetchSummary(person_id) {
  if (summaries.value[person_id]) return
  const token = await getToken()
  if (!token) return
  const res = await axios.get(`${API}/summary/${person_id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  summaries.value[person_id] = res.data
}

// ── Relation (NEW) ─────────────────────────────────────
async function fetchRelation(person_id) {
  if (relations.value[person_id]) return

  const token = await getToken()
  if (!token) return

  try {
    const res = await axios.get(`${API}/relation/${person_id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })

    let relation = null

    if (typeof res.data?.relation === 'string') {
      relation = res.data.relation
    } else if (res.data?.relation?.data?.length) {
      relation = res.data.relation.data[0].relationship
    }

    relations.value[person_id] = relation || 'unknown'
  } catch (e) {
    console.error('Relation fetch error:', e)
    relations.value[person_id] = 'unknown'
  }
}

// ── Style helpers ──────────────────────────────────────
function getWrapStyle(face) {
  const [top, right, bottom, left] = face.location || [0, 0, 0, 0]
  return {
    top:    `${top}px`,
    left:   `${left}px`,
    width:  `${right - left}px`,
    height: `${bottom - top}px`,
  }
}

function isUnknown(face) {
  return face.name === 'Unknown' || (face.confidence !== undefined && face.confidence < 0.6)
}

function dismissPopup() {
  popupDismissed.value = true
}

const AVATAR_COLORS = ['av-indigo', 'av-teal', 'av-rose', 'av-amber', 'av-sky']
function avatarColor(n) {
  if (!n || n === 'Unknown') return 'av-red'
  return AVATAR_COLORS[n.charCodeAt(0) % AVATAR_COLORS.length]
}

// ── Recording ──────────────────────────────────────────
async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  mediaRecorder.value = new MediaRecorder(stream)
  audioChunks.value   = []
  mediaRecorder.value.ondataavailable = (e) => audioChunks.value.push(e.data)
  mediaRecorder.value.onstop = sendAudio
  mediaRecorder.value.start()
  isRecording.value = true
}

function stopRecording() {
  mediaRecorder.value.stop()
  isRecording.value = false
}

async function sendAudio() {
  const blob  = new Blob(audioChunks.value, { type: 'audio/webm' })
  const token = await getToken()
  const formData = new FormData()
  formData.append('audio', blob)
  const knownFace = faces.value.find((f) => f.person_id)
  if (knownFace) formData.append('person_id', knownFace.person_id)
  const res = await axios.post(`${API}/process-interaction`, formData, {
    headers: { Authorization: `Bearer ${token}` },
  })
  transcript.value = res.data.transcript
  summary.value    = res.data.summary
}

// ── Add face ───────────────────────────────────────────
async function addFace() {
  if (!name.value.trim()) return
  const token = await getToken()
  if (!token) return

  const fd = new FormData()
  fd.append('name', name.value)
  const personRes = await axios.post(`${API}/person`, fd, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const personId = personRes.data.id

  const canvas = document.createElement('canvas')
  canvas.width  = video.value.videoWidth
  canvas.height = video.value.videoHeight
  canvas.getContext('2d').drawImage(video.value, 0, 0)

  canvas.toBlob(async (blob) => {
    const fd2 = new FormData()
    fd2.append('file', blob)
    fd2.append('person_id', personId)
    await axios.post(`${API}/add-face`, fd2, {
      headers: { Authorization: `Bearer ${token}` },
    })
    name.value = ''
    popupDismissed.value = true
  }, 'image/jpeg')
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;500;600;700&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Shell ──────────────────────────────────────────── */
.shell {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: #f0ede8;
  font-family: 'DM Mono', monospace;
  overflow: hidden;
}

/* ── Video ──────────────────────────────────────────── */
.video {
  position: absolute;
  top: 0;
  left: 0;
  width: calc(100% - 270px);
  height: 100%;
  object-fit: cover;
}

/* ── Face wrapper ────────────────────────────────────── */
.face-wrap {
  position: absolute;
  pointer-events: none;
}

/* ── Bounding box ────────────────────────────────────── */
.face-box {
  position: absolute;
  inset: 0;
  border: 2px solid rgba(37, 99, 235, 0.8);
  border-radius: 4px;
  background: rgba(37, 99, 235, 0.05);
}
.face-box.unknown {
  border-color: rgba(220, 38, 38, 0.8);
  background: rgba(220, 38, 38, 0.04);
}

/* ── Inline label below the box ──────────────────────── */
.face-label {
  position: absolute;
  top: calc(100% + 5px);
  left: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 4px;
  padding: 3px 9px;
  white-space: nowrap;
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.face-label.unknown {
  border-color: rgba(220, 38, 38, 0.22);
}
.face-label-name {
  font-family: 'Syne', sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #1e3a8a;
  letter-spacing: 0.02em;
}
.face-label.unknown .face-label-name { color: #991b1b; }
.face-label-conf {
  font-size: 10px;
  color: #94a3b8;
  font-family: 'DM Mono', monospace;
}
.face-label-relation {
  color: #64748b;
  font-size: 10px;
}

/* ── Status bar ──────────────────────────────────────── */
.statusbar {
  position: absolute;
  top: 0;
  left: 0;
  width: calc(100% - 270px);
  height: 38px;
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  z-index: 10;
}

.status-item {
  font-size: 10px;
  letter-spacing: 0.14em;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 7px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
  transition: background 0.3s;
}
.status-dot.live {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34,197,94,0.18);
  animation: livepulse 2s ease-in-out infinite;
}
@keyframes livepulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(34,197,94,0.18); }
  50%       { box-shadow: 0 0 0 6px rgba(34,197,94,0.06); }
}

.status-divider { color: #e2e8f0; font-size: 14px; }

/* ── Sidebar ──────────────────────────────────────────── */
.sidebar {
  position: absolute;
  top: 0;
  right: 0;
  width: 270px;
  height: 100%;
  background: #ffffff;
  border-left: 1px solid #e8e3dc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 20;
  box-shadow: -2px 0 20px rgba(0,0,0,0.05);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 15px 16px 12px;
  border-bottom: 1px solid #f1ede7;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
  transition: background 0.4s;
}
.brand-dot.active {
  background: #22c55e;
  animation: livepulse 2s ease-in-out infinite;
}

.brand-text {
  font-family: 'Syne', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0.14em;
}

.sidebar-time {
  font-size: 10px;
  color: #94a3b8;
  letter-spacing: 0.06em;
}

/* ── Stats strip ─────────────────────────────────────── */
.stats-strip {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f1ede7;
  background: #faf8f5;
}

.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-num {
  font-family: 'Syne', sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1;
}

.stat-label {
  font-size: 8px;
  letter-spacing: 0.14em;
  color: #94a3b8;
}

.stat-div {
  width: 1px;
  height: 28px;
  background: #e8e3dc;
}

/* ── Section label ───────────────────────────────────── */
.sidebar-section-label {
  font-size: 8px;
  letter-spacing: 0.18em;
  color: #94a3b8;
  padding: 12px 16px 6px;
}

/* ── Face list ───────────────────────────────────────── */
.face-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  scrollbar-width: thin;
  scrollbar-color: #e8e3dc transparent;
}

/* ── Face card ───────────────────────────────────────── */
.face-card {
  background: #faf8f5;
  border: 1px solid #e8e3dc;
  border-radius: 10px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: box-shadow 0.2s;
}
.face-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.face-card.unknown {
  border-color: rgba(220,38,38,0.18);
  background: #fff8f8;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 9px;
}

/* ── Avatar ──────────────────────────────────────────── */
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Syne', sans-serif;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.av-indigo { background: #ede9fe; color: #4338ca; }
.av-teal   { background: #ccfbf1; color: #0d9488; }
.av-rose   { background: #ffe4e6; color: #e11d48; }
.av-amber  { background: #fef3c7; color: #d97706; }
.av-sky    { background: #e0f2fe; color: #0284c7; }
.av-red    { background: #fee2e2; color: #dc2626; }

.card-meta { flex: 1; min-width: 0; }
.card-name {
  font-family: 'Syne', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-conf { font-size: 10px; color: #94a3b8; margin-top: 2px; }

/* ── Badge ───────────────────────────────────────────── */
.card-badge {
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 2px 7px;
  border-radius: 3px;
  flex-shrink: 0;
}
.badge-ok   { background: #dcfce7; color: #15803d; }
.badge-warn { background: #fee2e2; color: #dc2626; }

/* ── Card summary ────────────────────────────────────── */
.card-summary {
  border-top: 1px solid #f1ede7;
  padding-top: 7px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.summary-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.summary-tag {
  font-size: 8px;
  letter-spacing: 0.1em;
  color: #cbd5e1;
  flex-shrink: 0;
  padding-top: 1px;
  min-width: 28px;
}
.summary-text { font-size: 10px; color: #64748b; line-height: 1.5; }

/* ── Empty state ─────────────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
}
.empty-icon { font-size: 26px; color: #e2e8f0; }
.empty-text { font-size: 11px; color: #cbd5e1; letter-spacing: 0.08em; }

/* ── Card list transitions ───────────────────────────── */
.card-enter-active { transition: all 0.22s ease; }
.card-leave-active { transition: all 0.18s ease; }
.card-enter-from   { opacity: 0; transform: translateX(10px); }
.card-leave-to     { opacity: 0; transform: translateX(10px); }

/* ── Mic section ─────────────────────────────────────── */
.mic-section {
  border-top: 1px solid #f1ede7;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #faf8f5;
}

.mic-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  background: #fff;
  border: 1px solid #e2ddd6;
  border-radius: 8px;
  color: #475569;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.05em;
  padding: 9px 14px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.mic-btn:hover { border-color: #c4bdb4; background: #f5f2ee; }
.mic-btn.recording {
  background: #fff5f5;
  border-color: rgba(220,38,38,0.3);
  color: #dc2626;
  animation: rec-pulse 1.5s ease-in-out infinite;
}
@keyframes rec-pulse {
  0%, 100% { border-color: rgba(220,38,38,0.3); }
  50%       { border-color: rgba(220,38,38,0.1); }
}
.mic-icon { font-size: 13px; }

.log-block {
  background: #fff;
  border: 1px solid #ece7e0;
  border-radius: 6px;
  padding: 8px 10px;
}
.log-tag {
  font-size: 8px;
  letter-spacing: 0.14em;
  color: #94a3b8;
  margin-bottom: 4px;
}
.log-text { font-size: 10px; color: #475569; line-height: 1.6; }

/* ── ADD FACE POPUP — bottom-left, floating ──────────── */
.add-popup {
  position: absolute;
  bottom: 24px;
  left: 24px;
  width: 308px;
  background: #ffffff;
  border: 1px solid #e2ddd6;
  border-radius: 16px;
  padding: 18px;
  box-shadow:
    0 4px 6px rgba(0,0,0,0.04),
    0 12px 40px rgba(0,0,0,0.10);
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.add-popup-header {
  display: flex;
  align-items: center;
  gap: 9px;
}

.add-popup-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dc2626;
  flex-shrink: 0;
  animation: livepulse 1.4s ease-in-out infinite;
}

.add-popup-title {
  font-family: 'Syne', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  flex: 1;
}

.add-popup-close {
  background: none;
  border: none;
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
  padding: 3px 5px;
  border-radius: 4px;
  line-height: 1;
  transition: color 0.15s, background 0.15s;
}
.add-popup-close:hover { color: #475569; background: #f1ede7; }

.add-popup-hint {
  font-size: 11px;
  color: #64748b;
  line-height: 1.55;
}

.add-popup-row {
  display: flex;
  gap: 8px;
}

.add-input {
  flex: 1;
  background: #faf8f5;
  border: 1px solid #e2ddd6;
  border-radius: 8px;
  color: #0f172a;
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  padding: 9px 12px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.add-input::placeholder { color: #cbd5e1; }
.add-input:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(147,197,253,0.25);
}

.add-btn {
  background: #0f172a;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  padding: 9px 16px;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
  white-space: nowrap;
}
.add-btn:hover { background: #1e293b; }
.add-btn:active { transform: scale(0.97); }

/* ── Popup transition ────────────────────────────────── */
.popup-enter-active { transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.popup-leave-active { transition: all 0.2s ease; }
.popup-enter-from   { opacity: 0; transform: translateY(20px) scale(0.95); }
.popup-leave-to     { opacity: 0; transform: translateY(10px) scale(0.97); }
</style>