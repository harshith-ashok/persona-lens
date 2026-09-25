<template>
  <div class="it" :class="[e.kind, { done: e.is_done }]">
    <button v-if="e.kind === 'task'" class="check" type="button" :aria-label="e.is_done ? 'Mark not done' : 'Mark done'" @click="$emit('toggle', e)">{{ e.is_done ? '✓' : '' }}</button>
    <span v-else class="dot" />
    <div class="body">
      <div class="top">
        <span class="kind">{{ LABEL[e.kind] }}</span>
        <span v-if="e.occurs_on" class="when">{{ short(e.occurs_on) }}</span>
        <button class="x" type="button" aria-label="Delete" @click="$emit('remove', e)">×</button>
      </div>
      <div class="title">{{ e.title }}<span v-if="e.amount !== null" class="amt"> · {{ fmtAmount }}</span></div>
      <div v-if="e.detail" class="detail">{{ e.detail }}</div>
      <div v-if="e.person_name" class="who">with {{ e.person_name }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ e: { type: Object, required: true } })
defineEmits(['toggle', 'remove'])

const LABEL = { decision: 'Decision', activity: 'Activity', event: 'Event', money: 'Money', task: 'To-do' }
const short = (d) => new Date(d + 'T12:00').toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
const fmtAmount = computed(() => `${Number(props.e.amount).toLocaleString()} ${props.e.currency || ''}`.trim())
</script>

<style scoped>
.it { display: flex; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--line); }
.dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 7px; flex: none; background: var(--ink-dim); }
.decision .dot { background: var(--glow); }
.event .dot { background: var(--id); }
.money .dot { background: #8FE388; }
.check { width: 20px; height: 20px; border-radius: 4px; border: 1.5px solid var(--line-strong); background: none; color: var(--glow); font-size: 13px; line-height: 1; cursor: pointer; flex: none; margin-top: 2px; }
.body { flex: 1; min-width: 0; }
.top { display: flex; align-items: center; gap: 8px; }
.kind { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-dim); }
.when { font-family: var(--font-mono); font-size: 10px; color: var(--id); }
.x { margin-left: auto; background: none; border: none; color: var(--ink-dim); font-size: 16px; cursor: pointer; opacity: 0.5; }
.x:hover { opacity: 1; }
.title { font-size: 14px; font-weight: 500; }
.amt { color: #8FE388; }
.detail { font-size: 12px; color: var(--ink-dim); line-height: 1.45; margin-top: 2px; }
.who { font-size: 11px; color: var(--ink-dim); margin-top: 2px; }
.done .title { text-decoration: line-through; opacity: 0.6; }
</style>
