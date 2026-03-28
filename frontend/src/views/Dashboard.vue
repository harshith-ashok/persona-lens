<template>
  <div class="container">
    <video ref="video" autoplay playsinline class="video"></video>

    <!-- FACE POPUPS -->
    <div v-for="(face, i) in faces" :key="i" class="popup" :style="getStyle(face)">
      <div class="popup-name">{{ face.name }}</div>

      <div v-if="face.confidence" class="popup-confidence">
        {{ Math.round(face.confidence * 100) }}%
      </div>

      <div v-if="face.person_id && summaries[face.person_id]" class="summary">
        <span v-if="summaries[face.person_id].first_summary">
          First: {{ summaries[face.person_id].first_summary }}
        </span>

        <span v-if="summaries[face.person_id].last_summary">
          Last: {{ summaries[face.person_id].last_summary }}
        </span>
      </div>
    </div>

    <div class="mic-panel">
      <button v-if="!isRecording" @click="startRecording">Start Recording</button>

      <button v-else @click="stopRecording">⏺ Stop</button>

      <p v-if="transcript">TR: {{ transcript }}</p>
      <p v-if="summary">SUM: {{ summary }}</p>
    </div>

    <!-- ADD FACE PANEL -->

    <div v-if="shouldShowAdd" class="panel">
      <h3 style="color: white;">New Face Detected</h3>

      <input v-model="name" placeholder="Enter name" />

      <button @click="addFace">Add Face</button>

      <p class="hint">
        {{ targetFace?.name }}
        ({{ Math.round((targetFace?.confidence || 0) * 100) }}%)
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import axios from 'axios'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://pffshbkpvbxakvblflzw.supabase.co'
const SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZnNoYmtwdmJ4YWt2YmxmbHp3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MDUyMTIsImV4cCI6MjA5MDE4MTIxMn0.4rUiGa7rBz7dwloK6nXHqKx2_2nJj1lQpGM7PZQXMLY'
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

const API = 'http://localhost:8120'

const video = ref(null)
const faces = ref([])
const trackedFaces = ref({})
const summaries = ref({})
const name = ref('')
const isRecording = ref(false)
const mediaRecorder = ref(null)
const audioChunks = ref([])

const transcript = ref('')
const summary = ref('')

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

  mediaRecorder.value = new MediaRecorder(stream)
  audioChunks.value = []

  mediaRecorder.value.ondataavailable = (e) => {
    audioChunks.value.push(e.data)
  }

  mediaRecorder.value.onstop = sendAudio

  mediaRecorder.value.start()
  isRecording.value = true
}
function stopRecording() {
  mediaRecorder.value.stop()
  isRecording.value = false
}
async function sendAudio() {
  const blob = new Blob(audioChunks.value, { type: 'audio/webm' })

  const token = await getToken()

  const formData = new FormData()
  formData.append('audio', blob)

  // attach current detected person if exists
  const knownFace = faces.value.find((f) => f.person_id)
  if (knownFace) {
    formData.append('person_id', knownFace.person_id)
  }

  const res = await axios.post(`${API}/process-interaction`, formData, {
    headers: { Authorization: `Bearer ${token}` },
  })

  transcript.value = res.data.transcript
  summary.value = res.data.summary
}

let isProcessing = false

// 🔐 Token
async function getToken() {
  const { data } = await supabase.auth.getSession()
  return data?.session?.access_token || null
}

// 🎯 Detect if we should show add UI
const shouldShowAdd = computed(() => {
  return faces.value.some(
    (face) => face.name === 'Unknown' || (face.confidence !== undefined && face.confidence < 0.6),
  )
})

const targetFace = computed(() => {
  return faces.value.find(
    (face) => face.name === 'Unknown' || (face.confidence !== undefined && face.confidence < 0.6),
  )
})

// 🎥 INIT CAMERA
onMounted(async () => {
  await nextTick()

  const stream = await navigator.mediaDevices.getUserMedia({ video: true })
  video.value.srcObject = stream

  video.value.onloadedmetadata = () => {
    video.value.play()
    startLoop()
  }
})

// 📸 Capture
function captureFrame() {
  if (!video.value || video.value.videoWidth === 0) return null

  const canvas = document.createElement('canvas')
  canvas.width = 320
  canvas.height = 240

  const ctx = canvas.getContext('2d')
  ctx.drawImage(video.value, 0, 0, 320, 240)

  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.7))
}

