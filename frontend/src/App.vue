<template>
  <div class="container">
    <video ref="video" autoplay playsinline class="video"></video>

    <!-- POPUPS -->
    <div v-for="(face, i) in faces" :key="i" class="popup" :style="getStyle(face)">
      {{ face.name }}
    </div>

    <!-- PANEL -->
    <div class="panel">
      <input v-model="name" placeholder="Enter name" />
      <button @click="addFace">Add Face</button>
    </div>
    <div class="panel-r popup">
      <p>Harshith</p>
      <p>Likes Sports and girls</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const video = ref(null)
const faces = ref([])
const name = ref('')

let isProcessing = false

onMounted(async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ video: true })
  video.value.srcObject = stream

  startLoop()
})

function captureFrame() {
  const canvas = document.createElement('canvas')
  canvas.width = 320
  canvas.height = 240

  const ctx = canvas.getContext('2d')
  ctx.drawImage(video.value, 0, 0, 320, 240)

  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.7)
  })
}

async function startLoop() {
  setInterval(async () => {
    if (isProcessing) return
    isProcessing = true

    try {
      const blob = await captureFrame()

      const formData = new FormData()
      formData.append('file', blob)

      const res = await axios.post('http://localhost:8120/recognize', formData)

      // 🔥 scale to screen
      const scaleX = video.value.videoWidth / 320
      const scaleY = video.value.videoHeight / 240

      faces.value = res.data.map((face) => ({
        name: face.name,
        location: [
          face.location[0] * scaleY,
          face.location[1] * scaleX,
          face.location[2] * scaleY,
          face.location[3] * scaleX,
        ],
      }))
    } catch (err) {
      console.error(err)
    }

    isProcessing = false
  }, 1000)
}

function getStyle(face) {
  const [top, , , left] = face.location

  return {
    top: `${top}px`,
    left: `${left}px`,
  }
}

async function addFace() {
  if (!name.value) {
    alert('Enter name')
    return
  }

  const canvas = document.createElement('canvas')
  canvas.width = video.value.videoWidth
  canvas.height = video.value.videoHeight

  const ctx = canvas.getContext('2d')
  ctx.drawImage(video.value, 0, 0)

  canvas.toBlob(async (blob) => {
    const formData = new FormData()
    formData.append('file', blob)
    formData.append('name', name.value)

    const res = await axios.post('http://localhost:8120/add-face', formData)
    alert(res.data.message)
  }, 'image/jpeg')
}
</script>

<style>
.container {
  position: relative;
  width: 100vw;
  height: 100vh;
}

.video {
  position: absolute;
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
  font-size: 14px;
}

.panel {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: rgba(0, 0, 0, 0.7);
  padding: 10px;
  border-radius: 10px;
}
.panel-r {
  position: absolute;
  bottom: 20px;
  right: 20px;
  background: rgba(0, 0, 0, 0.7);
  padding: 40px;
  border-radius: 10px;
}
</style>
