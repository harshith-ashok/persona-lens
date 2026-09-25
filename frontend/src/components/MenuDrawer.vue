<template>
  <div>
    <div class="drawer-scrim" :class="{ open }" @click="$emit('close')" />
    <div class="drawer" :class="{ open }" role="dialog" aria-label="Menu">
      <div class="drawer-head">
        <span>Menu</span>
        <button class="drawer-close" type="button" aria-label="Close menu" @click="$emit('close')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 6L6 18M6 6l12 12" /></svg>
        </button>
      </div>
      <div class="drawer-nav">
        <button v-for="t in TABS" :key="t.id" type="button" :class="{ active: tab === t.id }" @click="tab = t.id; selected = null">
          {{ t.label }}
        </button>
      </div>

      <div class="drawer-body">
        <!-- People -->
        <div v-if="tab === 'people'">
          <div v-if="selected" class="detail">
            <button class="back-link" type="button" @click="selected = null">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>People
            </button>
            <div class="p-name" style="font-size: 15px">
              {{ selected.name }}<small>{{ selected.relation || 'Not specified' }} · last seen {{ fmtDate(selected.lastSeen) }}</small>
            </div>
            <div class="detail-block"><div class="k">First met</div><p>{{ selected.firstSummary || 'No summary yet.' }}</p></div>
            <div class="detail-block" style="border-top: none; padding-top: 0">
              <div class="k">Most recent</div><p>{{ selected.lastSummary || 'No summary yet.' }}</p>
            </div>
          </div>
          <template v-else>
            <div v-if="!people.length" class="empty-mini">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></svg>
              No one logged yet.
            </div>
            <div v-for="p in sortedPeople" :key="p.id" class="person-row" tabindex="0" role="button"
                 @click="selected = p" @keydown.enter="selected = p">
              <div class="avatar">{{ initials(p.name) }}</div>
              <div class="p-name">{{ p.name }}<small>{{ p.relation || 'Not specified' }} · {{ p.sessions }} session{{ p.sessions === 1 ? '' : 's' }}<template v-if="p.relevance"> · {{ p.relevance.label }}</template></small></div>
            </div>
          </template>
        </div>

        <!-- History -->
        <div v-else-if="tab === 'history'">
          <div v-if="!history.length" class="empty-mini">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 3" /></svg>
            No sessions yet.
          </div>
          <div v-for="s in history" :key="s.id" class="hist-row">
            <div class="hd">
              <span class="who">{{ s.personName || 'Unnamed' }}</span>
              <span class="date">{{ fmtDate(s.date, true) }}</span>
            </div>
            <div class="snip">{{ truncate(s.summary, 110) }}</div>
            <button v-if="!s.personId && s.status === 'ended'" class="btn name-btn" type="button" @click="$emit('name-session', s)">
              Name this person
            </button>
            <button v-if="s.hasVideo" class="btn name-btn" type="button" @click="$emit('watch-video', s)">Watch video</button>
            <div v-if="s.hostPct !== null" class="diar-bar">
              <span class="host" :style="{ width: s.hostPct + '%' }" /><span class="other" :style="{ width: 100 - s.hostPct + '%' }" />
            </div>
          </div>
        </div>

        <!-- Life timeline -->
        <TimelinePanel v-else-if="tab === 'timeline'" />

        <!-- Ask your memory -->
        <AskPanel v-else-if="tab === 'ask'" />

        <!-- Settings -->
        <div v-else-if="tab === 'settings'" class="settings">
          <label class="setting">
            <span class="l">Big &amp; simple mode<small>Large text, high contrast, and a single big button. Hold the small "Exit" button in the corner to leave it.</small></span>
            <input type="checkbox" :checked="simple" @change="$emit('update:simple', $event.target.checked)" />
          </label>
          <label class="setting">
            <span class="l">Save video of conversations<small>Off by default. When on, the camera video of a vision session is kept on your own backend machine so you can watch it later from History. You can delete any video.</small></span>
            <input type="checkbox" :checked="saveVideo" @change="$emit('update:saveVideo', $event.target.checked)" />
          </label>
        </div>

        <!-- You: name (username), voice and face -->
        <HostSetup v-else :host="host" @changed="$emit('host-changed')" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import HostSetup from './HostSetup.vue'
import AskPanel from './AskPanel.vue'
import TimelinePanel from './TimelinePanel.vue'

const TABS = [
  { id: 'people', label: 'People' },
  { id: 'history', label: 'History' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'ask', label: 'Ask' },
  { id: 'voice', label: 'You' },
  { id: 'settings', label: 'More' },
]

const props = defineProps({
  open: Boolean,
  people: { type: Array, default: () => [] },
  history: { type: Array, default: () => [] },
  host: { type: Object, default: null },
  initialTab: { type: String, default: 'people' },
  simple: { type: Boolean, default: false },
  saveVideo: { type: Boolean, default: false },
})
defineEmits(['close', 'host-changed', 'name-session', 'update:simple', 'update:saveVideo', 'watch-video'])

const tab = ref('people')
const selected = ref(null)

watch(() => props.open, (o) => {
  if (o) { tab.value = props.initialTab; selected.value = null }
})

// closest people first: who they are to you, and how often they show up
const sortedPeople = computed(() => [...props.people].sort((a, b) => (b.relevance?.score ?? 0) - (a.relevance?.score ?? 0)))

const initials = (n) => n.split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
const truncate = (s, n) => (!s ? '—' : s.length > n ? s.slice(0, n - 1) + '…' : s)
function fmtDate(v, short = false) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString([], short ? { month: 'short', day: 'numeric' } : { month: 'short', day: 'numeric', year: 'numeric' })
}
</script>

<style scoped>
.name-btn { padding: 5px 12px; font-size: 12px; margin: 2px 0 8px; }
.drawer-nav button { font-size: 12px; padding: 9px 2px; }
.setting { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 6px 0; cursor: pointer; }
.setting .l { font-size: 14px; }
.setting small { display: block; color: var(--ink-dim); font-size: 12px; line-height: 1.5; margin-top: 4px; }
.setting input { width: 22px; height: 22px; accent-color: var(--glow); flex: none; margin-top: 2px; }
</style>