// 🧠 Fetch summaries
async function fetchSummary(person_id) {
  if (summaries.value[person_id]) return

  const token = await getToken()
  if (!token) return

  const res = await axios.get(`${API}/summary/${person_id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })

  summaries.value[person_id] = res.data
}

// 🔁 Recognize
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

  const scaleX = video.value.videoWidth / 320
  const scaleY = video.value.videoHeight / 240

  faces.value = res.data.map((face) => {
    const id = face.person_id || face.name

    if (trackedFaces.value[id]) {
      const prev = trackedFaces.value[id]
      face.location = face.location.map((v, i) => prev[i] * 0.7 + v * 0.3)
    }

    trackedFaces.value[id] = face.location

    if (face.person_id) fetchSummary(face.person_id)

    return {
      ...face,
      location: [
        face.location[0] * scaleY,
        face.location[1] * scaleX,
        face.location[2] * scaleY,
        face.location[3] * scaleX,
      ],
    }
  })
}

// 🔁 Loop
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

// 📍 Position popup (bottom-right of face)
function getStyle(face) {
  const [top, right, bottom, left] = face.location || [0, 0, 0, 0]

  return {
    top: `${bottom + 8}px`,
    left: `${right + 8}px`,
  }
}

// ➕ Add face
async function addFace() {
  if (!name.value.trim()) return

  const token = await getToken()
  if (!token) return

  const formData = new FormData()
  formData.append('name', name.value)

  const personRes = await axios.post(`${API}/person`, formData, {
    headers: { Authorization: `Bearer ${token}` },
  })

  const personId = personRes.data.id

  const canvas = document.createElement('canvas')
  canvas.width = video.value.videoWidth
  canvas.height = video.value.videoHeight

  const ctx = canvas.getContext('2d')
  ctx.drawImage(video.value, 0, 0)

  canvas.toBlob(async (blob) => {
    const fd = new FormData()
    fd.append('file', blob)
    fd.append('person_id', personId)

    await axios.post(`${API}/add-face`, fd, {
      headers: { Authorization: `Bearer ${token}` },
    })

    name.value = ''
  }, 'image/jpeg')
}
</script>

<style scoped>
input {
  width: 100%;
  padding: 13px 42px 13px 42px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid #1e1e1e;
  border-radius: 10px;
  color: #f0f0f0;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.25s, box-shadow 0.25s, background 0.25s;
  box-sizing: border-box;
}
.input-wrap input::placeholder { color: #333; }
.input-wrap input:focus {
  border-color: #6c63ff;
  background: rgba(108, 99, 255, 0.05);
  box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.12);
}

.container {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: #000;
  font-family: monospace !important;
}

.video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* POPUP */
.popup {
  position: absolute;
  min-width: 180px;
  max-width: 260px;

  background: rgba(20, 20, 20, 0.75);
  backdrop-filter: blur(12px);

  border: 1px solid rgba(108, 99, 255, 0.08);
  border-radius: 12px;

  padding: 10px 12px;
  color: #fff;
  font-size: 13px;

  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.popup-name {
  font-weight: 600;
  color: #9d97ff;
}

.popup-confidence {
  font-size: 11px;
  color: #9d97ff;
}

/* SUMMARY */
.summary {
  margin-top: 6px;
  font-size: 11px;
  color: #ccc;
}

.summary span {
  display: block;
  margin-top: 3px;
}

/* PANEL */
.panel {
  position: absolute;
  bottom: 20px;
  left: 20px;

  background: rgba(0, 0, 0, 0.8);
  padding: 14px;
  border-radius: 12px;
}

.panel input {
  padding: 6px;
  margin-top: 8px;
  width: 100%;
}

.mic-panel {
  position: absolute;
  top: 20px;
  left: 20px;

  background: rgba(0, 0, 0, 0.8);
  padding: 11px;
  border-radius: 12px;
  color: white;
  max-width: 300px;
}

.mic-panel button {
  padding: 8px 12px;
  margin-bottom: 8px;
  background: #9d97ff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.panel button {
  margin-top: 8px;
  padding: 8px;
  background: #9d97ff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.hint {
  font-size: 12px;
  margin-top: 6px;
  color: #aaa;
}
</style>
