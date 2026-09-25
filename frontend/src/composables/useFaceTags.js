import { ref } from 'vue'
import { api } from '@/lib/api'

const FRAME_W = 320
const FRAME_H = 240
const MATCH_MIN = 0.6
const LOOP_GAP_MS = 150
const SMOOTHING = 0.5     // weight of the newest box (higher = snappier, lower = steadier)
const DROPOUT_MS = 700    // keep tags this long when a frame briefly finds no face

/** Runs /recognize against a <video> and exposes AR tags positioned in viewfinder pixels. */
export function useFaceTags(videoRef) {
  const tags = ref([])
  const scanning = ref(false)
  const recognized = ref(null) // { person_id, name } of the best match seen this run
  const sawUnknown = ref(false) // an unmatched face was in frame at some point this run
  const viewport = ref({ w: 0, h: 0 }) // bumped on resize so tag styles recompute

  let running = false
  let lastFaceAt = 0
  const smoothed = {}

  function measure() {
    const v = videoRef.value
    if (v) viewport.value = { w: v.clientWidth, h: v.clientHeight }
  }

  function grabFrame() {
    const v = videoRef.value
    if (!v || !v.videoWidth) return Promise.resolve(null)
    const c = document.createElement('canvas')
    c.width = FRAME_W
    c.height = FRAME_H
    c.getContext('2d').drawImage(v, 0, 0, FRAME_W, FRAME_H)
    return new Promise((resolve) => c.toBlob(resolve, 'image/jpeg', 0.7))
  }

  /**
   * Frame coords -> viewfinder pixels. The video is object-fit: cover and mirrored, and the frame
   * sent for recognition is the whole video squeezed to 320x240, so coords are fractions of it.
   */
  function styleFor(tag) {
    const v = videoRef.value
    const { w: W, h: H } = viewport.value
    if (!v || !v.videoWidth || !W) return { display: 'none' }

    const [top, right, bottom, left] = tag.loc
    const scale = Math.max(W / v.videoWidth, H / v.videoHeight)
    const dw = v.videoWidth * scale, dh = v.videoHeight * scale
    const ox = (W - dw) / 2, oy = (H - dh) / 2
    const x = (px) => (px / FRAME_W) * dw + ox
    const y = (px) => (px / FRAME_H) * dh + oy
    const l = W - x(right), r = W - x(left)

    return { left: `${l}px`, top: `${y(top)}px`, width: `${r - l}px`, height: `${y(bottom) - y(top)}px` }
  }

  // labels sit to the right of the box; flip them to the left near the right edge
  function flips(tag) {
    const { w: W } = viewport.value
    const s = styleFor(tag)
    return !!W && parseFloat(s.left) + parseFloat(s.width) > W - 200
  }

  async function step() {
    const blob = await grabFrame()
    if (!blob) return
    const fd = new FormData()
    fd.append('file', blob)
    const { data } = await api.post('/recognize', fd)
    if (!running) return

    if (!data.length) {
      if (Date.now() - lastFaceAt > DROPOUT_MS) tags.value = []
      return
    }
    lastFaceAt = Date.now()

    const live = new Set()
    tags.value = data.map((f) => {
      const key = f.track_id
      live.add(key)
      const prev = smoothed[key]
      const loc = prev ? f.location.map((n, i) => prev[i] * (1 - SMOOTHING) + n * SMOOTHING) : f.location
      smoothed[key] = loc

      const unknown = f.name === 'Unknown' || f.confidence < MATCH_MIN
      if (unknown && !f.identifying) sawUnknown.value = true
      if (!unknown && f.person_id && !f.is_self) recognized.value = { person_id: f.person_id, name: f.name }
      return { key, name: f.name, person_id: f.person_id, is_self: !!f.is_self, confidence: f.confidence, unknown, identifying: f.identifying, loc }
    })
    for (const k of Object.keys(smoothed)) if (!live.has(Number(k))) delete smoothed[k]
    scanning.value = false
  }

  async function loop() {
    while (running) {
      try { await step() } catch (e) { console.error('recognize failed', e) }
      await new Promise((r) => setTimeout(r, LOOP_GAP_MS))
    }
  }

  function start() {
    if (running) return
    running = true
    scanning.value = true
    recognized.value = null
    sawUnknown.value = false
    lastFaceAt = 0
    measure()
    window.addEventListener('resize', measure)
    loop()
  }

  function stop() {
    running = false
    scanning.value = false
    tags.value = []
    window.removeEventListener('resize', measure)
    for (const k of Object.keys(smoothed)) delete smoothed[k]
  }

  /** Full-resolution still, used as the enrollment photo for a newly named person. */
  function captureFull() {
    const v = videoRef.value
    if (!v || !v.videoWidth) return Promise.resolve(null)
    const c = document.createElement('canvas')
    c.width = v.videoWidth
    c.height = v.videoHeight
    c.getContext('2d').drawImage(v, 0, 0)
    return new Promise((resolve) => c.toBlob(resolve, 'image/jpeg', 0.9))
  }

  return { tags, scanning, recognized, sawUnknown, styleFor, flips, start, stop, captureFull }
}
