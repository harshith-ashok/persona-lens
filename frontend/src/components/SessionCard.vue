<template>
  <div class="session-card-wrap open" @click.self="$emit('close')">
    <div class="session-card">
      <div class="sc-top">
        <span class="sc-kicker">{{ result.mode === 'vision' ? 'Vision' : 'Voice only' }} · {{ clock }}</span>
        <button class="sc-close" type="button" aria-label="Dismiss" @click="$emit('close')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 6L6 18M6 6l12 12" /></svg>
        </button>
      </div>
      <h2>{{ result.person_name || 'Unmatched speaker' }}</h2>
      <p>{{ result.summary || 'No summary was generated for this session.' }}</p>
      <div v-if="hostPct !== null" class="diar-bar">
        <span class="host" :style="{ width: hostPct + '%' }" />
        <span class="other" :style="{ width: 100 - hostPct + '%' }" />
      </div>

      <button v-if="result.transcript" class="tx-toggle" type="button" @click="showTx = !showTx">
        {{ showTx ? 'Hide transcript' : 'Show transcript' }}
      </button>
      <SpeakerTranscript v-if="showTx" :segments="result.segments" :fallback="result.transcript" class="tx-box" />

      <div class="sc-actions">
        <button v-if="result.needs_naming" class="btn primary" type="button" @click="$emit('name')">
          Name person
        </button>
        <button class="btn ghost" type="button" @click="$emit('close')">Dismiss</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import SpeakerTranscript from './SpeakerTranscript.vue'

const props = defineProps({
  result: { type: Object, required: true }, // /session/{id}/end response + person_name, mode, durationSec
})
defineEmits(['close', 'name'])

const showTx = ref(false)

const clock = computed(() => {
  const s = props.result.durationSec ?? 0
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

// share of speech (by characters) that was the host's
const hostPct = computed(() => {
  const lines = props.result.segments
  if (!lines?.length) return null
  let host = 0, total = 0
  for (const l of lines) {
    total += l.text.length
    if (l.speaker === 'host') host += l.text.length
  }
  return total ? Math.round((host / total) * 100) : null
})
</script>

<style scoped>
.tx-toggle { background: none; border: none; color: var(--ink-dim); font-size: 12px; padding: 0 0 10px; cursor: pointer; text-decoration: underline; }
.tx-box { margin-bottom: 14px; }
</style>
