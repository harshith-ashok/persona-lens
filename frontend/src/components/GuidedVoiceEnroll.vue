<template>
  <div class="guided">
    <div v-if="enrolled && !running" class="done-box">
      <div class="done-line"><span class="tick on">✓</span> Your voice is set up.</div>
      <button class="btn" type="button" @click="begin">Record it again</button>
    </div>

    <template v-else>
      <div class="dots" aria-hidden="true">
        <span v-for="(s, i) in sentences" :key="i" class="dot" :class="{ done: done.has(i), now: i === index && !allDone }" />
      </div>
      <div class="count">{{ allDone ? 'All sentences read' : `Sentence ${index + 1} of ${sentences.length}` }}</div>

      <p v-if="!allDone" class="sentence">
        <span v-for="(w, i) in targetWords" :key="i" class="w" :class="{ hit: heardSet.has(norm(w)) }">{{ w }}</span>
      </p>

      <div class="enroll-visual" style="height: 56px">
        <WaveCanvas :analyser="recorder.analyser.value" color="#FFB238" :bars="36" />
      </div>

      <div class="heard" :class="{ live: phase === 'listening' }">
        <span class="k">What I heard</span>
        <span class="t">{{ heardText || (phase === 'listening' ? 'Listening…' : '—') }}</span>
      </div>

      <div class="enroll-status" :class="{ ok: feedbackOk }">{{ feedback }}</div>

      <div class="row">
        <button v-if="phase === 'idle' || phase === 'retry'" class="btn primary" type="button" :disabled="!sentences.length" @click="listen">
          {{ phase === 'retry' ? 'Try again' : done.size ? 'Read the next sentence' : 'Start — read the sentence aloud' }}
        </button>
        <button v-else-if="phase === 'listening'" class="btn" type="button" @click="stopListening">Done speaking</button>
        <span v-else-if="phase === 'checking' || phase === 'finishing'" class="enroll-timer">{{ phase === 'finishing' ? 'Saving your voice…' : 'Checking…' }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { api } from '@/lib/api'
import { toast } from '@/composables/useToast'
import { useAudioRecorder } from '@/composables/useAudioRecorder'
import { useLiveCaptions } from '@/composables/useLiveCaptions'
import WaveCanvas from './WaveCanvas.vue'

const props = defineProps({
  enrolled: { type: Boolean, default: false }, // the host already has a voice print
})
const emit = defineEmits(['done'])

const AUTO_STOP_SCORE = 0.85   // stop by itself once this much of the sentence has been heard
const MAX_LISTEN_MS = 25000

const sentences = ref([])
const done = ref(new Set())
const index = ref(0)
const phase = ref('idle')      // idle | listening | checking | retry | finishing
const feedback = ref('')
const feedbackOk = ref(false)
const running = ref(false)     // true once the user starts (re-)recording, even if already enrolled

const recorder = useAudioRecorder()
const captions = useLiveCaptions()

let stream = null
let autoStop = null
let maxTimer = null

const allDone = computed(() => sentences.value.length > 0 && done.value.size === sentences.value.length)
const target = computed(() => sentences.value[index.value] || '')
const targetWords = computed(() => target.value.split(/\s+/).filter(Boolean))

const norm = (w) => w.toLowerCase().replace(/[^a-z']/g, '')
const heardText = computed(() => [...captions.lines.value.map((l) => l.text), captions.partial.value].filter(Boolean).join(' ').trim())
const heardSet = computed(() => new Set(heardText.value.split(/\s+/).map(norm).filter(Boolean)))

/** Order-aware word overlap (0..1), like the server's check. */
function similarity(a, b) {
  const x = a.split(/\s+/).map(norm).filter(Boolean)
  const y = b.split(/\s+/).map(norm).filter(Boolean)
  if (!x.length || !y.length) return 0
  const dp = Array.from({ length: x.length + 1 }, () => new Array(y.length + 1).fill(0))
  for (let i = 1; i <= x.length; i++)
    for (let j = 1; j <= y.length; j++)
      dp[i][j] = x[i - 1] === y[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
  return (2 * dp[x.length][y.length]) / (x.length + y.length)
}

onMounted(async () => {
  try {
    const { data } = await api.get('/voice/prompts')
    sentences.value = data.sentences
    done.value = new Set(data.done || [])
    index.value = nextIndex()
    if (!props.enrolled) running.value = true
  } catch (e) {
    feedback.value = 'Could not load the sentences. Check the connection.'
  }
})

const nextIndex = () => {
  const i = sentences.value.findIndex((_, k) => !done.value.has(k))
  return i === -1 ? 0 : i
}

function begin() {
  done.value = new Set()
  index.value = 0
  feedback.value = ''
  running.value = true
}

async function listen() {
  feedback.value = ''
  feedbackOk.value = false
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (e) {
    feedback.value = 'Microphone access was blocked.'
    return
  }
  await recorder.start(stream)
  captions.start(stream, null, { purpose: 'enroll' })
  phase.value = 'listening'
  maxTimer = setTimeout(stopListening, MAX_LISTEN_MS)
}

// once the live text covers the sentence, finish on its own (like a voice assistant setup)
watch(heardText, (text) => {
  if (phase.value !== 'listening' || !target.value) return
  clearTimeout(autoStop)
  if (similarity(target.value, text) >= AUTO_STOP_SCORE) autoStop = setTimeout(stopListening, 800)
})

async function stopListening() {
  if (phase.value !== 'listening') return
  clearTimeout(autoStop)
  clearTimeout(maxTimer)
  phase.value = 'checking'
  captions.stop()
  const blob = await recorder.stop()
  stream?.getTracks().forEach((t) => t.stop())
  stream = null

  try {
    const fd = new FormData()
    fd.append('index', String(index.value))
    fd.append('audio', blob, 'clip.webm')
    const { data } = await api.post('/voice/enroll/clip', fd)
    done.value = new Set(data.done)

    if (!data.ok) {
      feedback.value = data.transcript
        ? `I heard “${data.transcript}”. Please read the sentence exactly as shown.`
        : "I didn't hear anything. Check your microphone and try again."
      phase.value = 'retry'
      return
    }
    feedback.value = 'Got it.'
    feedbackOk.value = true
    if (data.complete) return finish()
    index.value = nextIndex()
    phase.value = 'idle'
  } catch (e) {
    feedback.value = e.response?.data?.detail || 'Could not check that recording.'
    phase.value = 'retry'
  }
}

async function finish() {
  phase.value = 'finishing'
  try {
    await api.post('/voice/enroll/finish')
    toast('Voice saved')
    running.value = false
    phase.value = 'idle'
    emit('done')
  } catch (e) {
    feedback.value = e.response?.data?.detail || 'Could not save your voice.'
    phase.value = 'retry'
  }
}

onUnmounted(() => {
  clearTimeout(autoStop)
  clearTimeout(maxTimer)
  captions.stop()
  recorder.release()
  stream?.getTracks().forEach((t) => t.stop())
})
</script>

<style scoped>
.dots { display: flex; gap: 6px; margin-bottom: 6px; }
.dot { width: 26px; height: 4px; border-radius: 4px; background: var(--line); }
.dot.done { background: var(--glow); }
.dot.now { background: var(--id); }
.count { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-dim); margin-bottom: 8px; }
.sentence { font-size: 20px; line-height: 1.45; font-weight: 500; margin: 0 0 12px; }
.w { color: var(--ink-dim); transition: color 0.15s ease; margin-right: 0.3em; display: inline-block; }
.w.hit { color: var(--glow); }
.heard { border: 1px solid var(--line); border-radius: 5px; padding: 8px 10px; margin: 10px 0; display: flex; flex-direction: column; gap: 3px; min-height: 58px; }
.heard.live { border-color: var(--id-dim); }
.heard .k { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; color: var(--ink-dim); }
.heard .t { font-size: 14px; font-style: italic; }
.row { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.done-box { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.done-line { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.tick { width: 22px; height: 22px; border-radius: 50%; border: 1px solid var(--line-strong); display: grid; place-items: center; font-family: var(--font-mono); font-size: 11px; }
.tick.on { background: var(--glow); border-color: var(--glow); color: #04211B; }
</style>
