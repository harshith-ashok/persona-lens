<template>
  <div class="face-enroll">
    <div class="face-stage">
      <video v-show="streaming" ref="video" autoplay playsinline muted class="face-video" />
      <img v-if="!streaming && photo" :src="`data:image/jpeg;base64,${photo}`" alt="Your face" class="face-photo" />
      <div v-if="!streaming && !photo" class="face-empty">No face photo yet</div>
    </div>

    <div class="row">
      <template v-if="!streaming">
        <button class="btn" type="button" :disabled="busy" @click="openCamera">{{ photo ? 'Retake with camera' : 'Use camera' }}</button>
        <button class="btn ghost" type="button" :disabled="busy" @click="$refs.file.click()">Choose a photo</button>
        <input ref="file" type="file" accept="image/*" hidden @change="onFile" />
      </template>
      <template v-else>
        <button class="btn primary" type="button" :disabled="busy" @click="capture">Capture</button>
        <button class="btn ghost" type="button" :disabled="busy" @click="closeCamera">Cancel</button>
      </template>
    </div>
    <div class="enroll-status" :class="{ ok: !!photo && !error }">{{ error || (busy ? 'Saving…' : hint) }}</div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { api } from '@/lib/api'
import { toast } from '@/composables/useToast'

const props = defineProps({
  photo: { type: String, default: '' }, // base64 JPEG of the current face photo (from GET /host)
})
const emit = defineEmits(['saved'])

const video = ref(null)
const streaming = ref(false)
const busy = ref(false)
const error = ref('')
let stream = null

const hint = computed(() => (props.photo ? 'Saved to your account. Every device you sign in on can use it.' : 'Look at the camera in good light.'))

async function openCamera() {
  error.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
    streaming.value = true
    await nextTick()
    video.value.srcObject = stream
  } catch (e) {
    error.value = 'Camera access was blocked.'
  }
}

function closeCamera() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  streaming.value = false
}

async function upload(blob) {
  busy.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', blob, 'face.jpg')
    fd.append('replace', 'true') // a new photo replaces the old ones
    await api.post('/host/face', fd)
    toast('Face saved')
    emit('saved')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Could not save that photo.'
  } finally {
    busy.value = false
  }
}

function capture() {
  const v = video.value
  const c = document.createElement('canvas')
  c.width = v.videoWidth
  c.height = v.videoHeight
  c.getContext('2d').drawImage(v, 0, 0)
  c.toBlob(async (blob) => {
    closeCamera()
    if (blob) await upload(blob)
  }, 'image/jpeg', 0.9)
}

function onFile(e) {
  const f = e.target.files?.[0]
  e.target.value = ''
  if (f) upload(f)
}

onUnmounted(closeCamera)
</script>

<style scoped>
.face-stage { height: 200px; border: 1px solid var(--line); border-radius: 5px; background: rgba(255, 255, 255, 0.02); overflow: hidden; display: grid; place-items: center; margin-bottom: 10px; }
.face-video { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
.face-photo { height: 100%; max-width: 100%; object-fit: contain; }
.face-empty { color: var(--ink-dim); font-size: 13px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
