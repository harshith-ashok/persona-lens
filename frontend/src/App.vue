<template>
  <div class="container">
    <video ref="video" autoplay playsinline class="video"></video>
    <canvas ref="canvas" class="overlay"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const video = ref(null)
const canvas = ref(null)

let isProcessing = false

onMounted(async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ video: true })
  video.value.srcObject = stream

  video.value.onloadedmetadata = () => {
    canvas.value.width = video.value.videoWidth
    canvas.value.height = video.value.videoHeight

    startRecognition()
  }
})

function captureFrame() {
  const tempCanvas = document.createElement('canvas')
  tempCanvas.width = video.value.videoWidth
  tempCanvas.height = video.value.videoHeight

  const ctx = tempCanvas.getContext('2d')
  ctx.drawImage(video.value, 0, 0)

  return new Promise((resolve) => {
    tempCanvas.toBlob((blob) => resolve(blob), 'image/jpeg')
  })
}

async function startRecognition() {
  setInterval(async () => {
    if (isProcessing) return
    isProcessing = true

    try {
      const blob = await captureFrame()

      const formData = new FormData()
      formData.append('file', blob)

      const res = await axios.post('http://localhost:8120/recognize', formData)

      drawOverlay(res.data)
    } catch (err) {
      console.error(err)
    }

    isProcessing = false
  }, 1) // every 1 second
}

function drawOverlay(faces) {
  const ctx = canvas.value.getContext('2d')

  ctx.clearRect(0, 0, canvas.value.width, canvas.value.height)
  ctx.drawImage(video.value, 0, 0)

  faces.forEach((face) => {
    const [top, right, bottom, left] = face.location

    const width = right - left
    const height = bottom - top

    // 🔴 Box
    // ctx.strokeStyle = '#00FFAA'
    // ctx.lineWidth = 3
    // ctx.strokeRect(left, top, width, height)

    // 🟢 Floating label
    const label = face.name
    ctx.font = '18px Arial'
    const textWidth = ctx.measureText(label).width

    const padding = 8
    const boxX = left
    const boxY = top - 30

    // Background bubble
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
    ctx.fillRect(boxX, boxY, textWidth + padding * 2, 25)

    // Text
    ctx.fillStyle = '#00FFAA'
    ctx.fillText(label, boxX + padding, boxY + 18)
  })
}
</script>

<style>
.container {
  /* position: relative;
  width: ;
  height: 1000px; */
  overflow: hidden;
}

.video {
  position: absolute;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.overlay {
  position: absolute;
  width: 100%;
  height: 100%;
}
</style>
