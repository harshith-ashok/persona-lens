import { ref } from 'vue'

const CHECK_MS = 200
const SOUND_RMS = 0.015 // time-domain RMS above this counts as sound

/**
 * Watches a MediaStream and calls onSilence() after `silenceMs` of continuous silence.
 * `silentFor` (seconds) is reactive so the UI can show a countdown.
 */
export function useSilenceDetector({ silenceMs = 15000, onSilence }) {
  const silentFor = ref(0)

  let ctx = null
  let timer = null
  let lastSound = 0

  function start(stream) {
    stop()
    ctx = new (window.AudioContext || window.webkitAudioContext)()
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 1024
    ctx.createMediaStreamSource(stream).connect(analyser)
    const buf = new Float32Array(analyser.fftSize)

    lastSound = performance.now()
    timer = setInterval(() => {
      analyser.getFloatTimeDomainData(buf)
      let sum = 0
      for (const v of buf) sum += v * v
      const rms = Math.sqrt(sum / buf.length)

      const now = performance.now()
      if (rms > SOUND_RMS) lastSound = now
      const silent = now - lastSound
      silentFor.value = Math.floor(silent / 1000)

      if (silent >= silenceMs) {
        stop()
        onSilence?.()
      }
    }, CHECK_MS)
  }

  function stop() {
    clearInterval(timer)
    timer = null
    silentFor.value = 0
    if (ctx) {
      ctx.close().catch(() => {})
      ctx = null
    }
  }

  return { silentFor, start, stop }
}
