<template>
  <div class="tx">
    <template v-if="segments?.length">
      <div v-for="(s, i) in segments" :key="i" class="tx-line">
        <span class="tx-dot" :class="s.speaker === 'host' ? 'host' : 'other'" />
        <span class="tx-who">{{ s.name || label(s.speaker) }}</span>
        <span class="tx-text">{{ s.text }}</span>
      </div>
    </template>
    <p v-else-if="fallback" class="tx-plain">{{ fallback }}</p>
    <p v-else class="tx-plain">No speech detected.</p>
  </div>
</template>

<script setup>
defineProps({
  segments: { type: Array, default: null }, // [{ speaker, text }]
  fallback: { type: String, default: '' },  // plain transcript when diarization was unavailable
})

const label = (s) => (s === 'host' ? 'Host' : s === 'other' ? 'Other' : s)
</script>

<style scoped>
.tx { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; }
.tx-line { display: grid; grid-template-columns: 7px 46px 1fr; gap: 8px; align-items: baseline; font-size: 12px; line-height: 1.5; }
.tx-dot { width: 7px; height: 7px; border-radius: 50%; align-self: center; }
.tx-dot.host { background: var(--glow); }
.tx-dot.other { background: var(--id); }
.tx-who { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-dim); }
.tx-text { color: var(--ink); }
.tx-plain { font-size: 12px; color: var(--ink-dim); margin: 0; }
</style>
