<template>
  <div class="tl">
    <div class="chips" role="tablist">
      <button v-for="f in FILTERS" :key="f.id" type="button" class="chip" :class="{ on: filter === f.id }" @click="filter = f.id">{{ f.label }}</button>
    </div>

    <div class="tl-actions">
      <button class="btn" type="button" @click="adding = !adding">{{ adding ? 'Cancel' : 'Add an item' }}</button>
    </div>

    <form v-if="adding" class="add" @submit.prevent="add">
      <select v-model="form.kind">
        <option v-for="k in KINDS" :key="k.id" :value="k.id">{{ k.label }}</option>
      </select>
      <input v-model="form.title" type="text" placeholder="What is it?" />
      <input v-model="form.occurs_on" type="date" />
      <div v-if="form.kind === 'money'" class="money">
        <input v-model="form.amount" type="number" step="any" placeholder="Amount" />
        <input v-model="form.currency" type="text" maxlength="4" placeholder="INR" />
      </div>
      <button class="btn primary" type="submit" :disabled="!form.title.trim() || saving">Save</button>
    </form>

    <div v-if="loading" class="hint">Loading…</div>

    <template v-else>
      <section v-if="showUpcoming && upcoming.length" class="group">
        <h4>Coming up</h4>
        <TimelineItem v-for="e in upcoming" :key="'u' + e.id" :e="e" @toggle="toggle" @remove="remove" />
      </section>

      <section v-for="g in groups" :key="g.date" class="group">
        <h4>{{ dayLabel(g.date) }}</h4>
        <TimelineItem v-for="e in g.items" :key="e.id" :e="e" @toggle="toggle" @remove="remove" />
      </section>

      <div v-if="!groups.length && !(showUpcoming && upcoming.length)" class="empty-mini">
        Nothing here yet. Decisions, plans, money and to-dos are picked out of your conversations automatically.
        <div class="tl-actions"><button class="btn" type="button" :disabled="scanning" @click="scan">{{ scanning ? 'Looking…' : 'Look through older conversations' }}</button></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '@/lib/api'
import { toast } from '@/composables/useToast'
import TimelineItem from './TimelineItem.vue'

const KINDS = [
  { id: 'decision', label: 'Decision' },
  { id: 'activity', label: 'Activity' },
  { id: 'event', label: 'Event / appointment' },
  { id: 'money', label: 'Money' },
  { id: 'task', label: 'To-do' },
]
const FILTERS = [{ id: 'all', label: 'All' }, { id: 'decision', label: 'Decisions' }, { id: 'activity', label: 'Activities' },
  { id: 'event', label: 'Events' }, { id: 'money', label: 'Money' }, { id: 'task', label: 'To-do' }]

const filter = ref('all')
const events = ref([])
const upcoming = ref([])
const loading = ref(true)
const adding = ref(false)
const saving = ref(false)
const scanning = ref(false)
const form = ref({ kind: 'task', title: '', occurs_on: '', amount: '', currency: '' })

const showUpcoming = computed(() => filter.value === 'all' || filter.value === 'task' || filter.value === 'event')
const today = () => new Date().toISOString().slice(0, 10)

// past and undated things by day; what is coming up is shown separately above
const groups = computed(() => {
  const upIds = new Set(showUpcoming.value ? upcoming.value.map((e) => e.id) : [])
  const by = {}
  for (const e of events.value) {
    if (upIds.has(e.id)) continue
    ;(by[e.date] ||= []).push(e)
  }
  return Object.keys(by).sort().reverse().map((date) => ({ date, items: by[date] }))
})

function dayLabel(d) {
  const t = today()
  const y = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
  if (d === t) return 'Today'
  if (d === y) return 'Yesterday'
  return new Date(d + 'T12:00').toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })
}

async function load() {
  loading.value = true
  try {
    const params = filter.value === 'all' ? {} : { kind: filter.value }
    const [t, u] = await Promise.all([api.get('/timeline', { params }), api.get('/timeline/upcoming')])
    events.value = t.data.events
    upcoming.value = u.data.events.filter((e) => filter.value === 'all' || e.kind === filter.value)
  } catch (e) {
    toast('Could not load the timeline')
  } finally {
    loading.value = false
  }
}

async function toggle(e) {
  const fd = new FormData()
  fd.append('is_done', String(!e.is_done))
  try { await api.patch(`/timeline/${e.id}`, fd); await load() } catch (err) { toast('Could not update that') }
}

async function remove(e) {
  try { await api.delete(`/timeline/${e.id}`); await load() } catch (err) { toast('Could not delete that') }
}

async function add() {
  saving.value = true
  try {
    const f = form.value
    const fd = new FormData()
    fd.append('kind', f.kind)
    fd.append('title', f.title.trim())
    if (f.occurs_on) fd.append('occurs_on', f.occurs_on)
    if (f.kind === 'money' && f.amount !== '') { fd.append('amount', String(f.amount)); if (f.currency) fd.append('currency', f.currency) }
    await api.post('/timeline', fd)
    form.value = { kind: f.kind, title: '', occurs_on: '', amount: '', currency: '' }
    adding.value = false
    await load()
  } catch (err) {
    toast(err.response?.data?.detail || 'Could not add that')
  } finally {
    saving.value = false
  }
}

async function scan() {
  scanning.value = true
  try {
    const { data } = await api.post('/timeline/reextract', null, { timeout: 180000 })
    toast(data.events ? `Found ${data.events} items` : 'Nothing new found')
    await load()
  } catch (e) {
    toast('Could not look through conversations')
  } finally {
    scanning.value = false
  }
}

onMounted(load)
watch(filter, load)
</script>

<style scoped>
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.chip { background: none; border: 1px solid var(--line); color: var(--ink-dim); border-radius: 999px; padding: 5px 11px; font-size: 12px; cursor: pointer; }
.chip.on { border-color: var(--glow); color: var(--glow); }
.tl-actions { margin: 4px 0 12px; }
.add { display: flex; flex-direction: column; gap: 8px; border: 1px solid var(--line); border-radius: 5px; padding: 10px; margin-bottom: 14px; }
.add input, .add select { border: 1px solid var(--line); background: rgba(255, 255, 255, 0.03); color: var(--ink); border-radius: 4px; padding: 8px 10px; font-size: 14px; font-family: var(--font-ui); }
.add option { background: #0b0f10; }
.money { display: flex; gap: 8px; }
.money input:first-child { flex: 1; }
.money input:last-child { width: 72px; }
.group { margin-bottom: 14px; }
.group h4 { font-family: var(--font-mono); font-size: 11px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-dim); margin: 0 0 6px; }
.hint { color: var(--ink-dim); font-size: 13px; }
</style>
