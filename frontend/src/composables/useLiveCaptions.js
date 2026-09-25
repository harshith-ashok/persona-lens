import { ref } from 'vue'
import { supabase } from '@/lib/supabase'
import { API_URL } from '@/lib/api'

const TARGET_RATE = 16000
const KEEP_LINES = 3

// Downsamples whatever the mic gives us to 16 kHz mono PCM16 in 100 ms frames.
const WORKLET = `
class PCM16Downsampler extends AudioWorkletProcessor {
  constructor() {
    super()
    this.ratio = sampleRate / ${TARGET_RATE}
    this.phase = 0; this.sum = 0; this.n = 0
    this.out = new Int16Array(${TARGET_RATE / 10}); this.k = 0
  }
  process(inputs) {
    const ch = inputs[0][0]
    if (!ch) return true
    for (let i = 0; i < ch.length; i++) {
      this.sum += ch[i]; this.n++; this.phase += 1
      if (this.phase >= this.ratio) {
        this.phase -= this.ratio
        const v = Math.max(-1, Math.min(1, this.sum / this.n)); this.sum = 0; this.n = 0
        this.out[this.k++] = v < 0 ? v * 0x8000 : v * 0x7fff
        if (this.k === this.out.length) { this.port.postMessage(this.out.slice(0)); this.k = 0 }
      }
    }
    return true
  }
}
registerProcessor('pcm16-downsampler', PCM16Downsampler)
`

/**
 * Streams the mic to /ws/live and exposes rolling captions.
 * `lines` holds the last few finished utterances, `partial` the one in progress.
 */
export function useLiveCaptions() {
  const lines = ref([])
  const partial = ref('')
  const failed = ref(false)

  let ws = null
  let ctx = null
  let nextId = 1

  // `options.purpose = 'enroll'` = captions only, for voice setup (no session, nothing is kept)
  async function start(stream, sessionId, options = {}) {
    stop()
    lines.value = []
    partial.value = ''
    failed.value = false

    try {
      const { data } = await supabase.auth.getSession()
      const token = data?.session?.access_token
      if (!token) throw new Error('not signed in')

      ws = new WebSocket(API_URL.replace(/^http/, 'ws') + '/ws/live')
      ws.binaryType = 'arraybuffer'
      ws.onmessage = (e) => onEvent(JSON.parse(e.data))
      ws.onerror = () => (failed.value = true)

      await new Promise((resolve, reject) => {
        ws.onopen = () => {
          ws.send(JSON.stringify({ type: 'start', token, session_id: sessionId, purpose: options.purpose }))
          resolve()
        }
        ws.onclose = reject
      })

      ctx = new AudioContext()
      const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }))
      await ctx.audioWorklet.addModule(url)
      URL.revokeObjectURL(url)

      const node = new AudioWorkletNode(ctx, 'pcm16-downsampler')
      node.port.onmessage = (e) => {
        if (ws?.readyState === WebSocket.OPEN) ws.send(e.data.buffer)
      }
      const mute = ctx.createGain()
      mute.gain.value = 0 // the worklet only runs while connected to the destination
      ctx.createMediaStreamSource(new MediaStream(stream.getAudioTracks())).connect(node)
      node.connect(mute).connect(ctx.destination)
    } catch (e) {
      console.warn('Live captions unavailable:', e)
      failed.value = true
      stop()
    }
  }

  function onEvent(e) {
    if (e.type === 'partial') {
      partial.value = e.text
    } else if (e.type === 'final') {
      partial.value = ''
      lines.value = [...lines.value, { id: nextId++, speaker: e.speaker, person_id: e.person_id ?? null, text: e.text }].slice(-KEEP_LINES)
    } else if (e.type === 'error') {
      console.warn('Live captions error:', e.message)
      failed.value = true
    }
  }

  function stop() {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'stop' }))
    ws?.close()
    ws = null
    ctx?.close().catch(() => {})
    ctx = null
  }

  return { lines, partial, failed, start, stop }
}
