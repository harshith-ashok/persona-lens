import { ref, shallowRef } from 'vue'

/**
 * Records mic audio. Pass an existing MediaStream to record its audio tracks (the caller keeps
 * ownership of the stream); otherwise a mic stream is opened and closed here.
 * `analyser` is set while recording so the UI can draw a waveform.
 */
export function useAudioRecorder() {
  const isRecording = ref(false)
  const seconds = ref(0)
  const analyser = shallowRef(null)

  let stream = null
  let ownsStream = false
  let recorder = null
  let chunks = []
  let tick = null
  let ctx = null

  async function start(existing = null) {
    ownsStream = !existing
    stream = existing || (await navigator.mediaDevices.getUserMedia({ audio: true }))
    const audioOnly = new MediaStream(stream.getAudioTracks())

    chunks = []
    recorder = new MediaRecorder(audioOnly)
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    recorder.start()

    ctx = new (window.AudioContext || window.webkitAudioContext)()
    const node = ctx.createAnalyser()
    node.fftSize = 256
    ctx.createMediaStreamSource(audioOnly).connect(node)
    analyser.value = node

    isRecording.value = true
    seconds.value = 0
    tick = setInterval(() => seconds.value++, 1000)
    return stream
  }

  /** Stops recording; resolves with the audio Blob (null if nothing was recording). */
  function stop() {
    return new Promise((resolve) => {
      if (!recorder || recorder.state === 'inactive') {
        release()
        return resolve(null)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
        release()
        resolve(blob)
      }
      recorder.stop()
    })
  }

  function release() {
    clearInterval(tick)
    if (ownsStream) stream?.getTracks().forEach((t) => t.stop())
    stream = null
    ctx?.close().catch(() => {})
    ctx = null
    analyser.value = null
    isRecording.value = false
  }

  return { isRecording, seconds, analyser, start, stop, release }
}
