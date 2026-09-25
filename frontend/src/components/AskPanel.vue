<template>
  <div class="ask">
    <div v-if="!items.length && !busy" class="ask-empty">
      <p>Ask about your past conversations.</p>
      <button v-for="q in EXAMPLES" :key="q" type="button" class="chip" @click="send(q)">{{ q }}</button>
    </div>

    <div v-for="(it, i) in items" :key="i" class="qa">
      <div class="q">{{ it.question }}</div>
      <div class="a">{{ it.answer }}</div>
      <div v-if="it.sources?.length" class="srcs">
        <div v-for="s in it.sources" :key="s.session_id" class="src">
          <span class="src-meta">{{ fmt(s.date) }}<template v-if="s.person_name"> · {{ s.person_name }}</template></span>
          <span class="src-text">{{ s.snippet }}</span>
        </div>
      </div>
    </div>
    <div v-if="busy" class="ask-busy">{{ recording ? 'Listening…' : 'Thinking…' }}</div>

    <div class="ask-input">
      <input v-model="text" type="text" placeholder="Ask a question…" :disabled="busy || recording"
             @keyup.enter="send(text)" />
      <button type="button" class="icon-btn" :class="{ on: recording }" :disabled="busy && !recording"
              :aria-label="recording ? 'Stop and ask' : 'Ask by voice'" @click="recording ? sendVoice() : startVoice()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" /><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4" /></svg>
      </button>
      <button type="button" class="btn primary" :disabled="busy || recording || !text.trim()" @click="send(text)">Ask</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { api } from '@/lib/api'
import { toast } from '@/composables/useToast'
import { useAudioRecorder } from '@/composables/useAudioRecorder'

const EXAMPLES = ['Who visited me recently?', 'What did I plan to do today?', 'Did anyone bring me something?']

const items = ref([])   // newest first
const text = ref('')
const busy = ref(false)
const { isRecording: recording, start, stop, release } = useAudioRecorder()

async function ask(fd) {
  busy.value = true
  try {
    const { data } = await api.post('/ask', fd, { timeout: 90000 })
    items.value.unshift(data)
    text.value = ''
  } catch (e) {
    toast(e.response?.data?.detail || 'Could not answer that')
  } finally {
    busy.value = false
  }
}

function send(q) {
  if (!q?.trim() || busy.value) return
  const fd = new FormData()
  fd.append('question', q.trim())
  return ask(fd)
}

async function startVoice() {
  try { await start() } catch (e) { toast('Mic blocked') }
}

async function sendVoice() {
  const blob = await stop()
  if (!blob) return
  const fd = new FormData()
  fd.append('audio', blob, 'question.webm')
  return ask(fd)
}

const fmt = (iso) => new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })

onUnmounted(release)
</script>

<style scoped>
.ask { display: flex; flex-direction: column; gap: 14px; }
.ask-empty p { color: var(--ink-dim); font-size: 13px; margin: 0 0 10px; }
.chip { display: block; width: 100%; text-align: left; background: none; border: 1px solid var(--line); color: var(--ink); border-radius: 999px; padding: 8px 14px; margin-bottom: 8px; font-size: 13px; cursor: pointer; }
.chip:hover { border-color: var(--line-strong); }
.qa { border-top: 1px solid var(--line); padding-top: 12px; }
.q { font-family: var(--font-mono); font-size: 11px; color: var(--ink-dim); margin-bottom: 6px; }
.a { font-size: 14px; line-height: 1.55; }
.srcs { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.src { display: flex; flex-direction: column; gap: 2px; padding: 7px 9px; border-left: 2px solid var(--id-dim); background: rgba(255, 255, 255, 0.03); }
.src-meta { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; color: var(--id); }
.src-text { font-size: 12px; color: var(--ink-dim); line-height: 1.45; white-space: pre-line; }
.ask-busy { font-family: var(--font-mono); font-size: 12px; color: var(--ink-dim); }
.ask-input { display: flex; gap: 8px; align-items: center; position: sticky; bottom: 0; padding-top: 6px; background: var(--panel-strong); }
.ask-input input { flex: 1; min-width: 0; border: 1px solid var(--line); background: rgba(255, 255, 255, 0.03); color: var(--ink); border-radius: 999px; padding: 9px 14px; font-size: 14px; font-family: var(--font-ui); }
.ask-input input:focus { outline: 2px solid var(--glow); outline-offset: 1px; }
</style>
