<template>
  <div class="recall-stack" aria-live="polite">
    <transition-group name="recall">
      <div v-for="p in people" :key="p.id" class="recall">
        <div class="recall-head">
          <span class="recall-name">{{ p.name }}</span>
          <span v-if="p.relation" class="recall-rel">{{ p.relation }}</span>
        </div>
        <div class="recall-seen">{{ seen(p) }}</div>
        <p class="recall-last">
          <template v-if="p.lastSummary"><b>Last time:</b> {{ p.lastSummary }}</template>
          <template v-else>No conversation has been recorded with them yet.</template>
        </p>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { timeAgo } from '@/lib/format'

defineProps({
  people: { type: Array, default: () => [] }, // entries from GET /people
})

const seen = (p) => (p.lastSeen ? `Last seen ${timeAgo(p.lastSeen)}` : "First time we've met")
</script>
