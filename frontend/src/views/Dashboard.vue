<template>
  <div class="container">
    <video ref="video" autoplay playsinline class="video"></video>

    <!-- POPUPS -->
    <div
      v-for="(face, i) in faces"
      :key="i"
      class="popup"
      :style="getStyle(face)"
    >
      <span class="popup-name">{{ face.name }}</span>
      <span v-if="face.confidence" class="popup-confidence">
        {{ Math.round(face.confidence * 100) }}%
      </span>
    </div>

    <!-- ADD FACE PANEL -->
    <div class="panel">
      <input v-model="name" placeholder="Enter name" />
      <button @click="addFace">Add Face</button>
      <p>{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import axios from 'axios'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://pffshbkpvbxakvblflzw.supabase.co'
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZnNoYmtwdmJ4YWt2YmxmbHp3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MDUyMTIsImV4cCI6MjA5MDE4MTIxMn0.4rUiGa7rBz7dwloK6nXHqKx2_2nJj1lQpGM7PZQXMLY'
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

const API = 'http://localhost:8120'

const video = ref(null)
const faces = ref([])
const trackedFaces = ref({})
const name = ref('')
const status = ref('')

let isProcessing = false

// ✅ Get token safely
async function getToken() {
  const { data, error } = await supabase.auth.getSession()

  if (error || !data?.session) {
    console.warn("No session")
    return null
  }

  return data.session.access_token
}

// 🎥 INIT CAMERA
onMounted(async () => {
  await nextTick()

  if (!video.value) {
    console.error("Video ref missing")
    return
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    video.value.srcObject = stream

    video.value.onloadedmetadata = () => {
      video.value.play()
      startLoop()
    }
  } catch (err) {
    console.error("Camera error:", err)
  }
})

// 📸 CAPTURE FRAME
function captureFrame() {
  if (!video.value || video.value.videoWidth === 0) return null

  const canvas = document.createElement('canvas')
  canvas.width = 320
  canvas.height = 240

  const ctx = canvas.getContext('2d')
  ctx.drawImage(video.value, 0, 0, 320, 240)

  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.7)
  })
}

// 🔁 RECOGNITION LOOP
async function recognizeFrame() {
  const token = await getToken()
  if (!token) return

  const blob = await captureFrame()
  if (!blob) return

  const formData = new FormData()
  formData.append('file', blob)

  const res = await axios.post(`${API}/recognize`, formData, {
    headers: { Authorization: `Bearer ${token}` }
  })

  const scaleX = video.value.videoWidth / 320
  const scaleY = video.value.videoHeight / 240

  faces.value = res.data.map((face) => {
    const id = face.person_id || face.name

    if (trackedFaces.value[id]) {
      const prev = trackedFaces.value[id]
      face.location = face.location.map((v, i) =>
        prev[i] * 0.7 + v * 0.3
      )
    }

    trackedFaces.value[id] = face.location

    return {
      ...face,
      location: [
        face.location[0] * scaleY,
        face.location[1] * scaleX,
        face.location[2] * scaleY,
        face.location[3] * scaleX,
      ]
    }
  })
}

// 🔁 LOOP
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

// 📍 POPUP POSITION
function getStyle(face) {
  const [top, , , left] = face.location || [0, 0, 0, 0]
  return {
    top: `${top}px`,
    left: `${left}px`,
  }
}

// ➕ ADD FACE
async function addFace() {
  if (!name.value.trim()) {
    status.value = "Enter name"
    return
  }

  const token = await getToken()
  if (!token) return

  try {
    // create person
    const formData = new FormData()
    formData.append('name', name.value)

    const personRes = await axios.post(`${API}/person`, formData, {
      headers: { Authorization: `Bearer ${token}` }
    })

    const personId = personRes.data.id

    // capture image
    const canvas = document.createElement('canvas')
    canvas.width = video.value.videoWidth
    canvas.height = video.value.videoHeight

    const ctx = canvas.getContext('2d')
    ctx.drawImage(video.value, 0, 0)

    canvas.toBlob(async (blob) => {
      const fd = new FormData()
      fd.append('file', blob)
      fd.append('person_id', personId)

      const res = await axios.post(`${API}/add-face`, fd, {
        headers: { Authorization: `Bearer ${token}` }
      })

      status.value = res.data.message
      name.value = ''
    }, 'image/jpeg')

  } catch (err) {
    console.error(err)
    status.value = "Error adding face"
  }
}
</script>

<style scoped>
.container {
  position: relative;
  width: 100vw;
  height: 100vh;
}

.video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.popup {
  position: absolute;
  background: rgba(0, 0, 0, 0.7);
  color: #00ffaa;
  padding: 6px 10px;
  border-radius: 8px;
}

.panel {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: rgba(0, 0, 0, 0.7);
  padding: 10px;
}
</style>